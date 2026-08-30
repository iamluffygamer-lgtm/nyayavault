from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select

from app.dependencies import CurrentUser, DbSession, require_admin
from app.models.department import Department
from app.models.role import Role
from app.models.user import User
from app.schemas.common import Page
from app.schemas.user import DepartmentRead, RoleRead, UserCreate, UserRead
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


@router.get("/departments", response_model=list[DepartmentRead], summary="List departments")
def list_departments(db: DbSession, _user: CurrentUser) -> list[DepartmentRead]:
    rows = db.execute(select(Department).order_by(Department.name)).scalars().all()
    return [DepartmentRead.model_validate(d) for d in rows]
