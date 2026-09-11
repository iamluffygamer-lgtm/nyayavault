from typing import Any
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Request, HTTPException, status

from app.dependencies import DbSession, CourtGrant
from app.models.case import Case
from app.models.court_access import CourtAccessGrant, CourtAccessStatus
from app.models.audit import AuditAction, AuditResult
from app.models.document import Document
from app.models.evidence import Evidence
from app.security import verify_password, create_court_token
from app.services.audit_service import record_event, list_events
from app.services.case_service import get_case_timeline
from app.services.blockchain_service import verify_on_chain
from app.storage import get_storage
from pydantic import BaseModel
from sqlalchemy import select

router = APIRouter(prefix="/court-access", tags=["Court Access"])

# Rate limiter dictionaries
# In production, these should be in Redis
FAILED_ATTEMPTS_BY_IP_REF: dict[tuple[str, str], int] = {}
FAILED_ATTEMPTS_BY_REF: dict[str, int] = {}

class RedeemRequest(BaseModel):
    reference: str
    code: str

class RedeemResponse(BaseModel):
    token: str

@router.post("/redeem", response_model=RedeemResponse)
def redeem_court_access(req: RedeemRequest, request: Request, db: DbSession) -> Any:
    client_ip = request.client.host if request.client else "unknown"
    ip_ref_key = (client_ip, req.reference)
    
    # Rate limit check
    if FAILED_ATTEMPTS_BY_IP_REF.get(ip_ref_key, 0) > 5:
        raise HTTPException(status_code=429, detail="Too many attempts from this IP.")
    if FAILED_ATTEMPTS_BY_REF.get(req.reference, 0) > 10:
        raise HTTPException(status_code=429, detail="Too many attempts for this reference.")
        
    grant = db.execute(
        select(CourtAccessGrant).where(CourtAccessGrant.reference == req.reference)
    ).scalar_one_or_none()
    
    if not grant:
        FAILED_ATTEMPTS_BY_IP_REF[ip_ref_key] = FAILED_ATTEMPTS_BY_IP_REF.get(ip_ref_key, 0) + 1
        FAILED_ATTEMPTS_BY_REF[req.reference] = FAILED_ATTEMPTS_BY_REF.get(req.reference, 0) + 1
        raise HTTPException(status_code=401, detail="Invalid reference or code.")
        
    if grant.status != CourtAccessStatus.ACTIVE:
        raise HTTPException(status_code=401, detail="This access code is no longer active.")
        
    now = datetime.now(timezone.utc)
    if grant.expires_at < now:
        grant.status = CourtAccessStatus.EXPIRED
        db.flush()
        raise HTTPException(status_code=401, detail="This access code has expired.")
        
    if not verify_password(req.code, grant.code_hash):
        FAILED_ATTEMPTS_BY_IP_REF[ip_ref_key] = FAILED_ATTEMPTS_BY_IP_REF.get(ip_ref_key, 0) + 1
        FAILED_ATTEMPTS_BY_REF[req.reference] = FAILED_ATTEMPTS_BY_REF.get(req.reference, 0) + 1
        raise HTTPException(status_code=401, detail="Invalid reference or code.")
        
    # Success
    FAILED_ATTEMPTS_BY_IP_REF[ip_ref_key] = 0
    FAILED_ATTEMPTS_BY_REF[req.reference] = 0
    
    grant.status = CourtAccessStatus.REDEEMED
    grant.redeemed_at = now
    grant.session_expires_at = now + timedelta(hours=4)
    db.flush()
    
    token, _ = create_court_token(grant.case_id, grant.id, expires_minutes=240)
    
    record_event(
        db,
        action=AuditAction.COURT_ACCESS_REDEEMED,
        entity_type="COURT_ACCESS_GRANT",
        entity_id=grant.id,
        actor_id=None,
        court_grant_id=grant.id,
        case_id=grant.case_id,
        metadata={"ip": client_ip}
    )
    
    return {"token": token}


@router.post("/end-session", summary="End the court session early")
def end_court_session(grant: CourtGrant, db: DbSession) -> dict[str, str]:
    grant.status = CourtAccessStatus.EXPIRED
    now = datetime.now(timezone.utc)
    grant.session_expires_at = now
    db.flush()
    return {"status": "ok"}


from app.schemas.case import CaseRead
from app.schemas.document import DocumentRead, DocumentVersionRead
from app.schemas.evidence import EvidenceRead, EvidenceTransferRead

court_router = APIRouter(prefix="/court", tags=["Court Read-Only Views"])

@court_router.get("/case", response_model=CaseRead)
def get_court_case(grant: CourtGrant, db: DbSession) -> Any:
    case = db.get(Case, grant.case_id)
    record_event(
        db,
        action=AuditAction.COURT_CASE_VIEWED,
        entity_type="CASE",
        entity_id=case.id,
        actor_id=None,
        court_grant_id=grant.id,
        case_id=grant.case_id,
        metadata={}
    )
    return case

@court_router.get("/documents", response_model=list[DocumentRead])
def list_court_documents(grant: CourtGrant, db: DbSession) -> Any:
    docs = db.scalars(select(Document).where(Document.case_id == grant.case_id).order_by(Document.created_at.desc())).all()
    return docs

@court_router.get("/documents/{document_id}/versions", response_model=list[DocumentVersionRead])
def list_court_document_versions(document_id: uuid.UUID, grant: CourtGrant, db: DbSession) -> Any:
    doc = db.get(Document, document_id)
    if not doc or doc.case_id != grant.case_id:
        raise HTTPException(status_code=404, detail="Document not found.")
    record_event(
        db,
        action=AuditAction.COURT_DOCUMENT_VIEWED,
        entity_type="DOCUMENT",
        entity_id=doc.id,
        actor_id=None,
        court_grant_id=grant.id,
        case_id=grant.case_id,
        metadata={"document_id": str(doc.id)}
    )
    return doc.versions

@court_router.get("/documents/{document_id}/versions/{version_id}/verify-chain")
def verify_court_document_chain(document_id: uuid.UUID, version_id: uuid.UUID, grant: CourtGrant, db: DbSession) -> Any:
    doc = db.get(Document, document_id)
    if not doc or doc.case_id != grant.case_id:
        raise HTTPException(status_code=404, detail="Document not found.")
    
    version = next((v for v in doc.versions if v.id == version_id), None)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found.")
        
    record_event(
        db,
        action=AuditAction.COURT_VERIFY_REQUESTED,
        entity_type="DOCUMENT_VERSION",
        entity_id=version.id,
        actor_id=None,
        court_grant_id=grant.id,
        case_id=grant.case_id,
        metadata={"version_id": str(version.id)}
    )
    storage = get_storage()
    return verify_on_chain(db, storage, version_id)

@court_router.get("/evidence", response_model=list[EvidenceRead])
def list_court_evidence(grant: CourtGrant, db: DbSession) -> Any:
    evidence = db.scalars(select(Evidence).where(Evidence.case_id == grant.case_id).order_by(Evidence.collected_at.desc())).all()
    return evidence

from app.schemas.audit import AuditEventRead
from app.schemas.common import Page

@court_router.get("/audit", response_model=Page[AuditEventRead])
def list_court_audit(grant: CourtGrant, db: DbSession, limit: int = 50, offset: int = 0) -> Any:
    events = list_events(db, case_id=grant.case_id, limit=limit, offset=offset)
    from sqlalchemy import func
    from app.models.audit import AuditEvent
    total = db.execute(select(func.count()).select_from(AuditEvent).where(AuditEvent.case_id == grant.case_id)).scalar_one()
    return Page(
        items=[AuditEventRead.model_validate(e) for e in events],
        total=total,
        limit=limit,
        offset=offset,
    )

@court_router.get("/timeline")
def get_court_timeline(grant: CourtGrant, db: DbSession) -> Any:
    return get_case_timeline(db, grant.case_id)

from fastapi.responses import StreamingResponse
import mimetypes

@court_router.get("/documents/{document_id}/download")
def download_court_document(document_id: uuid.UUID, grant: CourtGrant, db: DbSession, version: int | None = None) -> StreamingResponse:
    doc = db.get(Document, document_id)
    if not doc or doc.case_id != grant.case_id:
        raise HTTPException(status_code=404, detail="Document not found.")
        
    vnum = version if version is not None else doc.current_version
    doc_version = next((v for v in doc.versions if v.version_number == vnum), None)
    if not doc_version:
        raise HTTPException(status_code=404, detail="Version not found.")
        
    storage = get_storage()
    try:
        stream = storage.download(doc_version.object_key)
    except Exception:
        raise HTTPException(status_code=404, detail="File not found in storage.")
        
    record_event(
        db,
        action=AuditAction.DOCUMENT_DOWNLOADED,
        entity_type="DOCUMENT_VERSION",
        entity_id=doc_version.id,
        actor_id=None,
        court_grant_id=grant.id,
        case_id=grant.case_id,
        metadata={"document_id": str(doc.id), "version": vnum}
    )
    
    mime_type = mimetypes.guess_type(doc_version.filename)[0] or "application/octet-stream"
    headers = {"Content-Disposition": f'attachment; filename="{doc_version.filename}"'}
    return StreamingResponse(stream, media_type=mime_type, headers=headers)
