"""Test handling of generic 'Screenshots' section without device specification."""

import pytest

from appstore_metadata_extractor import CombinedExtractor, WBSConfig


class TestGenericScreenshotsSection:
    """Test extraction from apps that have only 'Screenshots' without device specification."""

    def test_xivi_app_screenshots(self):
        """Test extraction from XIVI app which has generic Screenshots section."""
        config = WBSConfig()
        extractor = CombinedExtractor(config)

        # XIVI app has only "Screenshots" section, not "iPhone Screenshots"
        url = "https://apps.apple.com/us/app/xivi-ai-chat-assistant/id6503696206"
        metadata = extractor.fetch(url)

        # Should extract screenshots even with generic section name
        assert metadata.name == "XiVi - AI Chat Assistant"
        assert (
            len(metadata.screenshots) > 0
        ), "Should extract screenshots from generic section"
        assert all(
            str(url).startswith("https://") for url in metadata.screenshots
        ), "All screenshot URLs should be valid"

        # Verify the screenshots are from mzstatic CDN
        assert all(
            "mzstatic.com" in str(url) for url in metadata.screenshots
        ), "Screenshots should be from Apple's CDN"

    def test_generic_screenshots_not_mixed_with_ipad(self):
        """Ensure generic Screenshots section doesn't get mixed with iPad screenshots."""
        config = WBSConfig()
        extractor = CombinedExtractor(config)

        url = "https://apps.apple.com/us/app/xivi-ai-chat-assistant/id6503696206"
        metadata = extractor.fetch(url)

        # Generic screenshots should go to the main screenshots field
        assert len(metadata.screenshots) > 0
        # iPad screenshots should remain empty if not explicitly labeled
        assert len(metadata.ipad_screenshots) == 0

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
