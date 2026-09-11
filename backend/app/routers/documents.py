from __future__ import annotations
from app.models.permission import PermissionName

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile, status, BackgroundTasks
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.dependencies import CurrentUser, DbSession, Storage
from app.errors import NotFoundError
from app.models.audit import AuditAction, AuditResult
from app.models.document import DocumentType
from app.schemas.document import (
    DocumentListItem,
    DocumentRead,
    DocumentVersionRead,
    IntegrityReport,
)
from app.services import audit_service, document_service, extraction_service
from app.services.authorization import AuthorizationService, get_case_for_user
from app.services.file_validation import inspect_upload

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Documents"])


def _load_document_for_user(db, user, document_id: uuid.UUID):
    """Fetch a document and authorise the caller through its parent case."""
    document = document_service.get_document(db, document_id)
    # Authorisation is delegated to the case: a document is never reachable by
    # someone who cannot see the case it belongs to.
    access = get_case_for_user(db, user, document.case_id)
    return document, access


# --------------------------------------------------------------------- upload


@router.post(
    "/cases/{case_id}/documents",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document to a case (creates version 1)",
    responses={
        403: {"description": "Read-only access, or the case is closed"},
        409: {"description": "Identical content already stored"},
        413: {"description": "File exceeds the upload limit"},
        415: {"description": "File type not permitted or content does not match extension"},
    },
)
async def upload_document(
    case_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: DbSession,
    user: CurrentUser,
    storage: Storage,
    file: Annotated[UploadFile, File(description="The document to store")],
    title: Annotated[str, Form(min_length=1, max_length=255)],
    document_type: Annotated[DocumentType, Form()] = DocumentType.OTHER,
    description: Annotated[str | None, Form(max_length=20_000)] = None,
    change_reason: Annotated[str | None, Form(max_length=512)] = None,
) -> DocumentRead:
    """Steps 1–10 of the M0 upload contract, in order.

    1-3 happen before the body runs: the request is validated by FastAPI, the
    caller is authenticated by the dependency, and `get_case_for_user` with
    `require_write=True` authorises them for this case and refuses closed or
    archived cases. Only then is a single byte of the file read.
    """
    access = get_case_for_user(db, user, case_id, require_write=True)
    access = get_case_for_user(db, user, case_id, require_write=True)
    AuthorizationService(db).require(user, PermissionName.DOCUMENT_UPLOAD, access.case)

    settings = get_settings()
    try:
        inspected = await inspect_upload(
            file,
            max_bytes=settings.max_upload_bytes,
            declared_content_type=file.content_type,
        )
    except Exception as exc:
        # A rejected upload is itself worth recording — repeated rejections are
        # a signal, and an officer needs to be able to show they tried.
        audit_service.record_event(
            db,
            action=AuditAction.UPLOAD_REJECTED,
            entity_type="case",
            entity_id=case_id,
            case_id=case_id,
            actor_id=user.id,
            result=AuditResult.FAILURE,
            metadata={
                "filename": (file.filename or "")[:255],
                "declared_content_type": file.content_type,
                "reason": type(exc).__name__,
            },
        )
        db.commit()
        raise

    try:
        document, _version = document_service.create_document_with_first_version(
            db,
            storage=storage,
            case=access.case,
            title=title,
            document_type=document_type,
            description=description,
            inspected=inspected,
            actor=user,
            change_reason=change_reason,
        )
    finally:
        inspected.close()

    version_id = document.latest_version().id
    background_tasks.add_task(extraction_service.extract_text_task, version_id)
    
    from app.services.blockchain_service import anchor_background_task
    from app.database import get_db
    background_tasks.add_task(anchor_background_task, get_db, version_id)

    return DocumentRead.model_validate(document)


@router.post(
    "/documents/{document_id}/versions",
    response_model=DocumentVersionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Append a new version to an existing document",
)
async def upload_version(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: DbSession,
    user: CurrentUser,
    storage: Storage,
    file: Annotated[UploadFile, File()],
    change_reason: Annotated[str, Form(min_length=3, max_length=512)],
) -> DocumentVersionRead:
    """Superseding a document never destroys the previous revision.

    v1 keeps its bytes, its hash and its uploader; the new bytes become v2.
    `change_reason` is mandatory here — a revision to evidence without a stated
    reason is not something a court-facing system should accept silently.
    """
    document = document_service.get_document(db, document_id)
    access = get_case_for_user(db, user, document.case_id, require_write=True)
    AuthorizationService(db).require(user, PermissionName.DOCUMENT_UPLOAD, access.case)

    settings = get_settings()
    inspected = await inspect_upload(
        file, max_bytes=settings.max_upload_bytes, declared_content_type=file.content_type
    )
    try:
        version = document_service.store_version(
            db,
            storage=storage,
            case=access.case,
            document=document,
            inspected=inspected,
            actor=user,
            change_reason=change_reason,
        )
    finally:
        inspected.close()

    background_tasks.add_task(extraction_service.extract_text_task, version.id)
    
    from app.services.blockchain_service import anchor_background_task
    from app.database import get_db
    background_tasks.add_task(anchor_background_task, get_db, version.id)

    return DocumentVersionRead.model_validate(version)


# ----------------------------------------------------------------------- read


@router.get(
    "/cases/{case_id}/documents",
    response_model=list[DocumentListItem],
    summary="List documents in a case",
)
def list_case_documents(
    case_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> list[DocumentListItem]:
    access = get_case_for_user(db, user, case_id)
    documents = document_service.list_documents(db, case_id=access.case.id)

    items: list[DocumentListItem] = []
    for doc in documents:
        latest = doc.latest_version()
        items.append(
            DocumentListItem(
                **{
                    "id": doc.id,
                    "case_id": doc.case_id,
                    "title": doc.title,
                    "document_type": doc.document_type,
                    "current_version": doc.current_version,
                    "created_at": doc.created_at,
                    "updated_at": doc.updated_at,
                },
                latest_sha256=latest.sha256_hash if latest else None,
                latest_file_size=latest.file_size if latest else None,
                latest_filename=latest.original_filename if latest else None,
                latest_uploaded_at=latest.created_at if latest else None,
            )
        )
    return items


@router.get(
    "/documents/{document_id}",
    response_model=DocumentRead,
    summary="Document metadata with full version history",
)
def get_document(document_id: uuid.UUID, db: DbSession, user: CurrentUser) -> DocumentRead:
    document, _access = _load_document_for_user(db, user, document_id)
    return DocumentRead.model_validate(document)


@router.get(
    "/documents/{document_id}/versions",
    response_model=list[DocumentVersionRead],
    summary="Version history, oldest first",
)
def list_versions(
    document_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> list[DocumentVersionRead]:
    document, _access = _load_document_for_user(db, user, document_id)
    ordered = sorted(document.versions, key=lambda v: v.version_number)
    return [DocumentVersionRead.model_validate(v) for v in ordered]


@router.get(
    "/documents/{document_id}/download",
    summary="Download a document version",
    response_class=StreamingResponse,
    responses={200: {"content": {"application/octet-stream": {}}}},
)
def download_document(
    document_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    storage: Storage,
    version: Annotated[int | None, Query(ge=1, description="Defaults to the current version")] = None,
):
    """Stream the bytes back through the API.

    The object store is never exposed to the browser and no presigned URL is
    issued. That costs backend bandwidth, and it buys two things a presigned URL
    cannot: authorisation is re-checked on every byte served, and every read is
    written to the audit chain — which is the beginning of chain of custody.

    `Content-Disposition` uses the sanitised filename, and
    `X-Content-Type-Options: nosniff` stops a browser from re-interpreting the
    payload as something executable.
    """
    document, access = _load_document_for_user(db, user, document_id)
    target = document_service.get_version(db, document, version)

    audit_service.record_event(
        db,
        action=AuditAction.DOCUMENT_DOWNLOADED,
        entity_type="document_version",
        entity_id=target.id,
        case_id=document.case_id,
        actor_id=user.id,
        metadata={
            "document_id": str(document.id),
            "version_number": target.version_number,
            "sha256": target.sha256_hash,
            "access_via": access.via,
        },
    )
    db.commit()

    filename = target.original_filename.replace('"', "")
    return StreamingResponse(
        document_service.stream_version(storage, target),
        media_type=target.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(target.file_size),
            "X-Content-Type-Options": "nosniff",
            "X-Document-SHA256": target.sha256_hash,
            "X-Document-Version": str(target.version_number),
            "Cache-Control": "no-store",
        },
    )


@router.get(
    "/documents/{document_id}/verify",
    response_model=IntegrityReport,
    summary="Recompute SHA-256 from storage and compare against the recorded hash",
)
def verify_document(
    document_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    storage: Storage,
    version: Annotated[int | None, Query(ge=1, description="Defaults to every version")] = None,
) -> IntegrityReport:
    """Proof that stored evidence has not changed since it was submitted.

    Reads the bytes back out of the object store, hashes them again and compares
    against the digest taken at upload. A mismatch means the object was altered
    outside this API. The verification attempt is itself audited, pass or fail.
    """
    document, _access = _load_document_for_user(db, user, document_id)
    if not document.versions:
        raise NotFoundError("This document has no stored versions.")
    report = document_service.verify_document(
        db, storage=storage, document=document, actor=user, version_number=version
    )
    return IntegrityReport(**report)

@router.get(
    "/documents/{document_id}/versions/{version_number}/anchor",
    summary="Get anchor status",
)
def get_anchor_status(
    document_id: uuid.UUID,
    version_number: int,
    db: DbSession,
    user: CurrentUser,
):
    from app.schemas.blockchain import AnchorStatusRead
    from app.errors import NotFoundError
    
    document = get_document(document_id, db, user)
    # The document endpoint currently returns DocumentRead which is Pydantic.
    # We need the ORM object to get versions. Wait, get_document from document_service!
    from app.services.document_service import get_document as svc_get_document, get_version
    doc_orm = svc_get_document(db, document_id)
    # Re-check auth just in case (the svc method does not check auth, the router one does, but we used the router one above)
    version = get_version(db, doc_orm, version_number)
    if not version.blockchain_anchor:
        raise NotFoundError("No anchor found for this version.")
        
    return AnchorStatusRead(
        status=version.blockchain_anchor.status,
        tx_hash=version.blockchain_anchor.tx_hash,
        block_number=version.blockchain_anchor.block_number,
        error_message=version.blockchain_anchor.error_message
    )


@router.get(
    "/documents/{document_id}/versions/{version_number}/verify-chain",
    summary="Three-way verification against blockchain",
)
def verify_chain(
    document_id: uuid.UUID,
    version_number: int,
    db: DbSession,
    user: CurrentUser,
    storage: Storage,
):
    from app.schemas.blockchain import ChainVerificationResult
    from app.services.document_service import get_document as svc_get_document, get_version, build_object_key
    from app.services.blockchain_service import verify_on_chain
    from app.errors import NotFoundError
    
    # auth via router's get_document
    get_document(document_id, db, user)
    
    doc = svc_get_document(db, document_id)
    version = get_version(db, doc, version_number)
    
    stored_hash = version.sha256_hash
    
    # Recompute hash
    object_key = version.object_key
    
    import hashlib
    hasher = hashlib.sha256()
    stream = storage.stream(object_key)
    for chunk in stream:
        hasher.update(chunk)
    computed_hash = hasher.hexdigest()
    
    # Check chain
    on_chain_record = verify_on_chain(stored_hash)
    
    anchor = version.blockchain_anchor
    
    if computed_hash != stored_hash:
        status = "MISMATCH"
        detail = "Object storage has been tampered with!"
    elif not anchor or anchor.status == "PENDING":
        status = "PENDING"
        detail = "Anchor is still pending."
    elif anchor.status == "FAILED":
        status = "UNAVAILABLE"
        detail = "Anchor failed, no chain record."
    else:
        if not on_chain_record:
            status = "MISMATCH"
            detail = "Hash not found on chain despite success status!"
        else:
            status = "VERIFIED"
            detail = "Hash matches DB and Blockchain perfectly."
            
    return ChainVerificationResult(
        status=status,
        stored_hash=stored_hash,
        computed_hash=computed_hash,
        on_chain_hash=stored_hash if on_chain_record else None,
        tx_hash=anchor.tx_hash if anchor else None,
        block_number=anchor.block_number if anchor else None,
        detail=detail
    )

@router.post(
    "/documents/{document_id}/versions/{version_number}/demo-tamper",
    summary="[DEMO] Tamper with a document in storage",
    description="Duplicates the object and overwrites it with corrupt data to test integrity verification.",
    status_code=200,
)
def demo_tamper(
    document_id: uuid.UUID,
    version_number: int,
    db: DbSession,
    user: CurrentUser,
    storage: Storage,
):
    from app.config import get_settings
    from app.errors import NotFoundError, PermissionDeniedError
    from app.services.document_service import get_document as svc_get_document, get_version
    import io
    
    settings = get_settings()
    if not settings.allow_demo_tamper:
        raise NotFoundError("Not Found")
        
    if user.role.name not in ["ADMIN", "INVESTIGATOR"]:
        raise PermissionDeniedError("Not authorized to use demo mode.")
        
    doc = svc_get_document(db, document_id)
    version = get_version(db, doc, version_number)
    
    # Read the existing object
    try:
        stream = storage.stream(version.object_key)
        original_bytes = b"".join(list(stream))
    except Exception as e:
        raise NotFoundError(f"Could not read original object: {e}")
        
    tampered_bytes = original_bytes + b"\n\n[TAMPERED BY DEMO AT " + str(version_number).encode() + b"]"
    
    demo_key = f"demo-tamper/{version.object_key}"
    
    storage.put(demo_key, io.BytesIO(tampered_bytes), len(tampered_bytes), version.mime_type)
    
    version.object_key = demo_key
    db.commit()
    
    return {"status": "TAMPERED", "new_key": demo_key}
