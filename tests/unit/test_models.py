"""Unit tests for database models."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.appstore_metadata_extractor.core.security import get_password_hash
from src.appstore_metadata_extractor.db.models import (
    EmailVerification,
    LoginAttempt,
    PasswordReset,
    RefreshToken,
    User,
)


class TestUserModel:
    """Test User model functionality."""

    async def test_create_user(self, test_db: AsyncSession) -> None:
        """Test creating a user with all required fields."""
        user = User(
            email="test@example.com",
            username="testuser",
            hashed_password=get_password_hash("SecurePass123!"),
        )

        test_db.add(user)
        await test_db.commit()
        await test_db.refresh(user)

        assert user.id is not None
        assert isinstance(user.id, uuid.UUID)
        assert user.email == "test@example.com"
        assert user.username == "testuser"
        assert user.is_active is True
        assert user.is_verified is False
        assert user.is_superuser is False
        assert user.created_at is not None
        assert user.updated_at is not None
        assert user.last_login_at is None
        assert user.deleted_at is None

    async def test_user_soft_delete(self, test_db: AsyncSession) -> None:
        """Test soft delete functionality."""
        user = User(
            email="delete@example.com",
            username="deleteuser",
            hashed_password=get_password_hash("SecurePass123!"),
        )

        test_db.add(user)
        await test_db.commit()

        # Soft delete
        user.soft_delete()
        await test_db.commit()

        assert user.deleted_at is not None
        assert user.is_deleted is True

        # User should still exist in database
        result = await test_db.execute(
            select(User).where(User.email == "delete@example.com")
        )
        found_user = result.scalar_one_or_none()
        assert found_user is not None
        assert found_user.is_deleted is True

    async def test_user_unique_constraints(self, test_db: AsyncSession) -> None:
        """Test that email and username must be unique."""
        user1 = User(
            email="unique@example.com",
            username="uniqueuser",
            hashed_password=get_password_hash("SecurePass123!"),
        )

        test_db.add(user1)
        await test_db.commit()

        # Try to create user with same email
        user2 = User(
            email="unique@example.com",  # Same email
            username="differentuser",
            hashed_password=get_password_hash("SecurePass123!"),
        )

        test_db.add(user2)
        with pytest.raises(Exception):  # Should raise IntegrityError
            await test_db.commit()


class TestRefreshTokenModel:
    """Test RefreshToken model functionality."""

    async def test_create_refresh_token(self, test_db: AsyncSession) -> None:
        """Test creating a refresh token."""
        # Create user first
        user = User(
            email="token@example.com",
            username="tokenuser",
            hashed_password=get_password_hash("SecurePass123!"),
        )
        test_db.add(user)
        await test_db.commit()

        # Create refresh token
        token = RefreshToken(
            user_id=user.id,
            token_hash="hashed_token_12345",
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )

        test_db.add(token)
        await test_db.commit()
        await test_db.refresh(token)

        assert token.id is not None
        assert token.user_id == user.id
        assert token.token_hash == "hashed_token_12345"
        assert token.revoked_at is None
        assert token.is_revoked is False
        assert token.is_expired is False
        assert token.is_valid is True

    async def test_refresh_token_expiration(self, test_db: AsyncSession) -> None:
        """Test refresh token expiration check."""
        user = User(
            email="expire@example.com",
            username="expireuser",
            hashed_password=get_password_hash("SecurePass123!"),
        )
        test_db.add(user)
        await test_db.commit()

        # Create expired token
        expired_token = RefreshToken(
            user_id=user.id,
            token_hash="expired_token",
            expires_at=datetime.now(UTC) - timedelta(days=1),  # Expired
        )

        test_db.add(expired_token)
        await test_db.commit()

        assert expired_token.is_expired is True
        assert expired_token.is_valid is False

    async def test_refresh_token_revocation(self, test_db: AsyncSession) -> None:
        """Test refresh token revocation."""
        user = User(
            email="revoke@example.com",
            username="revokeuser",
            hashed_password=get_password_hash("SecurePass123!"),
        )
        test_db.add(user)
        await test_db.commit()

        # Create token
        token = RefreshToken(
            user_id=user.id,
            token_hash="revoked_token",
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )

        test_db.add(token)
        await test_db.commit()

        # Revoke token
        token.revoked_at = datetime.now(UTC)
        await test_db.commit()

        assert token.is_revoked is True
        assert token.is_valid is False


class TestEmailVerificationModel:
    """Test EmailVerification model functionality."""

    async def test_create_email_verification(self, test_db: AsyncSession) -> None:
        """Test creating an email verification token."""
        user = User(
            email="verify@example.com",
            username="verifyuser",
            hashed_password=get_password_hash("SecurePass123!"),
        )
        test_db.add(user)
        await test_db.commit()

        verification = EmailVerification(
            user_id=user.id,
            token_hash="verification_token_hash",
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )

        test_db.add(verification)
        await test_db.commit()

        assert verification.id is not None
        assert verification.verified_at is None
        assert verification.is_verified is False
        assert verification.is_expired is False
        assert verification.is_valid is True

    async def test_email_verification_complete(self, test_db: AsyncSession) -> None:
        """Test completing email verification."""
        user = User(
            email="complete@example.com",
            username="completeuser",
            hashed_password=get_password_hash("SecurePass123!"),
        )
        test_db.add(user)
        await test_db.commit()

        verification = EmailVerification(
            user_id=user.id,
            token_hash="complete_token_hash",
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )

        test_db.add(verification)
        await test_db.commit()

        # Mark as verified
        verification.verified_at = datetime.now(UTC)
        user.is_verified = True
        await test_db.commit()

        assert verification.is_verified is True
        assert verification.is_valid is False  # Already used
        assert user.is_verified is True


class TestPasswordResetModel:
    """Test PasswordReset model functionality."""

    async def test_create_password_reset(self, test_db: AsyncSession) -> None:
        """Test creating a password reset token."""
        user = User(
            email="reset@example.com",
            username="resetuser",
            hashed_password=get_password_hash("SecurePass123!"),
        )
        test_db.add(user)
        await test_db.commit()

        reset = PasswordReset(
            user_id=user.id,
            token_hash="reset_token_hash",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

        test_db.add(reset)
        await test_db.commit()

        assert reset.id is not None
        assert reset.used_at is None
        assert reset.is_used is False
        assert reset.is_expired is False
        assert reset.is_valid is True

    async def test_password_reset_used(self, test_db: AsyncSession) -> None:
        """Test marking password reset as used."""
        user = User(
            email="used@example.com",
            username="useduser",
            hashed_password=get_password_hash("SecurePass123!"),
        )
        test_db.add(user)
        await test_db.commit()

        reset = PasswordReset(
            user_id=user.id,
            token_hash="used_token_hash",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

        test_db.add(reset)
        await test_db.commit()

        # Mark as used
        reset.used_at = datetime.now(UTC)
        await test_db.commit()

        assert reset.is_used is True
        assert reset.is_valid is False


class TestLoginAttemptModel:
    """Test LoginAttempt model functionality."""

    async def test_create_login_attempt(self, test_db: AsyncSession) -> None:
        """Test creating login attempt records."""
        # Successful attempt
        success_attempt = LoginAttempt(
            email="attempt@example.com",
            ip_address="192.168.1.1",
            success=True,
        )

        test_db.add(success_attempt)
        await test_db.commit()

        assert success_attempt.id is not None
        assert success_attempt.email == "attempt@example.com"
        assert success_attempt.ip_address == "192.168.1.1"
        assert success_attempt.success is True
        assert success_attempt.attempted_at is not None

        # Failed attempt
        failed_attempt = LoginAttempt(
            email="attempt@example.com",
            ip_address="192.168.1.1",
            success=False,
        )

        test_db.add(failed_attempt)
        await test_db.commit()

        assert failed_attempt.success is False

    async def test_login_attempt_ipv6(self, test_db: AsyncSession) -> None:
        """Test that IPv6 addresses are supported."""
        attempt = LoginAttempt(
            email="ipv6@example.com",
            ip_address="2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            success=True,
        )

        test_db.add(attempt)
        await test_db.commit()

        # Should handle full IPv6 address (45 chars max)
        assert len(attempt.ip_address) <= 45
