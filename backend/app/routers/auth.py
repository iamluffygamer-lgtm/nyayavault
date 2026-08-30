from __future__ import annotations

from fastapi import APIRouter, status

from app.dependencies import CurrentUser, DbSession
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserRead
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Exchange credentials for an access token",
    responses={401: {"description": "Invalid credentials"}},
)
def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    """Authenticate a user.

    Every attempt, successful or not, is written to the audit chain. Failures
    return one generic message so the endpoint cannot be used to enumerate
    valid usernames.
    """
    token, expires_in, user = auth_service.authenticate(
        db, username=payload.username, password=payload.password
    )
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserRead.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserRead,
    summary="Current user, resolved from the database",
)
def read_me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)
