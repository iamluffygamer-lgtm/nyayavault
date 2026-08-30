from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.document import DocumentType
from app.schemas.common import ORMModel
from app.schemas.user import UserRead


class DocumentTextRead(ORMModel):
    extracted_text: str | None = None
    extraction_method: str | None = None
    extraction_status: str

class DocumentVersionRead(ORMModel):
    id: uuid.UUID
    version_number: int
    original_filename: str
    mime_type: str
    file_size: int
    sha256_hash: str = Field(..., description="Lowercase hex SHA-256 of the stored bytes")
    change_reason: str | None = None
    created_at: datetime
    uploader: UserRead
    text: DocumentTextRead | None = None

    # `object_key` is intentionally NOT exposed. Storage layout is an internal
    # detail and publishing it would help an attacker who reached MinIO directly.


class DocumentSummary(ORMModel):
    id: uuid.UUID
    case_id: uuid.UUID
    title: str
    document_type: DocumentType
    current_version: int
    created_at: datetime
    updated_at: datetime


class DocumentRead(DocumentSummary):
    description: str | None = None
    creator: UserRead
    versions: list[DocumentVersionRead] = []


class DocumentListItem(DocumentSummary):
    """List row carrying just enough of the current version for the table."""

    latest_sha256: str | None = None
    latest_file_size: int | None = None
    latest_filename: str | None = None
    latest_uploaded_at: datetime | None = None


class VersionVerification(BaseModel):
    version_number: int
    expected_sha256: str
    computed_sha256: str
    verified: bool
    detail: str


class IntegrityReport(BaseModel):
    document_id: str
    algorithm: str = "SHA-256"
    verified: bool
    results: list[VersionVerification]
