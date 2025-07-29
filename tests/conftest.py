"""Pytest configuration and fixtures for all tests."""

import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from appstore_metadata_extractor.api.main import app
from appstore_metadata_extractor.core.security import (
    create_access_token,
    get_password_hash,
)
from appstore_metadata_extractor.db.base import Base, get_db
from appstore_metadata_extractor.db.models import (  # noqa: F401
    AppMetadata,
    AppTag,
    AppTagAssociation,
    EmailVerification,
    LoginAttempt,
    MetadataChangeLog,
    PasswordReset,
    RefreshToken,
    TrackedApp,
    User,
)
from appstore_metadata_extractor.settings import Settings, get_settings

UTC = timezone.utc


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Override settings for testing."""
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        secret_key="test-secret-key-for-testing-only",
        debug=True,
    )


@pytest_asyncio.fixture
async def test_db(test_client: TestClient) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session using the same database as test_client."""
    # Get the engine from test_client
    engine = test_client._test_engine

    # Create session factory
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    # Create and yield the session
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def test_user(test_db: AsyncSession) -> User:
    """Create a test user."""
    import uuid

    user = User(
        id=uuid.uuid4(),  # SQLAlchemy will handle conversion
        email="test@example.com",
        username="testuser",
        hashed_password=get_password_hash("testpass123"),
        is_active=True,
        is_verified=True,
        is_superuser=False,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_tracked_app(test_db: AsyncSession, test_user: User) -> TrackedApp:
    """Create a test tracked app."""
    app = TrackedApp(
        user_id=test_user.id,
        app_id="123456789",
        app_name="Test App",
        bundle_id="com.example.testapp",
        is_active=True,
        check_frequency=86400,
        notify_on_update=True,
        last_checked_at=datetime.now(UTC),
    )
    test_db.add(app)
    await test_db.commit()
    await test_db.refresh(app)
    return app


@pytest.fixture
def auth_headers(test_user: User, test_settings: Settings) -> dict[str, str]:
    """Create authentication headers for test user."""
    # Import here to avoid circular imports and ensure fresh import
    from appstore_metadata_extractor.core.security import create_access_token

    token = create_access_token({"sub": str(test_user.id)}, _settings=test_settings)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_client(test_settings: Settings) -> Generator[TestClient, None, None]:
    """Create a test client with proper async database handling."""
    # Import here to avoid circular imports
    import os
    import tempfile
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
    from sqlalchemy.pool import StaticPool

    # Create a shared database for the entire test
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Create engine with StaticPool to ensure connection reuse
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False,
    )

    # Create session factory
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    # Override the get_db dependency to use our test session factory
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with async_session_factory() as session:
            yield session

    # Override the get_settings dependency
    def override_get_settings():
        return test_settings

    # Create tables synchronously
    import asyncio

    async def create_tables():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(create_tables())

    try:
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_settings] = override_get_settings

        with TestClient(app) as client:
            # Store engine on client for cleanup
            client._test_engine = engine
            client._test_db_path = db_path
            yield client
    finally:
        # Clean up
        app.dependency_overrides.clear()

        # Dispose engine
        asyncio.run(engine.dispose())

        # Remove database file
        if os.path.exists(db_path):
            os.unlink(db_path)


# Alias for backwards compatibility
@pytest.fixture
def async_client(test_client: TestClient) -> TestClient:
    """Alias for test client."""
    return test_client


@pytest.fixture(autouse=True)
def override_settings(test_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """Override settings for all tests."""
    # Set TESTING environment variable
    monkeypatch.setenv("TESTING", "1")

    # Clear the settings cache to force fresh settings
    from appstore_metadata_extractor.settings import _get_cached_settings

    if hasattr(_get_cached_settings, "cache_clear"):
        _get_cached_settings.cache_clear()

    # Override settings getter
    monkeypatch.setattr(
        "appstore_metadata_extractor.settings.get_settings", lambda: test_settings
    )
    # Override the global settings instance in the settings module
    monkeypatch.setattr("appstore_metadata_extractor.settings.settings", test_settings)
    # Security module now uses get_settings() directly, no need to override
