from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import uuid4

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.core.config import Settings
from distributoros.core.database import set_request_context, set_tenant_context, set_user_context
from distributoros.core.errors import AppError
from distributoros.core.outbox import OutboxEvent
from distributoros.modules.identity.models import AuthSession, PasswordResetToken, User
from distributoros.modules.identity.repository import IdentityRepository
from distributoros.modules.identity.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
    SignupRequest,
)
from distributoros.modules.identity.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    create_password_reset_credential,
    create_refresh_credential,
    hash_password,
    hash_password_reset_secret,
    hash_refresh_secret,
    normalize_email,
    parse_password_reset_credential,
    parse_refresh_credential,
    password_reset_secret_matches,
    refresh_secret_matches,
    serialize_password_reset_credential,
    serialize_refresh_credential,
    verify_password,
)
from distributoros.modules.tenancy.models import Business, Membership
from distributoros.modules.tenancy.repository import TenancyRepository


@dataclass(frozen=True)
class AuthResult:
    access_token: str
    refresh_token: str | None
    refresh_cookie_token: str | None
    expires_in: int
    user: User
    business: Business
    auth_session: AuthSession


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.identity = IdentityRepository(session)
        self.tenancy = TenancyRepository(session)
        self.logger = structlog.get_logger("distributoros.auth")

    async def signup(self, request: SignupRequest, *, transport: str) -> AuthResult:
        email = normalize_email(str(request.email))
        if await self.identity.get_user_by_email(email):
            raise AppError(
                status_code=409,
                code="EMAIL_ALREADY_REGISTERED",
                message="This email is already registered. Sign in or use a different email.",
                field_errors={"email": "This email is already registered."},
            )

        user = User(id=uuid4(), email=email, password_hash=hash_password(request.password))
        business = Business(
            id=uuid4(),
            business_name=request.business_name,
            # Supplying this value avoids INSERT ... RETURNING on the RLS-protected
            # business row before its owner membership exists.
            created_at=datetime.now(UTC),
        )
        membership = Membership(business_id=business.id, user_id=user.id, role="owner")

        await set_request_context(self.session, user_id=user.id, business_id=business.id)
        self.identity.add_user(user)
        self.tenancy.add_business(business)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            if _is_email_unique_violation(exc):
                raise AppError(
                    status_code=409,
                    code="EMAIL_ALREADY_REGISTERED",
                    message=("This email is already registered. Sign in or use a different email."),
                    field_errors={"email": "This email is already registered."},
                ) from exc
            raise
        self.tenancy.add_membership(membership)
        await self.session.flush()
        auth_result = self._create_session(user, business, transport=transport)
        await self.session.flush()

        self.logger.info(
            "signup_succeeded",
            user_id=str(user.id),
            business_id=str(business.id),
            session_id=str(auth_result.auth_session.id),
        )
        return auth_result

    async def login(self, request: LoginRequest, *, transport: str) -> AuthResult:
        email = normalize_email(str(request.email))
        user = await self.identity.get_user_by_email(email)
        password_hash = user.password_hash if user else DUMMY_PASSWORD_HASH
        password_valid = verify_password(request.password, password_hash)
        if user is None or not password_valid:
            self.logger.warning("login_failed", reason="invalid_credentials")
            raise AppError(
                status_code=401,
                code="INVALID_CREDENTIALS",
                message="Incorrect email or password. Check your details and try again.",
            )

        await set_user_context(self.session, user.id)
        membership = await self.tenancy.get_first_membership(user.id)
        if membership is None:
            self.logger.warning("login_failed", user_id=str(user.id), reason="no_membership")
            raise AppError(
                status_code=403,
                code="BUSINESS_ACCESS_REQUIRED",
                message=(
                    "Your account is not connected to an active business. "
                    "Contact support to restore access."
                ),
            )

        await set_tenant_context(self.session, membership.business_id)
        business = await self.tenancy.get_business(membership.business_id)
        if business is None:
            raise AppError(
                status_code=403,
                code="BUSINESS_ACCESS_REQUIRED",
                message=("Your business is not available. Contact support to restore access."),
            )

        result = self._create_session(user, business, transport=transport)
        await self.session.flush()
        self.logger.info(
            "login_succeeded",
            user_id=str(user.id),
            business_id=str(business.id),
            session_id=str(result.auth_session.id),
        )
        return result

    async def refresh(self, raw_token: str, *, transport: str) -> AuthResult:
        try:
            credential = parse_refresh_credential(raw_token)
        except ValueError as exc:
            raise self._refresh_error() from exc

        await set_user_context(self.session, credential.user_id)
        # Serialize rotation for a session so concurrent refreshes cannot both
        # validate the same credential and mint competing token families.
        auth_session = await self.identity.get_session_for_update(credential.session_id)
        now = datetime.now(UTC)
        if (
            auth_session is None
            or auth_session.user_id != credential.user_id
            or auth_session.revoked_at is not None
            or auth_session.expires_at <= now
            or auth_session.refresh_transport != transport
        ):
            self.logger.warning(
                "refresh_failed",
                user_id=str(credential.user_id),
                session_id=str(credential.session_id),
            )
            raise self._refresh_error()

        current_token_matches = refresh_secret_matches(
            credential.secret, auth_session.refresh_token_hash
        )
        previous_token_matches = (
            transport == "cookie"
            and auth_session.previous_refresh_token_hash is not None
            and auth_session.previous_refresh_valid_until is not None
            and auth_session.previous_refresh_valid_until > now
            and refresh_secret_matches(credential.secret, auth_session.previous_refresh_token_hash)
        )
        if not current_token_matches and not previous_token_matches:
            self.logger.warning(
                "refresh_failed",
                user_id=str(credential.user_id),
                session_id=str(credential.session_id),
                reason="credential_rejected",
            )
            raise self._refresh_error()

        membership = await self.tenancy.get_membership(
            auth_session.user_id, auth_session.business_id
        )
        if membership is None:
            raise AppError(
                status_code=403,
                code="BUSINESS_ACCESS_REQUIRED",
                message=(
                    "Your account no longer has access to this business. "
                    "Ask a business owner to restore access."
                ),
            )

        await set_tenant_context(self.session, auth_session.business_id)
        user = await self.identity.get_user(auth_session.user_id)
        business = await self.tenancy.get_business(auth_session.business_id)
        if user is None or business is None:
            raise self._refresh_error()

        rotated = None
        if current_token_matches:
            rotated = create_refresh_credential(user.id, auth_session.id)
            auth_session.previous_refresh_token_hash = auth_session.refresh_token_hash
            auth_session.previous_refresh_valid_until = now + timedelta(
                seconds=self.settings.refresh_grace_seconds
            )
            auth_session.refresh_token_hash = hash_refresh_secret(rotated.secret)
        else:
            self.logger.info(
                "concurrent_cookie_refresh_recovered",
                user_id=str(user.id),
                session_id=str(auth_session.id),
            )
        auth_session.last_used_at = now
        access_token = create_access_token(
            self.settings,
            user_id=user.id,
            session_id=auth_session.id,
            business_id=business.id,
        )
        await self.session.flush()
        self.logger.info(
            "session_refreshed",
            user_id=str(user.id),
            business_id=str(business.id),
            session_id=str(auth_session.id),
        )
        return AuthResult(
            access_token=access_token,
            refresh_token=(
                serialize_refresh_credential(rotated)
                if rotated is not None and transport == "native"
                else None
            ),
            refresh_cookie_token=(
                serialize_refresh_credential(rotated)
                if rotated is not None and transport == "cookie"
                else None
            ),
            expires_in=self.settings.access_token_minutes * 60,
            user=user,
            business=business,
            auth_session=auth_session,
        )

    async def logout(self, auth_session: AuthSession) -> None:
        if auth_session.revoked_at is None:
            auth_session.revoked_at = datetime.now(UTC)
            await self.session.flush()
        self.logger.info(
            "logout_succeeded",
            user_id=str(auth_session.user_id),
            business_id=str(auth_session.business_id),
            session_id=str(auth_session.id),
        )

    async def request_password_reset(self, email_address: str) -> None:
        email = normalize_email(email_address)
        user = await self.identity.get_user_by_email(email)
        if user is None:
            self.logger.info("password_reset_requested", matched_account=False)
            return

        now = datetime.now(UTC)
        await self.identity.invalidate_password_reset_tokens(user.id, now)
        token_id = uuid4()
        credential = create_password_reset_credential(token_id)
        serialized = serialize_password_reset_credential(credential)
        reset_token = PasswordResetToken(
            id=token_id,
            user_id=user.id,
            token_hash=hash_password_reset_secret(credential.secret),
            expires_at=now + timedelta(minutes=self.settings.password_reset_minutes),
        )
        query = urlencode({"token": serialized})
        separator = "&" if "?" in self.settings.password_reset_url_base else "?"
        self.identity.add_password_reset_token(reset_token)
        self.session.add(
            OutboxEvent(
                event_type="identity.password_reset_requested",
                payload={
                    "recipient": email,
                    "reset_url": f"{self.settings.password_reset_url_base}{separator}{query}",
                },
            )
        )
        await self.session.flush()
        self.logger.info("password_reset_requested", matched_account=True, user_id=str(user.id))

    async def reset_password(self, request: ResetPasswordRequest) -> None:
        try:
            credential = parse_password_reset_credential(request.token)
        except ValueError as exc:
            raise self._password_reset_error() from exc
        token = await self.identity.get_password_reset_token_for_update(credential.token_id)
        now = datetime.now(UTC)
        if (
            token is None
            or token.used_at is not None
            or token.expires_at <= now
            or not password_reset_secret_matches(credential.secret, token.token_hash)
        ):
            raise self._password_reset_error()
        user = await self.identity.get_user(token.user_id)
        if user is None:
            raise self._password_reset_error()
        await set_user_context(self.session, user.id)
        user.password_hash = hash_password(request.new_password)
        token.used_at = now
        await self.identity.invalidate_password_reset_tokens(user.id, now)
        await self.identity.revoke_all_sessions(user.id, now)
        await self.session.flush()
        self.logger.info("password_reset_completed", user_id=str(user.id))

    async def change_password(
        self,
        user: User,
        request: ChangePasswordRequest,
    ) -> None:
        if not verify_password(request.current_password, user.password_hash):
            raise AppError(
                status_code=422,
                code="CURRENT_PASSWORD_INCORRECT",
                message="Current password is incorrect. Check it and try again.",
                field_errors={"current_password": "Current password is incorrect."},
            )
        if request.current_password == request.new_password:
            raise AppError(
                status_code=422,
                code="PASSWORD_UNCHANGED",
                message="New password must be different from the current password.",
                field_errors={
                    "new_password": "Choose a password different from the current password."
                },
            )
        now = datetime.now(UTC)
        user.password_hash = hash_password(request.new_password)
        await self.identity.invalidate_password_reset_tokens(user.id, now)
        await self.identity.revoke_all_sessions(user.id, now)
        await self.session.flush()
        self.logger.info("password_changed", user_id=str(user.id))

    def _create_session(self, user: User, business: Business, *, transport: str) -> AuthResult:
        session_id = uuid4()
        credential = create_refresh_credential(user.id, session_id)
        auth_session = AuthSession(
            id=session_id,
            user_id=user.id,
            business_id=business.id,
            refresh_token_hash=hash_refresh_secret(credential.secret),
            refresh_transport=transport,
            expires_at=datetime.now(UTC) + timedelta(days=self.settings.refresh_token_days),
        )
        self.identity.add_session(auth_session)
        access_token = create_access_token(
            self.settings,
            user_id=user.id,
            session_id=session_id,
            business_id=business.id,
        )
        return AuthResult(
            access_token=access_token,
            refresh_token=(
                serialize_refresh_credential(credential) if transport == "native" else None
            ),
            refresh_cookie_token=(
                serialize_refresh_credential(credential) if transport == "cookie" else None
            ),
            expires_in=self.settings.access_token_minutes * 60,
            user=user,
            business=business,
            auth_session=auth_session,
        )

    @staticmethod
    def _refresh_error() -> AppError:
        return AppError(
            status_code=401,
            code="SESSION_EXPIRED",
            message="Your session has expired. Sign in again to continue.",
        )

    @staticmethod
    def _password_reset_error() -> AppError:
        return AppError(
            status_code=422,
            code="PASSWORD_RESET_LINK_INVALID",
            message=(
                "This password reset link is invalid or has expired. "
                "Request a new link and try again."
            ),
            field_errors={"token": "Request a new password reset link."},
        )


def normalize_transport(client_platform: str) -> str:
    return "cookie" if client_platform.lower() == "web" else "native"


def _is_email_unique_violation(exc: IntegrityError) -> bool:
    original = exc.orig
    sqlstate = getattr(original, "sqlstate", None)
    constraint_name = getattr(original, "constraint_name", None)
    return sqlstate == "23505" and constraint_name == "uq_users_email"
