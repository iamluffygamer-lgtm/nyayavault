"""Document upload, versioning, retrieval and integrity verification.

Upload sequence (matches the M0 specification exactly)
------------------------------------------------------
The router has already authenticated the caller and authorised them for the
case before anything here runs. This module then:

    4. validates the file (extension, sniffed content, size)
    5. computes SHA-256 from the uploaded bytes
    6. writes the object to storage under a server-generated key
    7. creates or reuses the Document record
    8. creates the next DocumentVersion (v1 for a new document)
    9. stores the SHA-256 on that version
   10. appends an audit event

Steps 7–10 share one database transaction. If any of them fails, the
transaction rolls back and the orphaned object is removed from storage, so the
store never accumulates blobs with no metadata.

Immutability
------------
Versions are only ever inserted. Re-uploading a file creates v2 alongside v1 —
the earlier bytes and hash stay exactly where they were. `(document_id,
version_number)` is unique, so even a concurrent double-submit cannot produce
two different v2 rows; the loser is rejected rather than overwriting.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ConflictError, IntegrityViolationError, NotFoundError
from app.models.audit import AuditAction, AuditResult
from app.models.case import Case
from app.models.document import Document, DocumentType, DocumentVersion
from app.models.user import User
from app.services import audit_service
from app.services.file_validation import InspectedUpload
from app.storage import ObjectNotFound, ObjectStorage, StorageError, build_object_key

logger = logging.getLogger(__name__)

SHA256_HEX_LENGTH = 64


@dataclass(frozen=True)
class VerificationResult:
    version_number: int
    expected_sha256: str
    computed_sha256: str
    verified: bool
    detail: str


def get_document(db: Session, document_id: uuid.UUID) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise NotFoundError("Document not found.")
    return document


def list_documents(db: Session, *, case_id: uuid.UUID) -> list[Document]:
    return list(
        db.execute(
            select(Document)
            .where(Document.case_id == case_id)
            .order_by(Document.created_at.desc())
        )
        .scalars()
        .all()
    )


def get_version(db: Session, document: Document, version_number: int | None) -> DocumentVersion:
    """Return a specific version, or the current one when `version_number` is None."""
    target = version_number if version_number is not None else document.current_version
    version = db.execute(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document.id,
            DocumentVersion.version_number == target,
        )
    ).scalar_one_or_none()
    if version is None:
        raise NotFoundError(f"Version {target} of this document does not exist.")
    return version


def _next_version_number(db: Session, document_id: uuid.UUID) -> int:
    highest = db.execute(
        select(func.max(DocumentVersion.version_number)).where(
            DocumentVersion.document_id == document_id
        )
    ).scalar_one_or_none()
    return (highest or 0) + 1


def store_version(
    db: Session,
    *,
    storage: ObjectStorage,
    case: Case,
    document: Document,
    inspected: InspectedUpload,
    actor: User,
    change_reason: str | None,
) -> DocumentVersion:
    """Write one new immutable version. Never overwrites an existing one."""
    version_number = _next_version_number(db, document.id)

    # Reject an identical re-upload rather than creating a duplicate revision.
    # This is what stops "save" being pressed twice from polluting the history.
    current = document.latest_version()
    if current is not None and current.sha256_hash == inspected.sha256:
        raise ConflictError(
            f"These bytes are already stored as version {current.version_number} "
            f"(SHA-256 {current.sha256_hash[:16]}…). No new version was created."
        )

    object_key = build_object_key(
        case_id=str(case.id),
        document_id=str(document.id),
        version_number=version_number,
        filename=inspected.safe_filename,
    )

    # A UUID collision is vanishingly unlikely, but overwriting stored evidence
    # would be unrecoverable, so we check before writing.
    if storage.exists(object_key):  # pragma: no cover - defensive
        raise ConflictError("Storage key collision detected; the upload was refused.")

    inspected.handle.seek(0)
    storage.put(object_key, inspected.handle, inspected.size, inspected.mime_type)

    try:
        version = DocumentVersion(
            document_id=document.id,
            version_number=version_number,
            object_key=object_key,
            original_filename=inspected.safe_filename,
            mime_type=inspected.mime_type,
            file_size=inspected.size,
            sha256_hash=inspected.sha256,
            uploaded_by=actor.id,
            change_reason=(change_reason or "").strip() or None,
        )
        db.add(version)
        document.current_version = version_number
        db.flush()

        audit_service.record_event(
            db,
            action=(
                AuditAction.DOCUMENT_UPLOADED
                if version_number == 1
                else AuditAction.DOCUMENT_VERSION_CREATED
            ),
            entity_type="document_version",
            entity_id=version.id,
            case_id=case.id,
            actor_id=actor.id,
            metadata={
                "document_id": str(document.id),
                "document_title": document.title,
                "version_number": version_number,
                "sha256": inspected.sha256,
                "file_size": inspected.size,
                "mime_type": inspected.mime_type,
                "original_filename": inspected.safe_filename,
                "change_reason": version.change_reason,
            },
        )
        db.commit()
        db.refresh(version)
        return version

    except IntegrityError as exc:
        db.rollback()
        storage.delete(object_key)
        raise ConflictError(
            "Another upload created this version first. Retry to append the next version."
        ) from exc
    except Exception:
        db.rollback()
        # Remove the object we just wrote so storage cannot drift ahead of the
        # database. Best-effort: a failure here is logged inside storage.delete.
        storage.delete(object_key)
        raise


def create_document_with_first_version(
    db: Session,
    *,
    storage: ObjectStorage,
    case: Case,
    title: str,
    document_type: DocumentType,
    description: str | None,
    inspected: InspectedUpload,
    actor: User,
    change_reason: str | None,
) -> tuple[Document, DocumentVersion]:
    document = Document(
        case_id=case.id,
        title=title.strip(),
        document_type=document_type,
        description=(description or "").strip() or None,
        current_version=0,
        created_by=actor.id,
    )
    db.add(document)
    db.flush()

    version = store_version(
        db,
        storage=storage,
        case=case,
        document=document,
        inspected=inspected,
        actor=actor,
        change_reason=change_reason,
    )
    db.refresh(document)
    return document, version


def stream_version(
    storage: ObjectStorage, version: DocumentVersion, chunk_size: int = 1024 * 1024
) -> Iterator[bytes]:
    """Yield the stored bytes. Raises NotFoundError if the object has vanished."""
    try:
        yield from storage.stream(version.object_key, chunk_size)
    except ObjectNotFound as exc:
        logger.error(
            "stored_object_missing",
            extra={"version_id": str(version.id), "object_key": version.object_key},
        )
        raise NotFoundError("The stored file is no longer available in object storage.") from exc


def verify_version(storage: ObjectStorage, version: DocumentVersion) -> VerificationResult:
    """Re-read the object and recompute its SHA-256.

    This is the check that makes the stored hash meaningful: it compares the
    bytes as they exist *now* against the digest taken at upload time. Any
    modification made directly in the object store — bypassing the API — shows
    up here as a mismatch.
    """
    digest = hashlib.sha256()
    try:
        for chunk in storage.stream(version.object_key):
            digest.update(chunk)
    except ObjectNotFound:
        return VerificationResult(
            version_number=version.version_number,
            expected_sha256=version.sha256_hash,
            computed_sha256="",
            verified=False,
            detail="The stored object is missing from object storage.",
        )
    except StorageError as exc:
        return VerificationResult(
            version_number=version.version_number,
            expected_sha256=version.sha256_hash,
            computed_sha256="",
            verified=False,
            detail=f"Object storage error during verification: {exc}",
        )

    computed = digest.hexdigest()
    matches = hmac.compare_digest(computed, version.sha256_hash)
    return VerificationResult(
        version_number=version.version_number,
        expected_sha256=version.sha256_hash,
        computed_sha256=computed,
        verified=matches,
        detail=(
            "Stored bytes match the hash recorded at upload."
            if matches
            else "MISMATCH: the stored bytes no longer match the hash recorded at upload."
        ),
    )


def verify_document(
    db: Session,
    *,
    storage: ObjectStorage,
    document: Document,
    actor: User,
    version_number: int | None = None,
) -> dict[str, Any]:
    """Verify one version, or every version when `version_number` is None."""
    versions = (
        [get_version(db, document, version_number)]
        if version_number is not None
        else sorted(document.versions, key=lambda v: v.version_number)
    )
    if not versions:
        raise NotFoundError("This document has no stored versions.")

    results = [verify_version(storage, v) for v in versions]
    all_valid = all(r.verified for r in results)

    audit_service.record_event(
        db,
        action=(
            AuditAction.DOCUMENT_INTEGRITY_VERIFIED
            if all_valid
            else AuditAction.DOCUMENT_INTEGRITY_FAILED
        ),
        entity_type="document",
        entity_id=document.id,
        case_id=document.case_id,
        actor_id=actor.id,
        result=AuditResult.SUCCESS if all_valid else AuditResult.FAILURE,
        metadata={
            "versions_checked": [r.version_number for r in results],
            "failed_versions": [r.version_number for r in results if not r.verified],
        },
    )
    db.commit()

    if not all_valid:
        logger.error(
            "integrity_violation",
            extra={
                "document_id": str(document.id),
                "failed": [r.version_number for r in results if not r.verified],
            },
        )

    return {
        "document_id": str(document.id),
        "algorithm": "SHA-256",
        "verified": all_valid,
        "results": [
            {
                "version_number": r.version_number,
                "expected_sha256": r.expected_sha256,
                "computed_sha256": r.computed_sha256,
                "verified": r.verified,
                "detail": r.detail,
            }
            for r in results
        ],
    }


def raise_if_tampered(result: dict[str, Any]) -> None:
    """Convert a failed verification into a 409 for endpoints that must refuse."""
    if not result.get("verified"):
        raise IntegrityViolationError(
            "Integrity check failed: the stored file no longer matches its recorded SHA-256."
        )
