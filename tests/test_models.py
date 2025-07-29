from datetime import datetime

import pytest
from pydantic import ValidationError

from appstore_metadata_extractor.models import AppInput, AppMetadata, ScrapeResult


class TestAppMetadata:
    def test_valid_metadata(self):
        metadata = AppMetadata(
            app_id="123456789",
            url="https://apps.apple.com/us/app/example/id123456789",
            title="Example App",
            developer="Example Developer",
            category="Productivity",
            version="1.0.0",
        )
        assert metadata.app_id == "123456789"
        assert metadata.title == "Example App"
        assert metadata.price is None
        assert metadata.in_app_purchases is False

    def test_metadata_with_all_fields(self):
        metadata = AppMetadata(
            app_id="123456789",
            url="https://apps.apple.com/us/app/example/id123456789",
            title="Example App",
            subtitle="The best example app",
            developer="Example Developer",
            category="Productivity",
            price="$4.99",
            in_app_purchases=True,
            description="This is a great app",
            version="2.0.0",
            version_date=datetime.now(),
            size="50 MB",
            languages=["English", "Spanish"],
            age_rating="4+",
            rating=4.5,
            rating_count=1000,
            screenshots=["url1", "url2"],
            icon_url="https://example.com/icon.png",
            whats_new="Bug fixes",
        )
        assert metadata.subtitle == "The best example app"
        assert metadata.price == "$4.99"
        assert metadata.in_app_purchases is True
        assert len(metadata.languages) == 2

    def test_invalid_url(self):
        with pytest.raises(ValidationError):
            AppMetadata(
                app_id="123456789",
                url="not-a-valid-url",
                title="Example App",
                developer="Example Developer",
                category="Productivity",
                version="1.0.0",
            )


class TestAppInput:
    def test_valid_input(self):
        app_input = AppInput(
            name="Test App", url="https://apps.apple.com/us/app/test/id123456789"
        )
        assert app_input.name == "Test App"
        assert str(app_input.url) == "https://apps.apple.com/us/app/test/id123456789"

    def test_invalid_url(self):
        with pytest.raises(ValidationError):
            AppInput(name="Test App", url="invalid-url")


class TestScrapeResult:
    def test_successful_result(self):
        metadata = AppMetadata(
            app_id="123456789",
            url="https://apps.apple.com/us/app/example/id123456789",
            title="Example App",
            developer="Example Developer",
            category="Productivity",
            version="1.0.0",
        )
        result = ScrapeResult(success=True, app_metadata=metadata)
        assert result.success is True
        assert result.app_metadata.title == "Example App"
        assert result.error is None

    def test_failed_result(self):
        result = ScrapeResult(
            success=False, error="Network error", error_details={"code": 500}
        )
        assert result.success is False
        assert result.error == "Network error"
        assert result.app_metadata is None
