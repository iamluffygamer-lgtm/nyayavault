from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import NotFoundError, PermissionDeniedError
from app.models.case import (
    MUTABLE_CASE_STATUSES,
    Case,
    CaseAccessLevel,
    CaseAssignment,
    CaseStatus,
)
from app.models.permission import PermissionName
from app.models.role import RoleName
from app.models.user import User

_LEVEL_RANK = {
    CaseAccessLevel.READ: 1,
    CaseAccessLevel.CONTRIBUTE: 2,
    CaseAccessLevel.MANAGE: 3,
}

@dataclass(frozen=True)
class CaseAccess:
    """Resolved access of one user to one case."""
    case: Case
    level: CaseAccessLevel
    via: str  # "role" | "creator" | "assignment"

    @property
    def can_read(self) -> bool:
        return True

    @property
    def can_contribute(self) -> bool:
        return _LEVEL_RANK[self.level] >= _LEVEL_RANK[CaseAccessLevel.CONTRIBUTE]

    @property
    def can_manage(self) -> bool:
        return _LEVEL_RANK[self.level] >= _LEVEL_RANK[CaseAccessLevel.MANAGE]

class AuthorizationService:
    def __init__(self, db: Session):
        self.db = db

    def require(self, user: User, action: PermissionName, resource: Any = None) -> Any:
        """
        Public API for authorization.
        Fails closed by raising PermissionDeniedError or NotFoundError.
        Returns the resolved resource (e.g., CaseAccess) if applicable.
        """
        has_perm, case_access = self._can(user, action, resource)
        
        if not has_perm:
            # If the resource is a Case and the user has absolutely no access, they get a 404
            # to avoid leaking existence.
            if isinstance(resource, Case):
                access = self._resolve_case_access(user, resource)
                if access is None:
                    raise NotFoundError("Case not found.")
            
            raise PermissionDeniedError(f"You do not have permission to {action}.")
            
        return case_access

    def _can(self, user: User, action: PermissionName, resource: Any = None) -> tuple[bool, Any]:
        """
        Private logic for determining if an action is allowed.
        Returns (is_allowed, contextual_data)
        """
        # 1. Does the user have the permission?
        user_permissions = {p.name for p in user.role.permissions} if getattr(user.role, 'permissions', None) else set()
        
        # Temporary fallback for development if permissions are not seeded
        if action not in user_permissions:
            # Check if this user is ADMIN. During M3a migration, admins can bypass just in case.
            if user.role_name != RoleName.ADMIN.value:
                return False, None
            # Otherwise we'd strictly return False

        if resource is None:
            return True, None

        if isinstance(resource, Case):
            access = self._resolve_case_access(user, resource)
            if access is None:
                return False, None

            # Interpret action requirements
            if action in {PermissionName.CASE_UPDATE, PermissionName.DOCUMENT_UPLOAD, PermissionName.EVIDENCE_CREATE, PermissionName.EVIDENCE_TRANSFER, PermissionName.EVIDENCE_SEAL, PermissionName.EVIDENCE_ANALYZE, PermissionName.EVIDENCE_SUBMIT}:
                if not access.can_contribute:
                    return False, access
                if resource.status not in MUTABLE_CASE_STATUSES:
                    return False, access

            return True, access

        return False, None

    def _resolve_case_access(self, user: User, case: Case) -> CaseAccess | None:
        """Return the user's access to a case, or None if they have none."""
        if user.role_name == RoleName.ADMIN:
            return CaseAccess(case=case, level=CaseAccessLevel.MANAGE, via="role")
        if case.created_by == user.id:
            return CaseAccess(case=case, level=CaseAccessLevel.MANAGE, via="creator")

        assignment = self.db.execute(
            select(CaseAssignment).where(
                CaseAssignment.case_id == case.id, CaseAssignment.user_id == user.id
            )
        ).scalar_one_or_none()
        
        if assignment is not None:
            return CaseAccess(case=case, level=assignment.access_level, via="assignment")

        user_permissions = {p.name for p in user.role.permissions} if getattr(user.role, 'permissions', None) else set()
        if PermissionName.CASE_VIEW in user_permissions and user.department and case.department:
            if case.department.path.startswith(user.department.path):
                return CaseAccess(case=case, level=CaseAccessLevel.READ, via="scope")

        return None


# Helpers for easy injection and backwards compatibility in M3a migration
def get_authz(db: Session) -> AuthorizationService:
    return AuthorizationService(db)

def get_case_for_user(
    db: Session,
    user: User,
    case_id: uuid.UUID,
    *,
    require_write: bool = False,
) -> CaseAccess:
    """Wrapper transitioning to AuthorizationService"""
    case = db.get(Case, case_id)
    if case is None:
        raise NotFoundError("Case not found.")

    action = PermissionName.CASE_UPDATE if require_write else PermissionName.CASE_VIEW
    return AuthorizationService(db).require(user, action, case)

def assert_case_status_transition(current: CaseStatus, target: CaseStatus) -> None:
    if current == CaseStatus.ARCHIVED and target != CaseStatus.ARCHIVED:
        raise PermissionDeniedError("An archived case cannot be reopened.")

def get_authorized_cases_query(user: User) -> select:
    """Return a SQLAlchemy Select statement yielding authorized case IDs."""
    from app.models.case import Case, CaseAssignment
    from app.models.department import Department
    from sqlalchemy import or_

    if user.role_name == RoleName.ADMIN:
        return select(Case.id)
        
    user_permissions = {p.name for p in user.role.permissions} if getattr(user.role, 'permissions', None) else set()
    has_global_view = PermissionName.CASE_VIEW in user_permissions
    
    conds = [
        Case.created_by == user.id,
        CaseAssignment.user_id == user.id
    ]
    
    if has_global_view and user.department:
        # User can view cases within their organizational scope
        conds.append(Department.path.startswith(user.department.path))
    
    return select(Case.id).distinct().outerjoin(
        CaseAssignment, CaseAssignment.case_id == Case.id
    ).outerjoin(
        Department, Case.department_id == Department.id
    ).where(
        or_(*conds)
    )
