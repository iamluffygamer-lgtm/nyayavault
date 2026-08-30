from __future__ import annotations

import uuid
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, uuid_pk

if TYPE_CHECKING:
    from app.models.user import User


class RoleName(StrEnum):
    """Canonical role identifiers.

    Roles live in a database table (so descriptions can be edited and further
    roles added), but these constants are what the authorisation layer compares
    against, so a typo in a policy check fails fast rather than silently.
    """

    ADMIN = "ADMIN"
    INVESTIGATOR = "INVESTIGATOR"
    FORENSIC_OFFICER = "FORENSIC_OFFICER"
    LEGAL_OFFICER = "LEGAL_OFFICER"
    AUDITOR = "AUDITOR"


ROLE_DESCRIPTIONS: dict[RoleName, str] = {
    RoleName.ADMIN: "Full administrative control: user management and system-wide visibility.",
    RoleName.INVESTIGATOR: "Opens and works cases; uploads investigation documents and evidence.",
    RoleName.FORENSIC_OFFICER: "Uploads and verifies forensic reports on assigned cases.",
    RoleName.LEGAL_OFFICER: "Prepares legal filings and reviews documents on assigned cases.",
    RoleName.AUDITOR: "Read-only oversight across all cases, including the full audit trail.",
}


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(512))

    users: Mapped[list["User"]] = relationship(back_populates="role")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Role {self.name}>"
