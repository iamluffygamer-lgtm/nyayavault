import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import ForeignKey, String, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow, uuid_pk


class CourtAccessStatus(StrEnum):
    ACTIVE = "ACTIVE"
    REDEEMED = "REDEEMED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class CourtAccessGrant(Base):
    __tablename__ = "court_access_grants"

    id: Mapped[uuid.UUID] = uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id"), index=True, nullable=False)
    
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    reference: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    
    status: Mapped[CourtAccessStatus] = mapped_column(
        SAEnum(CourtAccessStatus, native_enum=False, length=32),
        nullable=False,
        default=CourtAccessStatus.ACTIVE
    )
    
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    session_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
