"""FastAPI dependencies: authentication and role gates.

The critical rule lives here: `get_current_user` resolves the token's subject
against the `users` table on every single request and returns the *database*
role. No handler ever reads a role from the request body, a header or the JWT
claim set.
"""

# NOTE: `from __future__ import annotations` is deliberately NOT used in this
# module. FastAPI resolves the signature of a callable *instance* (RequireRoles)
# without access to the defining module's globals, so a stringified annotation
# such as "CurrentUser" cannot be resolved and the parameter would silently be
# treated as a query parameter instead of a dependency.

import uuid
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import AuthenticationError, PermissionDeniedError
from app.models.role import RoleName
from app.models.user import User
from app.security import decode_access_token, decode_court_token
from app.models.court_access import CourtAccessGrant, CourtAccessStatus
from datetime import datetime, timezone
from app.storage import ObjectStorage, get_storage

# auto_error=False so a missing header raises our own JSON error shape rather
# than Starlette's default.
_bearer = HTTPBearer(auto_error=False, description="JWT access token")

DbSession = Annotated[Session, Depends(get_db)]
Storage = Annotated[ObjectStorage, Depends(get_storage)]


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: DbSession,
) -> User:
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Authentication required.")

    claims = decode_access_token(credentials.credentials)
    if claims is None:
        raise AuthenticationError("Invalid or expired token.")

    try:
        user_id = uuid.UUID(str(claims.get("sub")))
    except (ValueError, TypeError):
        raise AuthenticationError("Invalid token subject.") from None

    user = db.get(User, user_id)
    if user is None:
        raise AuthenticationError("Invalid or expired token.")
    if not user.is_active:
        # Deactivation takes effect immediately, even for tokens issued earlier.
        raise AuthenticationError("This account has been deactivated.")

    request.state.user_id = str(user.id)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


class RequireRoles:
    """Dependency factory gating an endpoint on the caller's database role."""

    def __init__(self, *roles: RoleName, action: str = "perform this action") -> None:
        self._allowed = {str(r) for r in roles}
        self._action = action

    def __call__(self, user: CurrentUser) -> User:
        if user.role_name not in self._allowed:
            raise PermissionDeniedError(f"Your role ({user.role_name}) may not {self._action}.")
        return user


require_admin = RequireRoles(RoleName.ADMIN, action="manage users")


def get_court_access_grant(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: DbSession,
) -> CourtAccessGrant:
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Authentication required.")

    claims = decode_court_token(credentials.credentials)
    if claims is None:
        raise AuthenticationError("Invalid or expired court token.")

    try:
        grant_id = uuid.UUID(str(claims.get("sub")))
        case_id = uuid.UUID(str(claims.get("case_id")))
    except (ValueError, TypeError):
        raise AuthenticationError("Invalid token format.") from None

    grant = db.get(CourtAccessGrant, grant_id)
    if grant is None:
        raise AuthenticationError("Invalid court grant.")
    
    if grant.status != CourtAccessStatus.REDEEMED:
        raise AuthenticationError("Court grant is no longer active.")
        
    now = datetime.now(timezone.utc)
    if grant.session_expires_at is None or grant.session_expires_at < now:
        raise AuthenticationError("Court session has expired.")
        
    if str(grant.case_id) != str(case_id):
        raise AuthenticationError("Court grant scope mismatch.")
        
    return grant

CourtGrant = Annotated[CourtAccessGrant, Depends(get_court_access_grant)]
