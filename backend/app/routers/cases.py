from __future__ import annotations
from app.models.permission import PermissionName

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select

from app.dependencies import CurrentUser, DbSession
from app.models.audit import AuditAction
from app.models.case import CaseStatus
from app.models.document import Document
from app.schemas.audit import AuditEventRead
from app.schemas.case import (
    TimelineEvent,
    CaseAssignmentCreate,
    CaseAssignmentRead,
    CaseCreate,
    CaseRead,
    CaseStatistics,
    CaseStatusUpdate,
    CaseSummary,
)
from app.schemas.common import Page
from app.services import audit_service, case_service
from app.services.authorization import AuthorizationService, get_case_for_user

router = APIRouter(prefix="/cases", tags=["Cases"])


@router.post(
    "",
    response_model=CaseRead,
    status_code=status.HTTP_201_CREATED,
    summary="Open a new case",
)
def create_case(payload: CaseCreate, db: DbSession, user: CurrentUser) -> CaseRead:
    AuthorizationService(db).require(user, PermissionName.CASE_CREATE)
    case = case_service.create_case(
        db,
        title=payload.title,
        description=payload.description,
        status=payload.status,
        actor=user,
    )
    access = get_case_for_user(db, user, case.id)
    return CaseRead(
        **CaseSummary.model_validate(case).model_dump(),
        description=case.description,
        creator=case.creator,  # type: ignore[arg-type]
        document_count=0,
        access_level=access.level,
        can_upload=access.can_contribute,
    )


@router.get(
    "",
    response_model=Page[CaseSummary],
    summary="List cases visible to the caller",
)
def list_cases(
    db: DbSession,
    user: CurrentUser,
    search: Annotated[str | None, Query(max_length=128)] = None,
    case_status: Annotated[CaseStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[CaseSummary]:
    """Scoping is applied in SQL, not after the fact.

    ADMIN and AUDITOR see everything; everyone else sees only the cases they
    created or were assigned to.
    """
    cases, total = case_service.list_cases(
        db, user=user, search=search, status=case_status, limit=limit, offset=offset
    )
    return Page(
        items=[CaseSummary.model_validate(c) for c in cases],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/statistics",
    response_model=CaseStatistics,
    summary="Dashboard counters over the caller's visible cases",
)
def statistics(db: DbSession, user: CurrentUser) -> CaseStatistics:
    return CaseStatistics(**case_service.case_statistics(db, user=user))


@router.get(
    "/{case_id}",
    response_model=CaseRead,
    summary="Case detail",
    responses={404: {"description": "No such case, or the caller may not see it"}},
)
def get_case(case_id: uuid.UUID, db: DbSession, user: CurrentUser) -> CaseRead:
    access = get_case_for_user(db, user, case_id)
    case = access.case

    document_count = db.execute(
        select(func.count()).select_from(Document).where(Document.case_id == case.id)
    ).scalar_one()

    audit_service.record_event(
        db,
        action=AuditAction.CASE_VIEWED,
        entity_type="case",
        entity_id=case.id,
        case_id=case.id,
        actor_id=user.id,
        metadata={"access_via": access.via},
    )
    db.commit()

    return CaseRead(
        **CaseSummary.model_validate(case).model_dump(),
        description=case.description,
        creator=case.creator,  # type: ignore[arg-type]
        document_count=int(document_count),
        access_level=access.level,
        can_upload=access.can_contribute,
    )


@router.patch(
    "/{case_id}/status",
    response_model=CaseSummary,
    summary="Change case status (requires MANAGE access)",
)
def update_status(
    case_id: uuid.UUID, payload: CaseStatusUpdate, db: DbSession, user: CurrentUser
) -> CaseSummary:
    access = get_case_for_user(db, user, case_id)
    if not access.can_manage:
        from app.errors import PermissionDeniedError

        raise PermissionDeniedError("You do not manage this case.")
    case = case_service.update_status(db, case=access.case, target=payload.status, actor=user)
    return CaseSummary.model_validate(case)


@router.get(
    "/{case_id}/members",
    response_model=list[CaseAssignmentRead],
    summary="List users assigned to a case",
)
def list_members(
    case_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> list[CaseAssignmentRead]:
    access = get_case_for_user(db, user, case_id)
    return [CaseAssignmentRead.model_validate(a) for a in access.case.assignments]


@router.post(
    "/{case_id}/members",
    response_model=CaseAssignmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Grant a user access to a case (requires MANAGE access)",
)
def assign_member(
    case_id: uuid.UUID,
    payload: CaseAssignmentCreate,
    db: DbSession,
    user: CurrentUser,
) -> CaseAssignmentRead:
    access = get_case_for_user(db, user, case_id)
    if not access.can_manage:
        from app.errors import PermissionDeniedError

        raise PermissionDeniedError("You do not manage this case.")
    assignment = case_service.assign_member(
        db,
        case=access.case,
        user_id=payload.user_id,
        access_level=payload.access_level,
        actor=user,
    )
    return CaseAssignmentRead.model_validate(assignment)


@router.get(
    "/{case_id}/audit",
    response_model=Page[AuditEventRead],
    summary="Audit trail for a case",
)
def case_audit(
    case_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AuditEventRead]:
    access = get_case_for_user(db, user, case_id)
    events = audit_service.list_events(db, case_id=access.case.id, limit=limit, offset=offset)
    total = db.execute(
        select(func.count())
        .select_from(audit_service.AuditEvent)
        .where(audit_service.AuditEvent.case_id == access.case.id)
    ).scalar_one()
    return Page(
        items=[AuditEventRead.model_validate(e) for e in events],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{case_id}/lock-for-court",
    response_model=CaseRead,
    summary="Lock case for court (MANAGE access)",
)
def lock_case_for_court(case_id: uuid.UUID, db: DbSession, user: CurrentUser) -> Any:
    access = get_case_for_user(db, user, case_id)
    if not access.can_manage:
        from app.errors import PermissionDeniedError
        raise PermissionDeniedError("You do not manage this case.")
    
    case = access.case
    if case.status != CaseStatus.SUBMITTED:
        from app.errors import ValidationError
        raise ValidationError("Only SUBMITTED cases can be locked for court.")
        
    old_status = case.status
    case.status = CaseStatus.UNDER_TRIAL
    db.flush()
    
    # Audit log
    record_event(
        db,
        action=AuditAction.CASE_STATUS_CHANGED,
        entity_type="CASE",
        entity_id=case.id,
        actor_id=user.id,
        case_id=case.id,
        metadata={"old": str(old_status), "new": str(case.status)}
    )
    return case


@router.post(
    "/{case_id}/court-access",
    summary="Generate court access code (MANAGE access)",
)
def generate_court_access(case_id: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, str]:
    access = get_case_for_user(db, user, case_id)
    if not access.can_manage:
        from app.errors import PermissionDeniedError
        raise PermissionDeniedError("You do not manage this case.")
        
    case = access.case
    if case.status != CaseStatus.UNDER_TRIAL:
        from app.errors import ValidationError
        raise ValidationError("Case must be UNDER_TRIAL to grant court access.")
        
    plaintext_code = secrets.token_urlsafe(16)
    code_hash = hash_password(plaintext_code)
    reference = secrets.token_hex(4)  # 8 char hex string
    
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=30)
    
    grant = CourtAccessGrant(
        case_id=case.id,
        code_hash=code_hash,
        reference=reference,
        created_by=user.id,
        expires_at=expires_at,
    )
    db.add(grant)
    db.flush()
    
    record_event(
        db,
        action=AuditAction.COURT_ACCESS_GRANTED,
        entity_type="COURT_ACCESS_GRANT",
        entity_id=grant.id,
        actor_id=user.id,
        case_id=case.id,
        metadata={"reference": reference, "expires_at": expires_at.isoformat()}
    )
    
    return {"reference": reference, "code": plaintext_code}

@router.get(
    "/{case_id}/timeline",
    response_model=Page[TimelineEvent],
    summary="Get unified case timeline",
)
def get_timeline(
    case_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    limit: int = 50,
    offset: int = 0,
) -> Any:
    # authorize
    get_case_for_user(db, user, case_id)
    
    from app.services.case_service import get_case_timeline
    events, total = get_case_timeline(db, case_id, limit, offset)
    
    return {
        "items": events,
        "total": total,
        "limit": limit,
        "offset": offset,
    }
