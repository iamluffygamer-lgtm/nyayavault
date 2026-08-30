from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.evidence import EvidenceStatus, TransferStatus
from app.schemas.common import ORMModel
from app.schemas.user import UserRead
from app.schemas.document import DocumentRead


class EvidenceCreate(BaseModel):
    title: str = Field(..., max_length=255)
    description: str | None = None
    evidence_type: str = Field(..., max_length=64)
    collected_at: datetime | None = None
    collected_location: str | None = Field(default=None, max_length=255)
    collected_by: uuid.UUID | None = None
    source_document_id: uuid.UUID | None = None


class EvidenceRead(ORMModel):
    id: uuid.UUID
    case_id: uuid.UUID
    evidence_number: str
    title: str
    description: str | None
    evidence_type: str
    status: EvidenceStatus
    collected_at: datetime | None
    collected_location: str | None
    collected_by: uuid.UUID | None
    current_custodian: uuid.UUID | None
    source_document_id: uuid.UUID | None
    sha256_hash: str | None
    created_at: datetime
    updated_at: datetime
    
    collector: UserRead | None = None
    custodian: UserRead | None = None
    source_document: DocumentRead | None = None


class EvidenceTransferCreate(BaseModel):
    to_user_id: uuid.UUID
    reason: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)


class EvidenceTransferRead(ORMModel):
    id: uuid.UUID
    evidence_id: uuid.UUID
    from_user_id: uuid.UUID
    to_user_id: uuid.UUID
    transferred_at: datetime
    received_at: datetime | None
    reason: str | None
    location: str | None
    status: TransferStatus
    created_at: datetime
    
    from_user: UserRead
    to_user: UserRead

class IntegrityVerificationResult(BaseModel):
    evidence_id: uuid.UUID
    source_document_id: uuid.UUID
    expected_hash: str
    actual_hash: str
    is_intact: bool
    verified_at: datetime
