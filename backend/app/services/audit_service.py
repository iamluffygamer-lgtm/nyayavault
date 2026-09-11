"""Hash-linked audit trail.

Design
------
Every state change appends one row to `audit_events`. Each row stores the hash
of its predecessor, so the table is a hash chain:

    event_hash = SHA256(canonical_json({
        actor_id, case_id, entity_type, entity_id, action,
        result, timestamp, metadata, previous_event_hash
    }))

`canonical_json` sorts keys and uses compact separators, so the same logical
event always hashes to the same value regardless of dict ordering or Python
version. Concatenating fields into a single string was rejected because it is
ambiguous — ("ab", "c") and ("a", "bc") would collide.

The chain is GLOBAL rather than per-case: a per-case chain would let an attacker
delete an entire case's history without leaving a gap anywhere else.

Concurrency
-----------
Two simultaneous writes could otherwise read the same head and fork the chain.
On PostgreSQL we take a transaction-scoped advisory lock around the read-head /
append pair, which serialises appends without locking the whole table. SQLite
(tests) serialises writes anyway.

Threat model — read this before calling it a blockchain
-------------------------------------------------------
This gives tamper EVIDENCE. Anyone with UPDATE rights on the database can
rewrite history and recompute every hash. Real tamper resistance needs the head
hash published somewhere append-only outside this database (a notary service,
a WORM bucket, or a ledger). That is deliberately out of M0 scope.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.audit import GENESIS_HASH, AuditAction, AuditEvent, AuditResult
from app.models.base import utcnow

logger = logging.getLogger(__name__)

# Arbitrary but fixed key for the PostgreSQL advisory lock guarding chain appends.
_CHAIN_LOCK_KEY = 8_142_907_311


def canonical_json(payload: dict[str, Any]) -> str:
    """Deterministic JSON encoding used as the pre-image for hashing."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def canonical_timestamp(value: datetime) -> str:
    """Normalise a timestamp to UTC with fixed precision before hashing.

    This matters more than it looks. PostgreSQL returns timezone-aware
    datetimes; SQLite returns naive ones. Hashing `datetime.isoformat()`
    directly would therefore produce one value when the event is written and a
    different value when it is read back, and every verification would report
    tampering that never happened. Naive values are treated as UTC because
    `utcnow()` is the only thing that creates them here.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def compute_event_hash(
    *,
    actor_id: uuid.UUID | None,
    court_grant_id: uuid.UUID | None = None,
    case_id: uuid.UUID | None,
    entity_type: str,
    entity_id: str | None,
    action: str,
    result: str,
    timestamp: datetime,
    metadata: dict[str, Any],
    previous_event_hash: str,
) -> str:
    """SHA-256 over the canonical representation of one event."""
    payload = {
        "actor_id": str(actor_id) if actor_id else None,
        "case_id": str(case_id) if case_id else None,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "action": str(action),
        "result": str(result),
        "timestamp": canonical_timestamp(timestamp),
        "metadata": metadata,
        "previous_event_hash": previous_event_hash,
    }
    if court_grant_id is not None:
        payload["court_grant_id"] = str(court_grant_id)
        
    pre_image = canonical_json(payload)
    return hashlib.sha256(pre_image.encode("utf-8")).hexdigest()


def _lock_chain(db: Session) -> None:
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _CHAIN_LOCK_KEY})


def _head_hash(db: Session) -> str:
    """Hash of the most recently appended event, or the genesis sentinel."""
    stmt = (
        select(AuditEvent.event_hash)
        .order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none() or GENESIS_HASH


def record_event(
    db: Session,
    *,
    action: AuditAction,
    entity_type: str,
    entity_id: str | uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    court_grant_id: uuid.UUID | None = None,
    case_id: uuid.UUID | None = None,
    result: AuditResult = AuditResult.SUCCESS,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    """Append one event to the chain.

    The caller owns the transaction: this function flushes but does not commit,
    so the audit row and the change it describes land atomically. An audit write
    that fails therefore rolls the whole operation back — by design, an action
    that cannot be recorded must not happen.

    `metadata` must contain only non-sensitive, JSON-serialisable values. Never
    put document bytes, passwords or tokens in it.
    """
    _lock_chain(db)

    previous = _head_hash(db)
    timestamp = utcnow()
    payload = metadata or {}
    entity_ref = str(entity_id) if entity_id is not None else None

    event_hash = compute_event_hash(
        actor_id=actor_id,
        court_grant_id=court_grant_id,
        case_id=case_id,
        entity_type=entity_type,
        entity_id=entity_ref,
        action=action,
        result=result,
        timestamp=timestamp,
        metadata=payload,
        previous_event_hash=previous,
    )

    event = AuditEvent(
        actor_id=actor_id,
        court_grant_id=court_grant_id,
        case_id=case_id,
        entity_type=entity_type,
        entity_id=entity_ref,
        action=action,
        result=result,
        timestamp=timestamp,
        event_metadata=payload,
        previous_event_hash=previous,
        event_hash=event_hash,
    )
    db.add(event)
    db.flush()

    logger.info(
        "audit_event",
        extra={
            "action": str(action),
            "result": str(result),
            "entity_type": entity_type,
            "entity_id": entity_ref,
            "actor_id": str(actor_id) if actor_id else None,
            "event_hash": event_hash,
        },
    )
    return event


def list_events(
    db: Session,
    *,
    case_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AuditEvent]:
    """Newest-first audit events, optionally scoped to a single case."""
    stmt = select(AuditEvent).order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc())
    if case_id is not None:
        stmt = stmt.where(AuditEvent.case_id == case_id)
    stmt = stmt.offset(max(offset, 0)).limit(min(max(limit, 1), 200))
    return list(db.execute(stmt).scalars().all())


def verify_chain(db: Session) -> dict[str, Any]:
    """Recompute the entire chain and report whether it is intact.

    The walk follows the hash pointers from the genesis sentinel rather than
    sorting by timestamp. That matters: sorting would trust a column an attacker
    could edit, whereas the pointers are covered by the hashes themselves. It
    also means a deleted event is detected as the chain terminating early with
    rows left over, not merely as a suspicious gap.

    Three failure modes are distinguished:
      * an event whose content no longer hashes to its stored `event_hash`
      * two events claiming the same predecessor (a forked chain)
      * the walk ending while unvisited events remain (a deletion)
    """
    events = list(db.execute(select(AuditEvent)).scalars().all())
    total = len(events)

    if total == 0:
        return {
            "intact": True,
            "events_checked": 0,
            "head_hash": None,
            "broken_at_index": None,
            "broken_event_id": None,
            "detail": "The audit log is empty.",
        }

    by_previous: dict[str, list[AuditEvent]] = {}
    for event in events:
        by_previous.setdefault(event.previous_event_hash, []).append(event)

    cursor = GENESIS_HASH
    index = 0
    while cursor in by_previous:
        successors = by_previous[cursor]
        if len(successors) > 1:
            return _broken(
                total,
                index,
                successors[0],
                f"Forked chain: {len(successors)} events claim the same predecessor.",
            )

        event = successors[0]
        recomputed = compute_event_hash(
            actor_id=event.actor_id,
            court_grant_id=event.court_grant_id,
            case_id=event.case_id,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            action=event.action,
            result=event.result,
            timestamp=event.timestamp,
            metadata=event.event_metadata,
            previous_event_hash=event.previous_event_hash,
        )
        if recomputed != event.event_hash:
            return _broken(
                total,
                index,
                event,
                "Event content does not match its stored hash — the record was altered.",
            )

        cursor = event.event_hash
        index += 1

    if index != total:
        return _broken(
            total,
            index,
            None,
            f"Broken link: the chain ends after {index} of {total} events, "
            f"so {total - index} event(s) were removed or orphaned.",
        )

    return {
        "intact": True,
        "events_checked": total,
        "head_hash": cursor,
        "broken_at_index": None,
        "broken_event_id": None,
        "detail": "Audit chain verified: every event hashes to its stored value.",
    }


def _broken(
    total: int, index: int, event: AuditEvent | None, detail: str
) -> dict[str, Any]:
    logger.error(
        "audit_chain_broken",
        extra={
            "index": index,
            "event_id": str(event.id) if event else None,
            "detail": detail,
        },
    )
    return {
        "intact": False,
        "events_checked": total,
        "head_hash": None,
        "broken_at_index": index,
        "broken_event_id": str(event.id) if event else None,
        "detail": detail,
    }
