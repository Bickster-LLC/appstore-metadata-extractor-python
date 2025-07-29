"""Security module for JWT and password handling."""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from ..settings import Settings, get_settings

# Password hashing context with bcrypt
# Initialize with default rounds, will use settings at runtime
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # WBS boundary: 12 rounds default
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash using constant-time comparison.

    Args:
        plain_password: The plain text password to verify
        hashed_password: The bcrypt hashed password to compare against

    Returns:
        True if password matches, False otherwise
    """
    return bool(pwd_context.verify(plain_password, hashed_password))


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt with configured rounds.

    Args:
        password: The plain text password to hash

    Returns:
        The bcrypt hashed password
    """
    return str(pwd_context.hash(password))


def create_token(
    data: dict[str, Any],
    expires_delta: timedelta,
    token_type: str = "access",
    _settings: Optional[Settings] = None,
) -> str:
    """Create a JWT token with expiration and type.

    Args:
        data: The data to encode in the token
        expires_delta: How long until the token expires
        token_type: Type of token (access or refresh)
        _settings: Optional settings override (for testing)

    Returns:
        The encoded JWT token
    """
    config = _settings or get_settings()
    to_encode = data.copy()
    expire = datetime.now(UTC) + expires_delta
    to_encode.update(
        {
            "exp": expire,
            "type": token_type,
            "iat": datetime.now(UTC),
            "jti": secrets.token_urlsafe(32),  # Unique token ID
        }
    )

    encoded_jwt = jwt.encode(to_encode, config.secret_key, algorithm=config.algorithm)
    return str(encoded_jwt)


def create_access_token(
    data: dict[str, Any], _settings: Optional[Settings] = None
) -> str:
    """Create a JWT access token with short expiration.

    Per WBS boundaries: 15 minute expiration

    Args:
        data: The data to encode (typically {"sub": user_id})
        _settings: Optional settings override (for testing)

    Returns:
        The encoded JWT access token
    """
    config = _settings or get_settings()
    access_token_expires = timedelta(minutes=config.access_token_expire_minutes)
    return create_token(
        data, expires_delta=access_token_expires, token_type="access", _settings=config
    )


def create_refresh_token(
    data: dict[str, Any], _settings: Optional[Settings] = None
) -> str:
    """Create a JWT refresh token with long expiration.

    Per WBS boundaries: 30 day expiration

    Args:
        data: The data to encode (typically {"sub": user_id})
        _settings: Optional settings override (for testing)

    Returns:
        The encoded JWT refresh token
    """
    config = _settings or get_settings()
    refresh_token_expires = timedelta(days=config.refresh_token_expire_days)
    return create_token(
        data,
        expires_delta=refresh_token_expires,
        token_type="refresh",
        _settings=config,
    )


def decode_token(
    token: str, expected_type: str = "access", _settings: Optional[Settings] = None
) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Args:
        token: The JWT token to decode
        expected_type: The expected token type (access or refresh)
        _settings: Optional settings override (for testing)

    Returns:
        The decoded token payload

    Raises:
        JWTError: If token is invalid, expired, or wrong type
    """
    config = _settings or get_settings()
    try:
        payload = jwt.decode(token, config.secret_key, algorithms=[config.algorithm])

        # Validate token type
        token_type = payload.get("type")
        if token_type != expected_type:
            raise JWTError(
                f"Invalid token type. Expected {expected_type}, got {token_type}"
            )

        return dict(payload)
    except JWTError:
        raise


def hash_token(token: str) -> str:
    """Create a secure hash of a token for storage.

    Used for storing refresh tokens and verification tokens in the database.

    Args:
        token: The token to hash

    Returns:
        A secure hash of the token
    """
    # Use a simple hash for token storage (not for passwords!)
    import hashlib

    return hashlib.sha256(token.encode()).hexdigest()


def generate_verification_token() -> str:
    """Generate a secure random token for email verification.

    Returns:
        A URL-safe random token
    """
    return secrets.token_urlsafe(32)


def generate_password_reset_token() -> str:
    """Generate a secure random token for password reset.

    Returns:
        A URL-safe random token
    """
    return secrets.token_urlsafe(32)


def validate_password_complexity(password: str) -> bool:
    """Validate password meets complexity requirements.

    Per WBS boundaries:
    - Minimum 8 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 number

    Args:
        password: The password to validate

    Returns:
        True if password meets requirements, False otherwise
    """
    _settings = get_settings()
    if len(password) < _settings.password_min_length:
        return False

    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)

    return has_upper and has_lower and has_digit


def get_password_strength_message(password: str) -> str:
    """Get a descriptive message about password requirements.

    Args:
        password: The password to check

    Returns:
        A message describing what's missing
    """
    messages = []

    _settings = get_settings()
    if len(password) < _settings.password_min_length:
        messages.append(f"at least {_settings.password_min_length} characters")

    if not any(c.isupper() for c in password):
        messages.append("at least 1 uppercase letter")

    if not any(c.islower() for c in password):
        messages.append("at least 1 lowercase letter")

    if not any(c.isdigit() for c in password):
        messages.append("at least 1 number")

    if messages:
        return f"Password must contain {', '.join(messages)}"

    return "Password meets all requirements"
