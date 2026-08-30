from __future__ import annotations

import sqlalchemy

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, utcnow, uuid_pk

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.user import User


class DocumentType(StrEnum):
    FIR = "FIR"
    CHARGE_SHEET = "CHARGE_SHEET"
    WITNESS_STATEMENT = "WITNESS_STATEMENT"
    FORENSIC_REPORT = "FORENSIC_REPORT"
    SEIZURE_MEMO = "SEIZURE_MEMO"
    COURT_ORDER = "COURT_ORDER"
    LEGAL_NOTICE = "LEGAL_NOTICE"
    EVIDENCE_PHOTO = "EVIDENCE_PHOTO"
    OTHER = "OTHER"


class Document(Base, TimestampMixin):
    """A logical document within a case.

    The document row carries identity and metadata. Bytes always live on a
    DocumentVersion — there is no "current file" column, only a pointer to the
    current version number, so history can never be silently lost.
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[DocumentType] = mapped_column(
        SAEnum(DocumentType, native_enum=False, length=32, validate_strings=True),
        default=DocumentType.OTHER,
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text)

    current_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    case: Mapped["Case"] = relationship(back_populates="documents")
    creator: Mapped["User"] = relationship(lazy="joined", foreign_keys=[created_by])
    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentVersion.version_number",
    )

    def latest_version(self) -> "DocumentVersion | None":
        return max(self.versions, key=lambda v: v.version_number, default=None)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Document {self.title} v{self.current_version}>"


class DocumentVersion(Base):
    """One immutable revision of a document.

    Rows in this table are append-only by design:

    * `(document_id, version_number)` is unique, so v1 can never be written twice.
    * `object_key` is unique, so two versions can never point at the same object.
    * The service layer never issues UPDATE or DELETE against this table.

    `sha256_hash` is computed from the uploaded bytes *before* they reach the
    object store, which is what makes later verification meaningful.
    """

    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_document_version"),
        UniqueConstraint("object_key", name="uq_document_version_object_key"),
        CheckConstraint("version_number >= 1", name="version_number_positive"),
        CheckConstraint("file_size >= 0", name="file_size_non_negative"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Server-generated storage path. Never influenced by client input.
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)

    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Lowercase hex SHA-256 of the stored bytes (64 characters).
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    change_reason: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    document: Mapped["Document"] = relationship(back_populates="versions")
    uploader: Mapped["User"] = relationship(lazy="joined", foreign_keys=[uploaded_by])
    text: Mapped["DocumentText | None"] = relationship(back_populates="version")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DocumentVersion {self.document_id} v{self.version_number}>"

class ExtractionMethod(StrEnum):
    NATIVE_TEXT = "NATIVE_TEXT"
    OCR = "OCR"


class ExtractionStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    NOT_REQUIRED = "NOT_REQUIRED"


class DocumentText(Base, TimestampMixin):
    """Extracted text and search vector for a document version.
    
    This is derived data. The original document is never modified.
    """

    __tablename__ = "document_text"

    id: Mapped[uuid.UUID] = uuid_pk()
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    version: Mapped["DocumentVersion"] = relationship(back_populates="text")

    extracted_text: Mapped[str | None] = mapped_column(Text)
    
    # The TSVector is generated natively by Postgres (via migration).
    # In SQLite (used by tests), we use Text.
    search_vector = mapped_column(
        sqlalchemy.dialects.postgresql.TSVECTOR().with_variant(sqlalchemy.Text(), "sqlite"),
        server_default=sqlalchemy.FetchedValue(),
    )

    extraction_method: Mapped[ExtractionMethod | None] = mapped_column(
        SAEnum(ExtractionMethod, native_enum=False, length=32, validate_strings=True)
    )
    language: Mapped[str | None] = mapped_column(String(16))
    extraction_status: Mapped[ExtractionStatus] = mapped_column(
        SAEnum(ExtractionStatus, native_enum=False, length=32, validate_strings=True),
        default=ExtractionStatus.PENDING,
        nullable=False,
    )

