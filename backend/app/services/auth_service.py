"""Authentication and user provisioning."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import AuthenticationError, ConflictError, NotFoundError, ValidationError
from app.models.audit import AuditAction, AuditResult
from app.models.department import Department
from app.models.role import Role
from app.models.user import User
from app.security import (
    PasswordPolicyError,
    create_access_token,
    hash_password,
    verify_password,
)
from app.services import audit_service

logger = logging.getLogger(__name__)

# A bcrypt hash of a value nobody can supply. Verified against when the username
# does not exist so that a failed login takes the same time whether or not the
# account is real, closing a username-enumeration timing side channel.
_DUMMY_HASH = hash_password("nyayavault-timing-equaliser-" + uuid.uuid4().hex)


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.execute(
        select(User).where(func.lower(User.username) == username.strip().lower())
    ).scalar_one_or_none()


def authenticate(db: Session, *, username: str, password: str) -> tuple[str, int, User]:
    """Verify credentials and issue an access token.

    Every outcome is audited. Failures return one generic message so the caller
    cannot distinguish "no such user" from "wrong password" from "deactivated".
    """
    user = get_user_by_username(db, username)

    if user is None:
        verify_password(password, _DUMMY_HASH)  # constant-time equaliser
        audit_service.record_event(
            db,
            action=AuditAction.LOGIN_FAILED,
            entity_type="user",
            result=AuditResult.FAILURE,
            metadata={"username_attempted": username[:64], "reason": "unknown_user"},
        )
        db.commit()
        raise AuthenticationError("Invalid username or password.")

    if not verify_password(password, user.password_hash):
        audit_service.record_event(
            db,
            action=AuditAction.LOGIN_FAILED,
            entity_type="user",
            entity_id=user.id,
            actor_id=user.id,
            result=AuditResult.FAILURE,
            metadata={"reason": "bad_password"},
        )
        db.commit()
        raise AuthenticationError("Invalid username or password.")

    if not user.is_active:
        audit_service.record_event(
            db,
            action=AuditAction.LOGIN_FAILED,
            entity_type="user",
            entity_id=user.id,
            actor_id=user.id,
            result=AuditResult.DENIED,
            metadata={"reason": "account_inactive"},
        )
        db.commit()
        raise AuthenticationError("Invalid username or password.")

    token, expires_in = create_access_token(subject=str(user.id), role=user.role_name)

    audit_service.record_event(
        db,
        action=AuditAction.LOGIN_SUCCEEDED,
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        metadata={"role": user.role_name},
    )
    db.commit()
    return token, expires_in, user


def create_user(
    db: Session,
    *,
    username: str,
    email: str,
    password: str,
    role_id: uuid.UUID,
    department_id: uuid.UUID | None,
    full_name: str | None,
    actor: User,
) -> User:
    username = username.strip()
    email = email.strip().lower()

    try:
        from app.security import validate_password_policy

        validate_password_policy(password)
    except PasswordPolicyError as exc:
        raise ValidationError(str(exc)) from exc

    if get_user_by_username(db, username) is not None:
        raise ConflictError("That username is already registered.")
    if db.execute(select(User).where(func.lower(User.email) == email)).scalar_one_or_none():
        raise ConflictError("That email address is already registered.")

    role = db.get(Role, role_id)
    if role is None:
        raise NotFoundError("Role not found.")
    if department_id is not None and db.get(Department, department_id) is None:
        raise NotFoundError("Department not found.")

    user = User(
        username=username,
        email=email,
        full_name=full_name,
        password_hash=hash_password(password),
        role_id=role.id,
        department_id=department_id,
        is_active=True,
    )
    db.add(user)
    db.flush()

    audit_service.record_event(
        db,
        action=AuditAction.USER_CREATED,
        entity_type="user",
        entity_id=user.id,
        actor_id=actor.id,
        metadata={"username": user.username, "role": role.name},
    )
    db.commit()
    db.refresh(user)
    return user
