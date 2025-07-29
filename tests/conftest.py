"""Pytest configuration and fixtures for all tests."""

import pytest

from appstore_metadata_extractor.settings import Settings


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings."""
    return Settings(
        debug=True,
        rate_limit_calls=100,
        rate_limit_period=60,
        cache_ttl=300,
        cache_enabled=True,
        # Scraping settings
        request_timeout=30,
        max_retries=3,
        scraping_delay=1.0,
        concurrent_requests=5,
    )


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
