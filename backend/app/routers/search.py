import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query, BackgroundTasks
from pydantic import BaseModel, ConfigDict

from app.dependencies import CurrentUser, DbSession
from app.services import search_service, extraction_service, audit_service
from app.models.audit import AuditAction, AuditResult


router = APIRouter(tags=["search"])


class SearchResultItem(BaseModel):
    document_id: uuid.UUID
    title: str
    case_id: uuid.UUID
    case_number: str
    document_type: str
    version: int
    uploaded_at: datetime
    uploaded_by: str
    snippet: str | None = None
    extraction_status: str

    model_config = ConfigDict(from_attributes=True)


class SearchResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[SearchResultItem]


@router.get("/search", response_model=SearchResponse)
def execute_search(
    db: DbSession,
    user: CurrentUser,
    q: str | None = Query(None, min_length=1),
    case_id: uuid.UUID | None = None,
    document_type: str | None = None,
    uploaded_by: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Any:
    results = search_service.execute_search(
        db,
        user,
        q=q,
        case_id=case_id,
        document_type=document_type,
        uploaded_by=uploaded_by,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )

    # Audit the search
    audit_service.record_event(
        db,
        action=AuditAction.SEARCH_PERFORMED,
        entity_type="search",
        entity_id=None,
        actor_id=user.id,
        result=AuditResult.SUCCESS,
        metadata={
            "q": q,
            "case_id": str(case_id) if case_id else None,
            "document_type": document_type,
            "results_count": results["total"],
        }
    )

    return results


@router.post("/documents/{document_id}/versions/{version}/ocr")
def trigger_ocr(
    document_id: uuid.UUID,
    version: int,
    background_tasks: BackgroundTasks,
    db: DbSession,
    user: CurrentUser,
) -> Any:
    from app.models.document import Document
    from app.services.authorization import AuthorizationService, PermissionName
    
    doc = db.get(Document, document_id)
    if not doc:
        from app.errors import NotFoundError
        raise NotFoundError("Document not found")
        
    AuthorizationService(db).require(user, PermissionName.DOCUMENT_UPLOAD, doc.case)
    
    version_id = None
    for v in doc.versions:
        if v.version_number == version:
            version_id = v.id
            break
            
    if not version_id:
        from app.errors import NotFoundError
        raise NotFoundError("Version not found")

    from app.models.document import DocumentText, ExtractionStatus
    from sqlalchemy import select
    existing_text = db.scalar(select(DocumentText).where(DocumentText.document_version_id == version_id))
    if existing_text:
        if existing_text.extraction_status == ExtractionStatus.PROCESSING or (existing_text.extraction_status == ExtractionStatus.COMPLETED and existing_text.extraction_method == "OCR"):
            return {"status": "Already processed or processing"}
        existing_text.extraction_status = ExtractionStatus.PROCESSING
    else:
        existing_text = DocumentText(document_version_id=version_id, extraction_status=ExtractionStatus.PROCESSING)
        db.add(existing_text)
    
    db.commit()
    background_tasks.add_task(extraction_service.extract_text_task, version_id, True)
    return {"status": "Processing"}

