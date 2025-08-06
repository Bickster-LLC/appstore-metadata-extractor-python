"""Test handling of platform-specific screenshot extraction using URL parameters."""

import pytest

from appstore_metadata_extractor import CombinedExtractor, WBSConfig


class TestPlatformSpecificScreenshots:
    """Test extraction of screenshots using platform-specific URL parameters."""

    def test_xivi_app_screenshots(self):
        """Test extraction from XIVI app which has both iPhone and iPad screenshots."""
        config = WBSConfig()
        extractor = CombinedExtractor(config)

        # XIVI app has a generic "Screenshots" section with both device types
        url = "https://apps.apple.com/us/app/xivi-ai-chat-assistant/id6503696206"
        metadata = extractor.fetch(url)

        # Should extract both iPhone and iPad screenshots
        assert metadata.name == "XiVi - AI Chat Assistant"
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

    def test_platform_specific_extraction(self):
        """Test that platform-specific URLs correctly extract device screenshots."""
        config = WBSConfig()
        extractor = CombinedExtractor(config)

        url = "https://apps.apple.com/us/app/xivi-ai-chat-assistant/id6503696206"
        metadata = extractor.fetch(url)

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
            # Add more apps here that have generic Screenshots sections
            (
                "https://apps.apple.com/us/app/xivi-ai-chat-assistant/id6503696206",
                "XiVi - AI Chat Assistant",
            ),
        ],
    )
    def test_various_generic_screenshot_apps(self, app_url, app_name):
        """Test various apps with generic screenshot sections."""
        config = WBSConfig()
        extractor = CombinedExtractor(config)

        metadata = extractor.fetch(app_url)

        assert metadata.name == app_name
        assert len(metadata.screenshots) > 0, f"{app_name} should have screenshots"
