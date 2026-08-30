from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.dependencies import DbSession, RequireRoles
from app.models.audit import AuditEvent
from app.models.role import RoleName
from app.models.user import User
from app.schemas.audit import AuditEventRead, ChainVerificationReport
from app.schemas.common import Page
from app.services import audit_service

router = APIRouter(prefix="/audit", tags=["Audit"])

# The system-wide audit log is oversight material: ADMIN and AUDITOR only.
# Case participants read their own case's trail via GET /cases/{id}/audit.
OversightUser = Annotated[
    User,
    Depends(RequireRoles(RoleName.ADMIN, RoleName.AUDITOR, action="read the system audit log")),
]


@router.get(
    "/events",
    response_model=Page[AuditEventRead],
    summary="System-wide audit trail (ADMIN, AUDITOR)",
)
def list_events(
    db: DbSession,
    _user: OversightUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AuditEventRead]:
    events = audit_service.list_events(db, limit=limit, offset=offset)
    total = db.execute(select(func.count()).select_from(AuditEvent)).scalar_one()
    return Page(
        items=[AuditEventRead.model_validate(e) for e in events],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/verify",
    response_model=ChainVerificationReport,
    summary="Verify the integrity of the whole audit chain (ADMIN, AUDITOR)",
)
def verify_chain(db: DbSession, _user: OversightUser) -> ChainVerificationReport:
    """Recompute every event hash and confirm each links to its predecessor.

    If any historical row was edited or removed directly in the database, this
    reports the exact index at which the chain stops verifying.

    Tamper-evidence, not tamper-proofing — see the note in
    `app/services/audit_service.py` for the threat model and what a later
    milestone needs to add.
    """
    return ChainVerificationReport(**audit_service.verify_chain(db))
