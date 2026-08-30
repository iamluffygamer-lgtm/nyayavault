from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.case import CaseAccessLevel, CaseStatus
from app.schemas.common import ORMModel
from app.schemas.user import UserRead


class CaseCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: str | None = Field(None, max_length=20_000)
    status: CaseStatus = CaseStatus.OPEN

    @field_validator("title")
    @classmethod
    def _trim(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be blank.")
        return v


class CaseStatusUpdate(BaseModel):
    status: CaseStatus


class CaseAssignmentCreate(BaseModel):
    user_id: uuid.UUID
    access_level: CaseAccessLevel = CaseAccessLevel.CONTRIBUTE


class CaseAssignmentRead(ORMModel):
    id: uuid.UUID
    user: UserRead
    access_level: CaseAccessLevel
    created_at: datetime


class CaseSummary(ORMModel):
    """Row shape used by list views."""

    id: uuid.UUID
    case_number: str
    title: str
    status: CaseStatus
    created_at: datetime
    updated_at: datetime
    created_by: uuid.UUID


class CaseRead(CaseSummary):
    description: str | None = None
    creator: UserRead
    document_count: int = 0
    # What the *requesting* user may do, so the UI can hide controls it would
    # only be refused on anyway. The server still enforces every action.
    access_level: CaseAccessLevel | None = None
    can_upload: bool = False


class CaseStatistics(BaseModel):
    total_cases: int
    active_cases: int
    closed_cases: int
    total_documents: int
