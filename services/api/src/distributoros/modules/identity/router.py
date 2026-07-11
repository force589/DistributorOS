from typing import Annotated

from fastapi import APIRouter, Body, Cookie, Depends, Header, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.core.config import Settings, get_settings
from distributoros.core.database import get_session
from distributoros.core.errors import AppError
from distributoros.core.rate_limit import enforce_rate_limit
from distributoros.modules.identity.dependencies import Principal, get_current_principal
from distributoros.modules.identity.schemas import (
    AuthResponse,
    BusinessResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutResponse,
    MeResponse,
    MessageResponse,
    RefreshRequest,
    ResetPasswordRequest,
    SignupRequest,
    UserResponse,
)
from distributoros.modules.identity.service import AuthResult, AuthService, normalize_transport

router = APIRouter(prefix="/auth", tags=["Authentication"])
REFRESH_COOKIE_NAME = "distributoros_refresh"


def _client_identity(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _response_from_result(result: AuthResult) -> AuthResponse:
    return AuthResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        expires_in=result.expires_in,
        user=UserResponse(
            id=result.user.id,
            email=result.user.email,
            business=BusinessResponse(
                id=result.business.id,
                business_name=result.business.business_name,
                currency=result.business.currency,
                language=result.business.language,
                theme=result.business.theme,
                timezone=result.business.timezone,
            ),
        ),
    )


def _set_refresh_cookie(
    response: Response, token: str, settings: Settings, *, transport: str
) -> None:
    if transport != "cookie":
        return
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api/v1/auth",
    )


def _delete_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api/v1/auth",
    )


def _validate_cookie_origin(origin: str | None, settings: Settings, transport: str) -> None:
    if transport == "cookie" and origin is not None and origin not in settings.cors_origins:
        raise AppError(
            status_code=403,
            code="UNTRUSTED_ORIGIN",
            message=(
                "This sign-in request came from an untrusted website. "
                "Return to DistributorOS and try again."
            ),
        )


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    payload: SignupRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    client_platform: Annotated[str, Header(alias="X-Client-Platform")] = "native",
    origin: Annotated[str | None, Header()] = None,
) -> AuthResponse:
    await enforce_rate_limit(
        request,
        settings,
        scope="auth.signup",
        identity=_client_identity(request),
        limit=settings.signup_rate_limit,
        window_seconds=3600,
    )
    transport = normalize_transport(client_platform)
    _validate_cookie_origin(origin, settings, transport)
    result = await AuthService(session, settings).signup(payload, transport=transport)
    raw_refresh = result.refresh_cookie_token or result.refresh_token
    if raw_refresh:
        _set_refresh_cookie(response, raw_refresh, settings, transport=transport)
    return _response_from_result(result)


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    client_platform: Annotated[str, Header(alias="X-Client-Platform")] = "native",
    origin: Annotated[str | None, Header()] = None,
) -> AuthResponse:
    await enforce_rate_limit(
        request,
        settings,
        scope="auth.login",
        identity=f"{_client_identity(request)}:{str(payload.email).strip().lower()}",
        limit=settings.login_rate_limit,
        window_seconds=60,
    )
    transport = normalize_transport(client_platform)
    _validate_cookie_origin(origin, settings, transport)
    result = await AuthService(session, settings).login(payload, transport=transport)
    raw_refresh = result.refresh_cookie_token or result.refresh_token
    if raw_refresh:
        _set_refresh_cookie(response, raw_refresh, settings, transport=transport)
    return _response_from_result(result)


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    payload: Annotated[RefreshRequest | None, Body()] = None,
    refresh_cookie: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
    client_platform: Annotated[str, Header(alias="X-Client-Platform")] = "native",
    origin: Annotated[str | None, Header()] = None,
) -> AuthResponse:
    await enforce_rate_limit(
        request,
        settings,
        scope="auth.refresh",
        identity=_client_identity(request),
        limit=settings.refresh_rate_limit,
        window_seconds=60,
    )
    transport = normalize_transport(client_platform)
    _validate_cookie_origin(origin, settings, transport)
    raw_refresh = (
        refresh_cookie if transport == "cookie" else (payload.refresh_token if payload else None)
    )
    if not raw_refresh:
        raise AppError(
            status_code=401,
            code="SESSION_EXPIRED",
            message="Your session has expired. Sign in again to continue.",
        )
    result = await AuthService(session, settings).refresh(raw_refresh, transport=transport)
    rotated_refresh = result.refresh_cookie_token or result.refresh_token
    if rotated_refresh:
        _set_refresh_cookie(response, rotated_refresh, settings, transport=transport)
    return _response_from_result(result)


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MessageResponse:
    await enforce_rate_limit(
        request,
        settings,
        scope="auth.forgot_password",
        identity=_client_identity(request),
        limit=settings.login_rate_limit,
        window_seconds=60,
    )
    await AuthService(session, settings).request_password_reset(str(payload.email))
    return MessageResponse(
        message=("If an account exists for that email, a password reset link will be sent shortly.")
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MessageResponse:
    await enforce_rate_limit(
        request,
        settings,
        scope="auth.reset_password",
        identity=_client_identity(request),
        limit=settings.login_rate_limit,
        window_seconds=60,
    )
    await AuthService(session, settings).reset_password(payload)
    return MessageResponse(message="Your password has been reset. Sign in with the new password.")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MessageResponse:
    await AuthService(session, settings).change_password(principal.user, payload)
    _delete_refresh_cookie(response, settings)
    return MessageResponse(message="Your password has been changed. Sign in again to continue.")


@router.get("/me", response_model=MeResponse)
async def me(principal: Annotated[Principal, Depends(get_current_principal)]) -> MeResponse:
    return MeResponse(
        user=UserResponse(
            id=principal.user.id,
            email=principal.user.email,
            business=BusinessResponse(
                id=principal.business.id,
                business_name=principal.business.business_name,
                currency=principal.business.currency,
                language=principal.business.language,
                theme=principal.business.theme,
                timezone=principal.business.timezone,
            ),
        )
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    response: Response,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LogoutResponse:
    await AuthService(session, settings).logout(principal.auth_session)
    _delete_refresh_cookie(response, settings)
    return LogoutResponse(message="You have been signed out successfully.")
