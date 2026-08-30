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
from app.services.authorization import GLOBAL_READERS, assert_case_status_transition

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
    conditions = []

    if user.role_name not in {str(r) for r in GLOBAL_READERS}:
        conditions.append(
            or_(
                Case.created_by == user.id,
                Case.id.in_(
                    select(CaseAssignment.case_id).where(CaseAssignment.user_id == user.id)
                ),
            )
        )

    if status is not None:
        conditions.append(Case.status == status)

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
