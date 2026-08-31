from __future__ import annotations

import uuid
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, uuid_pk

if TYPE_CHECKING:
    from app.models.role import Role


class PermissionName(StrEnum):
    """Granular permissions for the M3 authorization engine."""
    CASE_VIEW = "CASE_VIEW"
    CASE_CREATE = "CASE_CREATE"
    CASE_UPDATE = "CASE_UPDATE"
    DOCUMENT_VIEW = "DOCUMENT_VIEW"
    DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD"
    EVIDENCE_VIEW = "EVIDENCE_VIEW"
    EVIDENCE_CREATE = "EVIDENCE_CREATE"
    EVIDENCE_TRANSFER = "EVIDENCE_TRANSFER"
    EVIDENCE_ANALYZE = "EVIDENCE_ANALYZE"
    EVIDENCE_SEAL = "EVIDENCE_SEAL"
    EVIDENCE_SUBMIT = "EVIDENCE_SUBMIT"
    EVIDENCE_ARCHIVE = "EVIDENCE_ARCHIVE"
    AUDIT_VIEW = "AUDIT_VIEW"
    USER_MANAGE = "USER_MANAGE"


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(512))

    roles: Mapped[list["Role"]] = relationship(
        secondary="role_permissions", back_populates="permissions"
    )

    def __repr__(self) -> str:
        return f"<Permission {self.name}>"


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False, index=True)
