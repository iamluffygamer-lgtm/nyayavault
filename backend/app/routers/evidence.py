from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db, get_storage
from app.errors import NotFoundError, PermissionDeniedError
from app.models.case import Case, CaseStatus
from app.models.evidence import Evidence, EvidenceStatus, EvidenceTransfer
from app.models.user import User
from app.schemas.evidence import (
    EvidenceCreate,
    EvidenceRead,
    EvidenceTransferCreate,
    EvidenceTransferRead,
    IntegrityVerificationResult,
)
from app.services.authorization import get_case_for_user
from app.services.evidence_service import (
    accept_transfer,
    get_evidence,
    initiate_transfer,
    register_evidence,
    reject_transfer,
    update_status,
    verify_integrity,
)
from app.storage import ObjectStorage
from app.models.role import RoleName
from app.services.authorization import require_role

router = APIRouter(tags=["Evidence"])


@router.post(
    "/cases/{case_id}/evidence",
    response_model=EvidenceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register new evidence",
)
def create_evidence(
    case_id: uuid.UUID,
    payload: EvidenceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    access = get_case_for_user(db, user, case_id, require_write=True)
    require_role(user, frozenset({RoleName.INVESTIGATOR, RoleName.ADMIN}), action="create evidence")
    return register_evidence(db, case=access.case, create=payload, actor=user)


@router.get(
    "/cases/{case_id}/evidence",
    response_model=list[EvidenceRead],
    summary="List case evidence",
)
def list_case_evidence(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    access = get_case_for_user(db, user, case_id)
    return db.scalars(
        select(Evidence)
        .where(Evidence.case_id == case_id)
        .order_by(Evidence.created_at.desc())
    ).all()


@router.get(
    "/evidence/{evidence_id}",
    response_model=EvidenceRead,
    summary="Get evidence details",
)
def get_evidence_detail(
    evidence_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    evidence = get_evidence(db, evidence_id)
    get_case_for_user(db, user, evidence.case_id)
    return evidence


@router.post(
    "/evidence/{evidence_id}/transfers",
    response_model=EvidenceTransferRead,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a custody transfer",
)
def create_transfer(
    evidence_id: uuid.UUID,
    payload: EvidenceTransferCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    evidence = get_evidence(db, evidence_id)
    get_case_for_user(db, user, evidence.case_id, require_write=True)
    require_role(user, frozenset({RoleName.INVESTIGATOR, RoleName.FORENSIC_OFFICER, RoleName.ADMIN}), action="transfer evidence")
    return initiate_transfer(db, evidence=evidence, create=payload, actor=user)


@router.get(
    "/evidence/{evidence_id}/transfers",
    response_model=list[EvidenceTransferRead],
    summary="List transfers for evidence",
)
def list_transfers(
    evidence_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    evidence = get_evidence(db, evidence_id)
    get_case_for_user(db, user, evidence.case_id)
    return db.scalars(
        select(EvidenceTransfer)
        .where(EvidenceTransfer.evidence_id == evidence_id)
        .order_by(EvidenceTransfer.created_at.asc())
    ).all()


@router.post(
    "/transfers/{transfer_id}/accept",
    response_model=EvidenceTransferRead,
    summary="Accept a custody transfer",
)
def accept_transfer_endpoint(
    transfer_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    transfer = db.get(EvidenceTransfer, transfer_id)
    if not transfer:
        raise NotFoundError("Transfer not found.")
    get_case_for_user(db, user, transfer.evidence.case_id)
    return accept_transfer(db, transfer=transfer, actor=user)


@router.post(
    "/transfers/{transfer_id}/reject",
    response_model=EvidenceTransferRead,
    summary="Reject a custody transfer",
)
def reject_transfer_endpoint(
    transfer_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    transfer = db.get(EvidenceTransfer, transfer_id)
    if not transfer:
        raise NotFoundError("Transfer not found.")
    get_case_for_user(db, user, transfer.evidence.case_id)
    return reject_transfer(db, transfer=transfer, actor=user)


@router.post("/evidence/{evidence_id}/seal", response_model=EvidenceRead)
def seal_evidence(
    evidence_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    evidence = get_evidence(db, evidence_id)
    get_case_for_user(db, user, evidence.case_id, require_write=True)
    require_role(user, frozenset({RoleName.INVESTIGATOR, RoleName.ADMIN}), action="seal evidence")
    return update_status(db, evidence, EvidenceStatus.SEALED, user)


@router.post("/evidence/{evidence_id}/start-analysis", response_model=EvidenceRead)
def start_analysis(
    evidence_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    evidence = get_evidence(db, evidence_id)
    get_case_for_user(db, user, evidence.case_id, require_write=True)
    require_role(user, frozenset({RoleName.FORENSIC_OFFICER, RoleName.ADMIN}), action="analyze evidence")
    if evidence.current_custodian != user.id:
        raise PermissionDeniedError("Only the current custodian can start analysis.")
    return update_status(db, evidence, EvidenceStatus.UNDER_ANALYSIS, user)


@router.post("/evidence/{evidence_id}/complete-analysis", response_model=EvidenceRead)
def complete_analysis(
    evidence_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    evidence = get_evidence(db, evidence_id)
    get_case_for_user(db, user, evidence.case_id, require_write=True)
    require_role(user, frozenset({RoleName.FORENSIC_OFFICER, RoleName.ADMIN}), action="analyze evidence")
    if evidence.current_custodian != user.id:
        raise PermissionDeniedError("Only the current custodian can complete analysis.")
    return update_status(db, evidence, EvidenceStatus.ANALYZED, user)


@router.post("/evidence/{evidence_id}/submit", response_model=EvidenceRead)
def submit_evidence(
    evidence_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    evidence = get_evidence(db, evidence_id)
    get_case_for_user(db, user, evidence.case_id, require_write=True)
    require_role(user, frozenset({RoleName.LEGAL_OFFICER, RoleName.INVESTIGATOR, RoleName.ADMIN}), action="submit evidence")
    return update_status(db, evidence, EvidenceStatus.COURT_SUBMITTED, user)


@router.post("/evidence/{evidence_id}/archive", response_model=EvidenceRead)
def archive_evidence(
    evidence_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    evidence = get_evidence(db, evidence_id)
    get_case_for_user(db, user, evidence.case_id)
    require_role(user, frozenset({RoleName.ADMIN, RoleName.INVESTIGATOR, RoleName.LEGAL_OFFICER}), action="archive evidence")
    return update_status(db, evidence, EvidenceStatus.ARCHIVED, user)


@router.get("/evidence/{evidence_id}/verify", response_model=IntegrityVerificationResult)
def verify_evidence(
    evidence_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    storage: ObjectStorage = Depends(get_storage),
) -> Any:
    evidence = get_evidence(db, evidence_id)
    get_case_for_user(db, user, evidence.case_id)
    # Auditor role should definitely be allowed. Other users as well since integrity verification shouldn't be restricted heavily
    # but the prompt says: "verify the current user can access the document", which `get_case_for_user` covers since documents are tied to cases.
    return verify_integrity(db, storage=storage, evidence=evidence, actor=user)

