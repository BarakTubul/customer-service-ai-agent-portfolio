from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import get_auth_service, get_current_guest_user
from app.core.settings import get_settings
from app.models.user import User
from app.schemas.auth import (
    GuestConvertRequest,
    GuestResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth")


def _set_auth_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        max_age=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/guest", response_model=GuestResponse, status_code=status.HTTP_201_CREATED)
def create_guest_session(
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> GuestResponse:
    guest = auth_service.create_guest()
    _set_auth_cookie(response, guest.access_token)
    return guest


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    token = auth_service.register(email=str(payload.email), password=payload.password)
    _set_auth_cookie(response, token.access_token)
    return token


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    token = auth_service.login(email=str(payload.email), password=payload.password)
    _set_auth_cookie(response, token.access_token)
    return token


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    settings = get_settings()
    response.delete_cookie(
        key=settings.auth_cookie_name,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
    )
    return response


@router.post("/guest/convert", response_model=TokenResponse)
def convert_guest(
    payload: GuestConvertRequest,
    response: Response,
    guest_user: User = Depends(get_current_guest_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    token = auth_service.convert_guest_to_registered(
        guest_user=guest_user,
        email=str(payload.email),
        password=payload.password,
    )
    _set_auth_cookie(response, token.access_token)
    return token
