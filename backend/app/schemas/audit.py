from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, computed_field

from app.models.audit import AuditAction, AuditResult
from app.schemas.common import ORMModel
from app.schemas.user import UserRead


class AuditEventRead(ORMModel):
    id: uuid.UUID
    action: AuditAction
    result: AuditResult
    entity_type: str
    entity_id: str | None = None
    case_id: uuid.UUID | None = None
    timestamp: datetime
    actor: UserRead | None = None
    event_metadata: dict[str, Any] = Field(default_factory=dict, alias="event_metadata")
    previous_event_hash: str
    event_hash: str

    @computed_field  # type: ignore[prop-decorator]
    @property
    def event_hash_short(self) -> str:
        return self.event_hash[:16]


class ChainVerificationReport(BaseModel):
    intact: bool
    events_checked: int
    head_hash: str | None = None
    broken_at_index: int | None = None
    broken_event_id: str | None = None
    detail: str
