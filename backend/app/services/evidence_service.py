from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.models.case import Case, CaseStatus
from app.models.document import Document
from app.models.evidence import Evidence, EvidenceStatus, EvidenceTransfer, TransferStatus
from app.models.user import User
from app.models.audit import AuditAction, AuditResult
from app.schemas.evidence import EvidenceCreate, EvidenceTransferCreate
from app.services import audit_service
from app.storage import ObjectStorage
from app.services.document_service import verify_version, VerificationResult

logger = logging.getLogger(__name__)

VALID_TRANSITIONS = {
    EvidenceStatus.COLLECTED: {EvidenceStatus.REGISTERED},
    EvidenceStatus.REGISTERED: {EvidenceStatus.SEALED},
    EvidenceStatus.SEALED: {EvidenceStatus.IN_CUSTODY},
    EvidenceStatus.IN_CUSTODY: {EvidenceStatus.TRANSFER_PENDING, EvidenceStatus.UNDER_ANALYSIS},
    EvidenceStatus.TRANSFER_PENDING: {EvidenceStatus.IN_CUSTODY},
    EvidenceStatus.UNDER_ANALYSIS: {EvidenceStatus.ANALYZED},
    EvidenceStatus.ANALYZED: {EvidenceStatus.COURT_SUBMITTED},
    EvidenceStatus.COURT_SUBMITTED: {EvidenceStatus.ARCHIVED},
    EvidenceStatus.ARCHIVED: set(),
}

def register_evidence(
    db: Session,
    *,
    case: Case,
    create: EvidenceCreate,
    actor: User,
) -> Evidence:
    if case.status == CaseStatus.ARCHIVED:
        raise PermissionDeniedError("Cannot add evidence to an archived case.")

    # Must be unique in case
    existing = db.query(Evidence).filter_by(case_id=case.id, evidence_number=create.title).first()
    # Actually evidence_number generation can be explicit or we can just generate a UUID or use a counter. Wait, prompt says: "Evidence number must be unique within the case." 
    # Let's generate a unique evidence number based on case.case_number or let the client pass it? 
    # The schema doesn't have evidence_number. Let's auto-generate it.
    count = db.query(Evidence).filter_by(case_id=case.id).count()
    evidence_num = f"{case.case_number}-EV-{count + 1:04d}"

    source_doc = None
    sha256_hash = None
    if create.source_document_id:
        source_doc = db.get(Document, create.source_document_id)
        if not source_doc or source_doc.case_id != case.id:
            raise ValidationError("Source document not found or belongs to a different case.")
        latest = source_doc.latest_version()
        if latest:
            sha256_hash = latest.sha256_hash

    evidence = Evidence(
        case_id=case.id,
        evidence_number=evidence_num,
        title=create.title,
        description=create.description,
        evidence_type=create.evidence_type,
        status=EvidenceStatus.REGISTERED,
        collected_at=create.collected_at,
        collected_location=create.collected_location,
        collected_by=create.collected_by,
        current_custodian=actor.id,
        source_document_id=create.source_document_id,
        sha256_hash=sha256_hash
    )
    db.add(evidence)
    db.flush()

    audit_service.record_event(
        db,
        action=AuditAction.EVIDENCE_CREATED,
        entity_type="evidence",
        entity_id=str(evidence.id),
        case_id=case.id,
        actor_id=actor.id,
        metadata={
            "evidence_number": evidence.evidence_number,
            "title": evidence.title,
            "evidence_type": evidence.evidence_type,
            "source_document_id": str(create.source_document_id) if create.source_document_id else None
        },
    )
    db.commit()
    db.refresh(evidence)
    return evidence


def get_evidence(db: Session, evidence_id: uuid.UUID) -> Evidence:
    ev = db.get(Evidence, evidence_id)
    if not ev:
        raise NotFoundError("Evidence not found.")
    return ev


def update_status(db: Session, evidence: Evidence, new_status: EvidenceStatus, actor: User) -> Evidence:
    if new_status not in VALID_TRANSITIONS.get(evidence.status, set()):
        raise ValidationError(f"Invalid state transition from {evidence.status} to {new_status}")
    
    old_status = evidence.status
    evidence.status = new_status
    
    # Audit actions mapping
    action_map = {
        EvidenceStatus.SEALED: AuditAction.EVIDENCE_SEALED,
        EvidenceStatus.UNDER_ANALYSIS: AuditAction.EVIDENCE_ANALYSIS_STARTED,
        EvidenceStatus.ANALYZED: AuditAction.EVIDENCE_ANALYSIS_COMPLETED,
        EvidenceStatus.COURT_SUBMITTED: AuditAction.EVIDENCE_COURT_SUBMITTED,
        EvidenceStatus.ARCHIVED: AuditAction.EVIDENCE_ARCHIVED
    }
    action = action_map.get(new_status)

    if action:
        audit_service.record_event(
            db,
            action=action,
            entity_type="evidence",
            entity_id=str(evidence.id),
            case_id=evidence.case_id,
            actor_id=actor.id,
            metadata={"old_status": old_status, "new_status": new_status},
        )
    db.commit()
    db.refresh(evidence)
    return evidence

def initiate_transfer(db: Session, evidence: Evidence, create: EvidenceTransferCreate, actor: User) -> EvidenceTransfer:
    if evidence.status == EvidenceStatus.ARCHIVED:
        raise PermissionDeniedError("Archived evidence cannot be transferred.")
    if evidence.current_custodian != actor.id:
        raise PermissionDeniedError("Only the current custodian can initiate a transfer.")
    if actor.id == create.to_user_id:
        raise ValidationError("Cannot transfer evidence to yourself.")
    if evidence.status == EvidenceStatus.TRANSFER_PENDING:
        raise ConflictError("A transfer is already pending.")

    target_user = db.get(User, create.to_user_id)
    if not target_user or not target_user.is_active:
        raise ValidationError("Target user does not exist or is inactive.")

    transfer = EvidenceTransfer(
        evidence_id=evidence.id,
        from_user_id=actor.id,
        to_user_id=create.to_user_id,
        reason=create.reason,
        location=create.location,
        status=TransferStatus.PENDING
    )
    db.add(transfer)
    
    old_status = evidence.status
    evidence.status = EvidenceStatus.TRANSFER_PENDING
    db.flush()

    audit_service.record_event(
        db,
        action=AuditAction.EVIDENCE_TRANSFER_CREATED,
        entity_type="evidence_transfer",
        entity_id=str(transfer.id),
        case_id=evidence.case_id,
        actor_id=actor.id,
        metadata={"to_user_id": str(create.to_user_id), "evidence_id": str(evidence.id)},
    )
    db.commit()
    db.refresh(transfer)
    return transfer

def accept_transfer(db: Session, transfer: EvidenceTransfer, actor: User) -> EvidenceTransfer:
    if transfer.status != TransferStatus.PENDING:
        raise ConflictError("Transfer is not pending.")
    if transfer.to_user_id != actor.id:
        raise PermissionDeniedError("Only the recipient can accept the transfer.")

    transfer.status = TransferStatus.COMPLETED
    transfer.received_at = __import__("app.models.base", fromlist=["utcnow"]).utcnow()
    
    evidence = transfer.evidence
    evidence.current_custodian = actor.id
    evidence.status = EvidenceStatus.IN_CUSTODY

    audit_service.record_event(
        db,
        action=AuditAction.EVIDENCE_TRANSFER_ACCEPTED,
        entity_type="evidence_transfer",
        entity_id=str(transfer.id),
        case_id=evidence.case_id,
        actor_id=actor.id,
        metadata={"from_user_id": str(transfer.from_user_id)},
    )
    db.commit()
    db.refresh(transfer)
    return transfer

def reject_transfer(db: Session, transfer: EvidenceTransfer, actor: User) -> EvidenceTransfer:
    if transfer.status != TransferStatus.PENDING:
        raise ConflictError("Transfer is not pending.")
    if transfer.to_user_id != actor.id:
        raise PermissionDeniedError("Only the recipient can reject the transfer.")

    transfer.status = TransferStatus.REJECTED
    evidence = transfer.evidence
    evidence.status = EvidenceStatus.IN_CUSTODY # custodian remains the same

    audit_service.record_event(
        db,
        action=AuditAction.EVIDENCE_TRANSFER_REJECTED,
        entity_type="evidence_transfer",
        entity_id=str(transfer.id),
        case_id=evidence.case_id,
        actor_id=actor.id,
        metadata={"from_user_id": str(transfer.from_user_id)},
    )
    db.commit()
    db.refresh(transfer)
    return transfer


def verify_integrity(db: Session, storage: ObjectStorage, evidence: Evidence, actor: User) -> dict[str, Any]:
    if not evidence.source_document_id:
        raise ValidationError("This evidence is not associated with a document.")
    
    doc = db.get(Document, evidence.source_document_id)
    latest_version = doc.latest_version()
    if not latest_version:
        raise ValidationError("Source document has no versions.")
    
    result = verify_version(storage, latest_version)
    
    # We compare result.computed_sha256 with evidence.sha256_hash instead of doc version hash
    matches = False
    if result.computed_sha256 and evidence.sha256_hash:
        import hmac
        matches = hmac.compare_digest(result.computed_sha256, evidence.sha256_hash)
    
    audit_service.record_event(
        db,
        action=AuditAction.EVIDENCE_INTEGRITY_VERIFIED if matches else AuditAction.EVIDENCE_INTEGRITY_FAILED,
        entity_type="evidence",
        entity_id=str(evidence.id),
        case_id=evidence.case_id,
        actor_id=actor.id,
        metadata={
            "expected_hash": evidence.sha256_hash,
            "computed_hash": result.computed_sha256,
            "is_intact": matches
        },
    )
    db.commit()
    return {
        "evidence_id": str(evidence.id),
        "source_document_id": str(doc.id),
        "expected_hash": evidence.sha256_hash,
        "actual_hash": result.computed_sha256,
        "is_intact": matches,
        "verified_at": __import__("app.models.base", fromlist=["utcnow"]).utcnow().isoformat()
    }
