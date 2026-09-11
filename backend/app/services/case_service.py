"""Case lifecycle."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ConflictError, NotFoundError
from app.models.audit import AuditAction
from app.models.case import Case, CaseAccessLevel, CaseAssignment, CaseStatus
from app.models.document import Document
from app.models.role import RoleName
from app.models.user import User
from app.services import audit_service
from app.services.authorization import assert_case_status_transition, get_authorized_cases_query

logger = logging.getLogger(__name__)

CASE_NUMBER_PREFIX = "NV"
_MAX_NUMBER_ATTEMPTS = 5


def generate_case_number(db: Session, *, year: int | None = None) -> str:
    """Produce the next human-readable case number, e.g. ``NV-2026-000042``.

    Derived from a count of the year's existing cases. Two concurrent creations
    can therefore propose the same number; the unique constraint on
    `cases.case_number` rejects the loser and `create_case` retries. Correctness
    comes from the constraint, not from the counter.
    """
    year = year or datetime.now(timezone.utc).year
    prefix = f"{CASE_NUMBER_PREFIX}-{year}-"
    existing = db.execute(
        select(func.count()).select_from(Case).where(Case.case_number.like(f"{prefix}%"))
    ).scalar_one()
    return f"{prefix}{existing + 1:06d}"


def create_case(
    db: Session,
    *,
    title: str,
    description: str | None,
    status: CaseStatus,
    actor: User,
) -> Case:
    last_error: Exception | None = None

    for attempt in range(_MAX_NUMBER_ATTEMPTS):
        case_number = generate_case_number(db)
        case = Case(
            case_number=case_number,
            title=title.strip(),
            description=(description or "").strip() or None,
            status=status,
            created_by=actor.id,
            department_id=actor.department_id,
        )
        db.add(case)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            last_error = exc
            logger.warning("case_number_collision", extra={"attempt": attempt + 1})
            continue

        # The creator is recorded as an explicit member as well, so case
        # membership is answerable from one table rather than two rules.
        db.add(
            CaseAssignment(
                case_id=case.id,
                user_id=actor.id,
                access_level=CaseAccessLevel.MANAGE,
                assigned_by=actor.id,
            )
        )

        audit_service.record_event(
            db,
            action=AuditAction.CASE_CREATED,
            entity_type="case",
            entity_id=case.id,
            case_id=case.id,
            actor_id=actor.id,
            metadata={"case_number": case.case_number, "status": str(case.status)},
        )
        db.commit()
        db.refresh(case)
        return case

    raise ConflictError("Could not allocate a unique case number. Please retry.") from last_error


def list_cases(
    db: Session,
    *,
    user: User,
    search: str | None = None,
    status: CaseStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Case], int]:
    """Return `(cases, total_matching)` restricted to what the user may see."""
    from app.services.authorization import get_authorized_cases_query
    conditions = [Case.id.in_(get_authorized_cases_query(user))]
    if search:
        # Parameter-bound LIKE. Wildcards in user input are escaped so a search
        # for "%" cannot widen the result set.
        term = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{term.lower()}%"
        conditions.append(
            or_(
                func.lower(Case.case_number).like(pattern, escape="\\"),
                func.lower(Case.title).like(pattern, escape="\\"),
            )
        )

    base = select(Case)
    count_stmt = select(func.count()).select_from(Case)
    for condition in conditions:
        base = base.where(condition)
        count_stmt = count_stmt.where(condition)

    total = db.execute(count_stmt).scalar_one()
    rows = (
        db.execute(
            base.order_by(Case.created_at.desc())
            .offset(max(offset, 0))
            .limit(min(max(limit, 1), 200))
        )
        .scalars()
        .all()
    )
    return list(rows), total


def update_status(db: Session, *, case: Case, target: CaseStatus, actor: User) -> Case:
    assert_case_status_transition(case.status, target)
    previous = case.status
    case.status = target
    db.flush()
    audit_service.record_event(
        db,
        action=AuditAction.CASE_STATUS_CHANGED,
        entity_type="case",
        entity_id=case.id,
        case_id=case.id,
        actor_id=actor.id,
        metadata={"from": str(previous), "to": str(target)},
    )
    db.commit()
    db.refresh(case)
    return case


def assign_member(
    db: Session,
    *,
    case: Case,
    user_id: uuid.UUID,
    access_level: CaseAccessLevel,
    actor: User,
) -> CaseAssignment:
    member = db.get(User, user_id)
    if member is None or not member.is_active:
        raise NotFoundError("User not found.")
    if member.role_name == RoleName.AUDITOR:
        raise ConflictError("Auditors already hold read access to every case.")

    existing = db.execute(
        select(CaseAssignment).where(
            CaseAssignment.case_id == case.id, CaseAssignment.user_id == member.id
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.access_level = access_level
        assignment = existing
    else:
        assignment = CaseAssignment(
            case_id=case.id,
            user_id=member.id,
            access_level=access_level,
            assigned_by=actor.id,
        )
        db.add(assignment)

    db.flush()
    audit_service.record_event(
        db,
        action=AuditAction.CASE_MEMBER_ASSIGNED,
        entity_type="case_assignment",
        entity_id=assignment.id,
        case_id=case.id,
        actor_id=actor.id,
        metadata={"member": member.username, "access_level": str(access_level)},
    )
    db.commit()
    db.refresh(assignment)
    return assignment


def case_statistics(db: Session, *, user: User) -> dict[str, int]:
    """Counts for the dashboard, computed over the caller's visible cases only."""
    from app.services.authorization import get_authorized_cases_query
    
    auth_query = get_authorized_cases_query(user)
    
    total = db.scalar(select(func.count()).select_from(Case).where(Case.id.in_(auth_query))) or 0
    active = db.scalar(select(func.count()).select_from(Case).where(Case.id.in_(auth_query), Case.status.in_({CaseStatus.OPEN, CaseStatus.UNDER_INVESTIGATION, CaseStatus.SUBMITTED}))) or 0
    closed = db.scalar(select(func.count()).select_from(Case).where(Case.id.in_(auth_query), Case.status == CaseStatus.CLOSED)) or 0
    
    documents = db.scalar(select(func.count()).select_from(Document).where(Document.case_id.in_(auth_query))) or 0

    return {
        "total_cases": total,
        "active_cases": active,
        "closed_cases": closed,
        "total_documents": int(documents),
    }


def get_case_timeline(db: Session, case_id: uuid.UUID, limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
    from app.models.audit import AuditEvent, AuditAction
    from app.models.user import User

    query = db.query(AuditEvent).filter(AuditEvent.case_id == case_id)
    total = query.count()
    
    events = query.order_by(AuditEvent.timestamp.desc()).offset(offset).limit(limit).all()
    
    timeline = []
    for e in events:
        actor_name = e.actor.full_name or e.actor.username if e.actor else "System"
        
        summary = f"{actor_name} performed {e.action.lower()}"
        icon_hint = "activity"
        
        # Determine summary and icon based on action
        if e.action == AuditAction.CASE_CREATED:
            summary = f"{actor_name} created the case"
            icon_hint = "case"
        elif e.action == AuditAction.CASE_STATUS_CHANGED:
            new_status = e.event_metadata.get("new_status", "unknown")
            summary = f"{actor_name} changed case status to {new_status}"
            icon_hint = "case"
        elif e.action == AuditAction.DOCUMENT_UPLOADED:
            summary = f"{actor_name} uploaded a new document"
            icon_hint = "document"
        elif e.action == AuditAction.DOCUMENT_VERSION_CREATED:
            summary = f"{actor_name} uploaded a new document version"
            icon_hint = "document"
        elif e.action == AuditAction.DOCUMENT_INTEGRITY_FAILED:
            summary = f"Integrity mismatch detected on document"
            icon_hint = "alert"
        elif e.action == AuditAction.ANCHOR_ATTEMPTED:
            status = e.event_metadata.get("status", "")
            if status == "SUCCESS":
                summary = f"Blockchain anchor confirmed for document"
                icon_hint = "blockchain"
            elif status == "FAILURE":
                summary = f"Blockchain anchor failed for document"
                icon_hint = "alert"
            else:
                summary = f"Blockchain anchor queued"
                icon_hint = "blockchain"
        elif "EVIDENCE" in e.action:
            if "TRANSFER" in e.action:
                summary = f"{actor_name} updated evidence custody"
                icon_hint = "transfer"
            else:
                summary = f"{actor_name} updated evidence"
                icon_hint = "evidence"
                
        timeline.append({
            "id": str(e.id),
            "timestamp": e.timestamp,
            "actor_name": actor_name,
            "action": e.action,
            "summary": summary,
            "icon_hint": icon_hint,
        })
        
    return timeline, total

def get_evidence_timeline(db: Session, evidence_id: uuid.UUID, limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
    from app.models.audit import AuditEvent, AuditAction
    from app.models.user import User

    query = db.query(AuditEvent).filter(AuditEvent.entity_type == "evidence", AuditEvent.entity_id == str(evidence_id))
    total = query.count()
    
    events = query.order_by(AuditEvent.timestamp.desc()).offset(offset).limit(limit).all()
    
    timeline = []
    for e in events:
        actor_name = e.actor.full_name or e.actor.username if e.actor else "System"
        
        summary = f"{actor_name} performed {e.action.lower()}"
        icon_hint = "evidence"
        
        if e.action == AuditAction.EVIDENCE_CREATED:
            summary = f"{actor_name} registered evidence"
        elif e.action == AuditAction.EVIDENCE_SEALED:
            summary = f"{actor_name} sealed evidence"
        elif e.action == AuditAction.EVIDENCE_TRANSFER_CREATED:
            summary = f"{actor_name} initiated custody transfer"
            icon_hint = "transfer"
        elif e.action == AuditAction.EVIDENCE_TRANSFER_ACCEPTED:
            summary = f"{actor_name} accepted custody"
            icon_hint = "transfer"
        elif e.action == AuditAction.EVIDENCE_TRANSFER_REJECTED:
            summary = f"{actor_name} rejected custody"
            icon_hint = "alert"
        elif e.action == AuditAction.EVIDENCE_ANALYSIS_STARTED:
            summary = f"{actor_name} started forensic analysis"
        elif e.action == AuditAction.EVIDENCE_ANALYSIS_COMPLETED:
            summary = f"{actor_name} completed forensic analysis"
        elif e.action == AuditAction.EVIDENCE_COURT_SUBMITTED:
            summary = f"{actor_name} submitted evidence to court"
        elif e.action == AuditAction.EVIDENCE_ARCHIVED:
            summary = f"{actor_name} archived evidence"
            
        timeline.append({
            "id": str(e.id),
            "timestamp": e.timestamp,
            "actor_name": actor_name,
            "action": e.action,
            "summary": summary,
            "icon_hint": icon_hint,
        })
        
    return timeline, total
