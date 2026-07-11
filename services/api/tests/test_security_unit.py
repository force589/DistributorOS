from uuid import uuid4

from pydantic import SecretStr, ValidationError

from distributoros.core.config import Settings
from distributoros.modules.identity.schemas import SignupRequest
from distributoros.modules.identity.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_is_hashed_and_verifiable() -> None:
    password = "correct horse battery staple"
    password_hash = hash_password(password)

    assert password_hash != password
    assert password not in password_hash
    assert verify_password(password, password_hash)
    assert not verify_password("incorrect password", password_hash)


def test_signup_validation_messages_are_specific() -> None:
    try:
        SignupRequest(business_name="  ", email="not-an-email", password="short")
    except ValidationError as exc:
        messages = {error["loc"][-1]: error["msg"] for error in exc.errors()}
    else:
        raise AssertionError("Invalid signup input should not validate")

    assert messages["business_name"] == "Business name is required."
    assert "valid email" in messages["email"].lower()
    assert messages["password"] == "Password must contain at least 8 characters."


def test_access_token_binds_user_session_and_business(test_settings: Settings) -> None:
    user_id = uuid4()
    session_id = uuid4()
    business_id = uuid4()
    token = create_access_token(
        test_settings,
        user_id=user_id,
        session_id=session_id,
        business_id=business_id,
    )

    claims = decode_access_token(test_settings, token)

    assert claims.user_id == user_id
    assert claims.session_id == session_id
    assert claims.business_id == business_id


def test_production_configuration_rejects_insecure_web_defaults() -> None:
    try:
        Settings(
            environment="production",
            database_url="postgresql+asyncpg://app:secret@database/distributoros",
            jwt_secret=SecretStr("a-production-secret-longer-than-thirty-two-characters"),
            cookie_secure=True,
            cors_origins=["http://localhost:8081"],
        )
    except ValidationError as exc:
        message = str(exc)
    else:
        raise AssertionError("Production settings should reject localhost CORS origins")

    assert "must not contain local development origins" in message
