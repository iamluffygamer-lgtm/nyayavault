from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, utcnow, uuid_pk

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.document import Document
    from app.models.user import User


class EvidenceStatus(StrEnum):
    COLLECTED = "COLLECTED"
    REGISTERED = "REGISTERED"
    SEALED = "SEALED"
    IN_CUSTODY = "IN_CUSTODY"
    TRANSFER_PENDING = "TRANSFER_PENDING"
    UNDER_ANALYSIS = "UNDER_ANALYSIS"
    ANALYZED = "ANALYZED"
    COURT_SUBMITTED = "COURT_SUBMITTED"
    ARCHIVED = "ARCHIVED"


class TransferStatus(StrEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"


class Evidence(Base, TimestampMixin):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )

    evidence_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    status: Mapped[EvidenceStatus] = mapped_column(
        SAEnum(EvidenceStatus, native_enum=False, length=32, validate_strings=True),
        default=EvidenceStatus.REGISTERED,
        nullable=False,
        index=True,
    )

    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collected_location: Mapped[str | None] = mapped_column(String(255))
    
    collected_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    current_custodian: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), index=True
    )
    sha256_hash: Mapped[str | None] = mapped_column(String(64))

    case: Mapped["Case"] = relationship(lazy="joined", foreign_keys=[case_id])
    collector: Mapped["User | None"] = relationship(lazy="joined", foreign_keys=[collected_by])
    custodian: Mapped["User | None"] = relationship(lazy="joined", foreign_keys=[current_custodian])
    source_document: Mapped["Document | None"] = relationship(lazy="joined", foreign_keys=[source_document_id])

    transfers: Mapped[list["EvidenceTransfer"]] = relationship(
        back_populates="evidence", cascade="all, delete-orphan", order_by="EvidenceTransfer.created_at"
    )

    __table_args__ = (
        UniqueConstraint("case_id", "evidence_number", name="uq_evidence_case_number"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Evidence {self.evidence_number} - {self.status}>"


class EvidenceTransfer(Base):
    __tablename__ = "evidence_transfers"

    id: Mapped[uuid.UUID] = uuid_pk()
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True
    )

    from_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    to_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    transferred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    
    reason: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255))

    status: Mapped[TransferStatus] = mapped_column(
        SAEnum(TransferStatus, native_enum=False, length=32, validate_strings=True),
        default=TransferStatus.PENDING,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    evidence: Mapped["Evidence"] = relationship(back_populates="transfers")
    from_user: Mapped["User"] = relationship(lazy="joined", foreign_keys=[from_user_id])
    to_user: Mapped["User"] = relationship(lazy="joined", foreign_keys=[to_user_id])

    def __repr__(self) -> str:  # pragma: no cover
        return f"<EvidenceTransfer {self.id} - {self.status}>"
