import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.dependencies import DbSession
from app.models.department import Department
from app.services.authorization import AuthorizationService, PermissionName
from app.dependencies import CurrentUser
from app.models.department import OrgType
from app.schemas.user import DepartmentUpdate


router = APIRouter(tags=["departments"])

class DepartmentBase(BaseModel):
    name: str = Field(..., max_length=128)
    description: str | None = Field(None, max_length=512)
    org_type: OrgType = OrgType.OTHER
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

@router.patch("/{department_id}", response_model=DepartmentRead)
def update_department(
    department_id: uuid.UUID,
    payload: DepartmentUpdate,
    db: DbSession,
    user: CurrentUser,
):
    from app.schemas.user import DepartmentUpdate
    from app.errors import NotFoundError, ValidationError
    
    AuthorizationService(db).require(user, PermissionName.USER_MANAGE)
    
    dept = db.get(Department, department_id)
    if not dept:
        raise NotFoundError("Department not found")
    
    # We will just parse the payload manually or we can import DepartmentUpdate
    update_data = payload
    
    if update_data.name is not None:
        if db.execute(select(Department).where(Department.name == update_data.name, Department.id != department_id)).scalar_one_or_none():
            raise ValidationError("Department name already exists")
        dept.name = update_data.name
        
    if update_data.description is not None:
        dept.description = update_data.description
        
    if update_data.parent_id is not None:
        if update_data.parent_id != dept.parent_id:
            parent = db.get(Department, update_data.parent_id)
            if not parent:
                raise NotFoundError("Parent department not found")
            # Only update parent_id, path trigger handles this node
            dept.parent_id = update_data.parent_id
            
    db.commit()
    db.refresh(dept)
    
    # Audit log
    from app.services.audit_service import record_event
    from app.models.audit import AuditAction
    record_event(
        db,
        action=AuditAction.DEPARTMENT_MODIFIED,
        entity_type="department",
        entity_id=str(dept.id),
        actor_id=user.id,
        metadata={"name": dept.name, "parent_id": str(dept.parent_id) if dept.parent_id else None}
    )
    db.commit()
    
    return dept
