from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, JSON, DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow, uuid_pk

if TYPE_CHECKING:
    from app.models.user import User

# JSONB on PostgreSQL (indexable, compact); plain JSON on SQLite for tests.
JSONType = JSONB().with_variant(JSON(), "sqlite")

# Sentinel used as the `previous_event_hash` of the very first event. Storing an
# explicit genesis value rather than NULL keeps chain verification uniform: every
# event, including the first, hashes over a 64-character predecessor.
GENESIS_HASH = "0" * 64


class AuditAction(StrEnum):
    LOGIN_SUCCEEDED = "LOGIN_SUCCEEDED"
    LOGIN_FAILED = "LOGIN_FAILED"
    USER_CREATED = "USER_CREATED"
    USER_MODIFIED = "USER_MODIFIED"
    DEPARTMENT_MODIFIED = "DEPARTMENT_MODIFIED"
    CASE_CREATED = "CASE_CREATED"
    CASE_VIEWED = "CASE_VIEWED"
    COURT_ACCESS_GRANTED = "COURT_ACCESS_GRANTED"
    COURT_ACCESS_REDEEMED = "COURT_ACCESS_REDEEMED"
    COURT_CASE_VIEWED = "COURT_CASE_VIEWED"
    COURT_DOCUMENT_VIEWED = "COURT_DOCUMENT_VIEWED"
    COURT_VERIFY_REQUESTED = "COURT_VERIFY_REQUESTED"
    CASE_STATUS_CHANGED = "CASE_STATUS_CHANGED"
    CASE_ACCESS_DENIED = "CASE_ACCESS_DENIED"
    CASE_MEMBER_ASSIGNED = "CASE_MEMBER_ASSIGNED"
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    DOCUMENT_VERSION_CREATED = "DOCUMENT_VERSION_CREATED"
    DOCUMENT_DOWNLOADED = "DOCUMENT_DOWNLOADED"
    DOCUMENT_INTEGRITY_VERIFIED = "DOCUMENT_INTEGRITY_VERIFIED"
    DOCUMENT_INTEGRITY_FAILED = "DOCUMENT_INTEGRITY_FAILED"
    UPLOAD_REJECTED = "UPLOAD_REJECTED"
    EVIDENCE_CREATED = "EVIDENCE_CREATED"
    EVIDENCE_SEALED = "EVIDENCE_SEALED"
    EVIDENCE_TRANSFER_CREATED = "EVIDENCE_TRANSFER_CREATED"
    EVIDENCE_TRANSFER_ACCEPTED = "EVIDENCE_TRANSFER_ACCEPTED"
    EVIDENCE_TRANSFER_REJECTED = "EVIDENCE_TRANSFER_REJECTED"
    EVIDENCE_ANALYSIS_STARTED = "EVIDENCE_ANALYSIS_STARTED"
    EVIDENCE_ANALYSIS_COMPLETED = "EVIDENCE_ANALYSIS_COMPLETED"
    EVIDENCE_COURT_SUBMITTED = "EVIDENCE_COURT_SUBMITTED"
    EVIDENCE_ARCHIVED = "EVIDENCE_ARCHIVED"
    EVIDENCE_INTEGRITY_VERIFIED = "EVIDENCE_INTEGRITY_VERIFIED"
    EVIDENCE_INTEGRITY_FAILED = "EVIDENCE_INTEGRITY_FAILED"
    EVIDENCE_ACCESS_DENIED = "EVIDENCE_ACCESS_DENIED"
    SEARCH_PERFORMED = "SEARCH_PERFORMED"
    ANCHOR_ATTEMPTED = "ANCHOR_ATTEMPTED"


class AuditResult(StrEnum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    DENIED = "DENIED"


class AuditEvent(Base):
    """Append-only, hash-linked audit record.

    Each event stores the hash of the event written immediately before it, so
    the log forms a chain:

        e1.event_hash = H(e1 fields + GENESIS_HASH)
        e2.event_hash = H(e2 fields + e1.event_hash)
        e3.event_hash = H(e3 fields + e2.event_hash)

    Editing or deleting any historical row breaks every hash after it, which
    `POST /api/v1/audit/verify` detects. This gives tamper-EVIDENCE, not tamper-
    proofing: an attacker with write access to the database could recompute the
    whole chain. Anchoring the head hash to external, append-only storage is the
    hardening step planned for a later milestone.

    Nothing in the application ever issues UPDATE or DELETE against this table.
    """

    __tablename__ = "audit_events"

    __table_args__ = (
        CheckConstraint(
            "actor_id IS NOT NULL OR court_grant_id IS NOT NULL OR action = 'LOGIN_FAILED'",
            name="chk_audit_attribution"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    # Nullable because failed logins are recorded before any actor is known.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    court_grant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("court_access_grants.id", ondelete="RESTRICT"), index=True
    )

    case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cases.id", ondelete="SET NULL"), index=True
    )

    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64))

    action: Mapped[AuditAction] = mapped_column(
        SAEnum(AuditAction, native_enum=False, length=48, validate_strings=True), nullable=False
    )
    result: Mapped[AuditResult] = mapped_column(
        SAEnum(AuditResult, native_enum=False, length=16, validate_strings=True),
        default=AuditResult.SUCCESS,
        nullable=False,
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )

    # `metadata` is reserved by SQLAlchemy's declarative API, so the attribute is
    # named event_metadata while the COLUMN is still called `metadata` as the
    # specification requires.
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONType, default=dict, nullable=False
    )

    previous_event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    actor: Mapped["User | None"] = relationship(lazy="joined", foreign_keys=[actor_id])

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditEvent {self.action} {self.event_hash[:12]}>"
