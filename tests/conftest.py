"""Pytest configuration and fixtures for all tests."""

import pytest


@pytest.fixture(autouse=True)
def set_testing_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set TESTING environment variable for all tests."""
    monkeypatch.setenv("TESTING", "1")
