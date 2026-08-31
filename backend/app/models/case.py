from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, utcnow, uuid_pk

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.user import User
    from app.models.department import Department


class CaseStatus(StrEnum):
    OPEN = "OPEN"
    UNDER_INVESTIGATION = "UNDER_INVESTIGATION"
    SUBMITTED = "SUBMITTED"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


# Statuses in which new documents may still be added. Closed and archived cases
# are read-only; this is enforced server-side in the document service.
MUTABLE_CASE_STATUSES = frozenset(
    {CaseStatus.OPEN, CaseStatus.UNDER_INVESTIGATION, CaseStatus.SUBMITTED}
)


class CaseAccessLevel(StrEnum):
    """What an explicitly assigned member may do on a case."""

    READ = "READ"
    CONTRIBUTE = "CONTRIBUTE"  # read + upload documents
    MANAGE = "MANAGE"  # contribute + assign other members, change status


class Case(Base, TimestampMixin):
    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = uuid_pk()

    # Human-facing identifier, e.g. "NV-2026-000042". Generated server-side;
    # unique so two officers cannot register the same case reference.
    case_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)

    department_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True, index=True)
    department: Mapped["Department | None"] = relationship(lazy="joined")

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    status: Mapped[CaseStatus] = mapped_column(
        # native_enum=False stores a VARCHAR guarded by a CHECK constraint. This
        # keeps the schema portable and avoids painful ALTER TYPE migrations
        # when a new status is added later.
        SAEnum(CaseStatus, native_enum=False, length=32, validate_strings=True),
        default=CaseStatus.OPEN,
        nullable=False,
        index=True,
    )

    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    creator: Mapped["User"] = relationship(lazy="joined", foreign_keys=[created_by])
    documents: Mapped[list["Document"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    assignments: Mapped[list["CaseAssignment"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Case {self.case_number}>"


class CaseAssignment(Base):
    """Case-level access control.

    Beyond the six entities in the M0 brief, but the problem statement calls for
    *case-level* access control and role alone cannot express "this investigator
    may see this case". Keeping it as a thin join table now avoids reworking
    every authorisation call site in a later milestone.
    """

    __tablename__ = "case_assignments"
    __table_args__ = (UniqueConstraint("case_id", "user_id", name="uq_case_assignment"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    access_level: Mapped[CaseAccessLevel] = mapped_column(
        SAEnum(CaseAccessLevel, native_enum=False, length=16, validate_strings=True),
        default=CaseAccessLevel.CONTRIBUTE,
        nullable=False,
    )
    assigned_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    case: Mapped["Case"] = relationship(back_populates="assignments")
    user: Mapped["User"] = relationship(lazy="joined", foreign_keys=[user_id])
