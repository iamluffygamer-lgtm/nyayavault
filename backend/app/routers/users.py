from __future__ import annotations
from app.models.permission import PermissionName

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select

from app.dependencies import CurrentUser, DbSession, require_admin
from app.models.department import Department
from app.models.role import Role
from app.models.user import User
from app.schemas.common import Page
from app.schemas.user import DepartmentRead, RoleRead, UserCreate, UserRead, UserUpdate
from app.services import auth_service

router = APIRouter(tags=["Users"])

AdminUser = Annotated[User, Depends(require_admin)]


@router.get(
    "/users",
    response_model=Page[UserRead],
    summary="List users (ADMIN only)",
)
def list_users(
    db: DbSession,
    _admin: AdminUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[UserRead]:
    total = db.execute(select(func.count()).select_from(User)).scalar_one()
    rows = (
        db.execute(select(User).order_by(User.created_at.desc()).offset(offset).limit(limit))
        .scalars()
        .all()
    )
    return Page(
        items=[UserRead.model_validate(u) for u in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user (ADMIN only)",
)
def create_user(payload: UserCreate, db: DbSession, admin: AdminUser) -> UserRead:
    """Provision an account.

    The role is taken from `role_id` in the body, but only an authenticated
    ADMIN reaches this handler — a user can never choose their own role at
    sign-up because there is no self-service sign-up.
    """
    user = auth_service.create_user(
        db,
        username=payload.username,
        email=payload.email,
        password=payload.password,
        role_id=payload.role_id,
        department_id=payload.department_id,
        full_name=payload.full_name,
        actor=admin,
    )
    return UserRead.model_validate(user)


@router.get("/roles", response_model=list[RoleRead], summary="List roles")
def list_roles(db: DbSession, _user: CurrentUser) -> list[RoleRead]:
    rows = db.execute(select(Role).order_by(Role.name)).scalars().all()
    return [RoleRead.model_validate(r) for r in rows]



@router.patch(
    "/users/{user_id}",
    response_model=UserRead,
    summary="Update user (ADMIN only)",
)
def update_user(
    user_id: str,
    payload: UserUpdate,
    db: DbSession,
    user: CurrentUser, # Use AuthorizationService
):
    from app.schemas.user import UserUpdate
    from app.errors import NotFoundError, ValidationError
    import uuid
    from app.services.authorization import AuthorizationService, PermissionName
    
    AuthorizationService(db).require(user, PermissionName.USER_MANAGE)
    
    uid = uuid.UUID(user_id)
    target_user = db.get(User, uid)
    if not target_user:
        raise NotFoundError("User not found")
        
    update_data = payload
    
    # Track what changed for audit
    changes = {}
    
    if update_data.is_active is not None and update_data.is_active != target_user.is_active:
        changes["is_active"] = {"old": target_user.is_active, "new": update_data.is_active}
        target_user.is_active = update_data.is_active
        
    if update_data.role_id is not None and update_data.role_id != target_user.role_id:
        role = db.get(Role, update_data.role_id)
        if not role:
            raise NotFoundError("Role not found")
        changes["role_id"] = {"old": str(target_user.role_id), "new": str(update_data.role_id)}
        target_user.role_id = update_data.role_id
        
    if update_data.department_id is not None and update_data.department_id != target_user.department_id:
        dept = db.get(Department, update_data.department_id)
        if not dept:
            raise NotFoundError("Department not found")
        changes["department_id"] = {"old": str(target_user.department_id) if target_user.department_id else None, "new": str(update_data.department_id)}
        target_user.department_id = update_data.department_id
        
    db.commit()
    db.refresh(target_user)
    
    if changes:
        from app.services.audit_service import record_event
        from app.models.audit import AuditAction
        record_event(
            db,
            action=AuditAction.USER_MODIFIED,
            entity_type="user",
            entity_id=str(target_user.id),
            actor_id=user.id,
            metadata={"changes": changes}
        )
        db.commit()
        
    return target_user
