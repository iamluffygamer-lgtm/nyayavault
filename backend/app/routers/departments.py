import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.dependencies import DbSession
from app.models.department import Department
from app.services.authorization import AuthorizationService, PermissionName
from app.dependencies import CurrentUser

router = APIRouter(tags=["departments"])

class DepartmentBase(BaseModel):
    name: str = Field(..., max_length=128)
    description: str | None = Field(None, max_length=512)
    org_type: str = Field(..., max_length=32)
    parent_id: uuid.UUID | None = None

class DepartmentRead(DepartmentBase):
    id: uuid.UUID
    path: str

    class Config:
        from_attributes = True

@router.post("", response_model=DepartmentRead, status_code=201)
def create_department(
    payload: DepartmentBase,
    db: DbSession,
    user: CurrentUser,
):
    AuthorizationService(db).require(user, PermissionName.USER_MANAGE)
    
    if payload.parent_id:
        parent = db.get(Department, payload.parent_id)
        if not parent:
            from app.errors import NotFoundError
            raise NotFoundError("Parent department not found")
            
    # Check name collision
    if db.execute(select(Department).where(Department.name == payload.name)).scalar_one_or_none():
        from app.errors import ValidationError
        raise ValidationError("Department name already exists")
        
    dept = Department(
        name=payload.name,
        description=payload.description,
        org_type=payload.org_type,
        parent_id=payload.parent_id
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept

@router.get("", response_model=list[DepartmentRead])
def list_departments(
    db: DbSession,
    user: CurrentUser,
):
    # Anyone authenticated can view the hierarchy to pick departments
    return db.execute(select(Department).order_by(Department.path)).scalars().all()
