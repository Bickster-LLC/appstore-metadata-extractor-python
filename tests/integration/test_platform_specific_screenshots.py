"""Test extraction of iPhone and iPad screenshots for dual-platform apps.

These tests originally targeted the "XiVi" app (id6503696206), which exposed a
generic "Screenshots" section. That app was renamed and no longer carries
screenshots, and Apple migrated the product page to a Svelte frontend whose
markup the legacy web screenshot scraper no longer matches. The combined
extractor now sources screenshots primarily from the iTunes API, so these tests
use a stable first-party app (Apple Books) that publishes both iPhone and iPad
screenshots and verify that distinct screenshot sets are returned per device.
"""

import pytest

from appstore_metadata_extractor import CombinedExtractor, WBSConfig

pytestmark = pytest.mark.integration

# Stable first-party app that publishes both iPhone and iPad screenshots.
DUAL_PLATFORM_APP_URL = "https://apps.apple.com/us/app/apple-books/id364709193"
DUAL_PLATFORM_APP_NAME = "Apple Books"


class TestPlatformSpecificScreenshots:
    """Test extraction of iPhone and iPad screenshots from a dual-platform app."""

    def test_dual_platform_app_screenshots(self):
        """An app with both device types yields both screenshot sets."""
        config = WBSConfig()
        extractor = CombinedExtractor(config)

        metadata = extractor.fetch(DUAL_PLATFORM_APP_URL)

        # Should extract both iPhone and iPad screenshots
        assert metadata.name == DUAL_PLATFORM_APP_NAME
        assert len(metadata.screenshots) > 0, "Should extract iPhone screenshots"
        assert len(metadata.ipad_screenshots) > 0, "Should extract iPad screenshots"

        # Verify all URLs are valid
        assert all(
            str(url).startswith("https://") for url in metadata.screenshots
        ), "All iPhone screenshot URLs should be valid"
        assert all(
            str(url).startswith("https://") for url in metadata.ipad_screenshots
        ), "All iPad screenshot URLs should be valid"

        # Verify the screenshots are from mzstatic CDN
        assert all(
            "mzstatic.com" in str(url) for url in metadata.screenshots
        ), "iPhone screenshots should be from Apple's CDN"
        assert all(
            "mzstatic.com" in str(url) for url in metadata.ipad_screenshots
        ), "iPad screenshots should be from Apple's CDN"

    def test_iphone_and_ipad_sets_differ(self):
        """iPhone and iPad screenshot sets are distinct for a dual-platform app."""
        config = WBSConfig()
        extractor = CombinedExtractor(config)

        metadata = extractor.fetch(DUAL_PLATFORM_APP_URL)

        # Both iPhone and iPad screenshots should be extracted
        assert len(metadata.screenshots) > 0, "Should have iPhone screenshots"
        assert len(metadata.ipad_screenshots) > 0, "Should have iPad screenshots"

        # Verify they are different sets of screenshots
        iphone_urls = set(str(url) for url in metadata.screenshots)
        ipad_urls = set(str(url) for url in metadata.ipad_screenshots)

        # The sets should be different (different device screenshots)
        assert (
            iphone_urls != ipad_urls
        ), "iPhone and iPad should have different screenshots"

    @pytest.mark.parametrize(
        "app_url,app_name",
        [
            (DUAL_PLATFORM_APP_URL, DUAL_PLATFORM_APP_NAME),
        ],
    )
    def test_various_dual_platform_apps(self, app_url, app_name):
        """Apps with both device types expose screenshots via the extractor."""
        config = WBSConfig()
        extractor = CombinedExtractor(config)

        metadata = extractor.fetch(app_url)

        assert metadata.name == app_name
        assert len(metadata.screenshots) > 0, f"{app_name} should have screenshots"
