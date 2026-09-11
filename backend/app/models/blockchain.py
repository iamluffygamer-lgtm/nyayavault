from datetime import datetime
import uuid

from sqlalchemy import ForeignKey, String, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from enum import StrEnum

from app.models.base import Base
from app.models.base import TimestampMixin


class AnchorStatus(StrEnum):
    PENDING = "PENDING"
    ANCHORED = "ANCHORED"
    FAILED = "FAILED"


class BlockchainAnchor(Base, TimestampMixin):
    __tablename__ = "blockchain_anchors"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_versions.id", ondelete="CASCADE"), unique=True)
    anchored_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[AnchorStatus] = mapped_column(Enum(AnchorStatus), default=AnchorStatus.PENDING, nullable=False)
    tx_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    block_number: Mapped[int | None] = mapped_column(nullable=True)
    contract_address: Mapped[str | None] = mapped_column(String(42), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    document_version = relationship("DocumentVersion", back_populates="blockchain_anchor")
