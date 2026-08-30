from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import ORMModel

USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{3,64}$")


class RoleRead(ORMModel):
    id: uuid.UUID
    name: str
    description: str | None = None


class DepartmentRead(ORMModel):
    id: uuid.UUID
    name: str
    description: str | None = None


class UserRead(ORMModel):
    id: uuid.UUID
    username: str
    email: EmailStr
    full_name: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    role: RoleRead
    department: DepartmentRead | None = None


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    full_name: str | None = Field(None, max_length=160)
    # Never echoed back in any response schema.
    password: str = Field(..., min_length=12, max_length=256)
    role_id: uuid.UUID
    department_id: uuid.UUID | None = None

    @field_validator("username")
    @classmethod
    def _username_shape(cls, v: str) -> str:
        v = v.strip()
        if not USERNAME_PATTERN.match(v):
            raise ValueError(
                "Username may contain only letters, digits, dot, underscore and hyphen."
            )
        return v
