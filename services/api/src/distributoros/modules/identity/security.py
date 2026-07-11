import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from distributoros.core.config import Settings

password_hasher = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = password_hasher.hash("DistributorOS timing placeholder")


@dataclass(frozen=True)
class AccessClaims:
    user_id: UUID
    session_id: UUID
    business_id: UUID


@dataclass(frozen=True)
class RefreshCredential:
    user_id: UUID
    session_id: UUID
    secret: str


@dataclass(frozen=True)
class PasswordResetCredential:
    token_id: UUID
    secret: str


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def create_access_token(
    settings: Settings,
    *,
    user_id: UUID,
    session_id: UUID,
    business_id: UUID,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "tid": str(business_id),
        "type": "access",
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm="HS256")


def decode_access_token(settings: Settings, token: str) -> AccessClaims:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "sid", "tid", "type", "exp", "iat"]},
        )
        if payload["type"] != "access":
            raise InvalidTokenError("Unexpected token type")
        return AccessClaims(
            user_id=UUID(payload["sub"]),
            session_id=UUID(payload["sid"]),
            business_id=UUID(payload["tid"]),
        )
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid access token") from exc


def create_refresh_credential(user_id: UUID, session_id: UUID) -> RefreshCredential:
    return RefreshCredential(
        user_id=user_id,
        session_id=session_id,
        secret=secrets.token_urlsafe(48),
    )


def serialize_refresh_credential(credential: RefreshCredential) -> str:
    return f"{credential.user_id}.{credential.session_id}.{credential.secret}"


def parse_refresh_credential(value: str) -> RefreshCredential:
    try:
        user_id, session_id, secret = value.split(".", maxsplit=2)
        if len(secret) < 32:
            raise ValueError
        return RefreshCredential(user_id=UUID(user_id), session_id=UUID(session_id), secret=secret)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid refresh credential") from exc


def hash_refresh_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def refresh_secret_matches(secret: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_refresh_secret(secret), expected_hash)


def create_password_reset_credential(token_id: UUID) -> PasswordResetCredential:
    return PasswordResetCredential(token_id=token_id, secret=secrets.token_urlsafe(48))


def serialize_password_reset_credential(credential: PasswordResetCredential) -> str:
    return f"{credential.token_id}.{credential.secret}"


def parse_password_reset_credential(value: str) -> PasswordResetCredential:
    try:
        token_id, secret = value.split(".", maxsplit=1)
        if len(secret) < 32:
            raise ValueError
        return PasswordResetCredential(token_id=UUID(token_id), secret=secret)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid password reset credential") from exc


def hash_password_reset_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def password_reset_secret_matches(secret: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_password_reset_secret(secret), expected_hash)
