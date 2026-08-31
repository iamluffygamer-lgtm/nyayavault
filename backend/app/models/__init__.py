"""SQLAlchemy models.

Importing every model here guarantees the mappers are configured and that
Alembic's autogenerate sees the complete metadata.
"""

from app.models.audit import (
    GENESIS_HASH,
    AuditAction,
    AuditEvent,
    AuditResult,
)
from app.models.base import Base
from app.models.case import (
    MUTABLE_CASE_STATUSES,
    Case,
    CaseAccessLevel,
    CaseAssignment,
    CaseStatus,
)
from app.models.department import Department
from app.models.document import Document, DocumentType, DocumentVersion, DocumentText, ExtractionMethod, ExtractionStatus
from app.models.permission import Permission, PermissionName, RolePermission
from app.models.role import ROLE_DESCRIPTIONS, Role, RoleName
from app.models.user import User
from app.models.evidence import Evidence, EvidenceTransfer, EvidenceStatus, TransferStatus

__all__ = [
    "Base",
    "Role",
    "RoleName",
    "Permission",
    "PermissionName",
    "RolePermission",
    "ROLE_DESCRIPTIONS",
    "Department",
    "User",
    "Case",
    "CaseStatus",
    "CaseAssignment",
    "CaseAccessLevel",
    "MUTABLE_CASE_STATUSES",
    "Document",
    "DocumentType",
    "DocumentVersion, DocumentText, ExtractionMethod, ExtractionStatus",
    "AuditEvent",
    "AuditAction",
    "AuditResult",
    "GENESIS_HASH",
    "Evidence",
    "EvidenceTransfer",
    "EvidenceStatus",
    "TransferStatus",
]
