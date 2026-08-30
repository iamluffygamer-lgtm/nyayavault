from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, uuid_pk

if TYPE_CHECKING:
    from app.models.user import User


class Department(Base):
    """Organisational unit a user belongs to (e.g. Cyber Crime Cell, FSL)."""

    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(512))

    users: Mapped[list["User"]] = relationship(back_populates="department")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Department {self.name}>"
