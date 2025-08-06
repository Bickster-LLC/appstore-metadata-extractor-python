"""Integration tests for screenshot validation including resolution checking."""

import asyncio
import io
import re
from typing import Dict, List, Optional, Tuple

import pytest
import requests
from PIL import Image

from appstore_metadata_extractor.core import CombinedExtractor, WBSConfig


class ScreenshotValidator:
    """Helper class to validate screenshot dimensions."""

    # Common iPhone screenshot resolutions (width x height)
    IPHONE_RESOLUTIONS = [
        # 6.9" iPhone (mandatory)
        (1320, 2868),
        (2868, 1320),  # Landscape
        # 6.7" iPhone
        (1290, 2796),
        (2796, 1290),  # Landscape
        # 6.5" iPhone
        (1242, 2688),
        (2688, 1242),  # Landscape
        # 5.5" iPhone
        (1242, 2208),
        (2208, 1242),  # Landscape
        # Common resized versions
        (392, 696),  # Common thumbnail size
        (696, 392),  # Landscape thumbnail
    ]

    # Common iPad screenshot resolutions (width x height)
    IPAD_RESOLUTIONS = [
        # 13" iPad (mandatory)
        (2160, 2880),
        (2880, 2160),  # Landscape
        # 12.9" iPad
        (2048, 2732),
        (2732, 2048),  # Landscape
        # 11" iPad
        (1668, 2388),
        (2388, 1668),  # Landscape
        # 10.5" iPad
        (1668, 2224),
        (2224, 1668),  # Landscape
        # Common resized versions
        (576, 768),  # Common thumbnail size
        (768, 576),  # Landscape thumbnail
    ]

    @staticmethod
    def extract_resolution_from_url(url: str) -> Optional[Tuple[int, int]]:
        """Extract resolution from App Store screenshot URL."""
        # Look for pattern like "392x696bb" in the URL
        match = re.search(r"(\d+)x(\d+)bb", url)
        if match:
            width = int(match.group(1))
            height = int(match.group(2))
            return (width, height)
        return None

    @staticmethod
    def download_image(url: str) -> Optional[Image.Image]:
        """Download image from URL and return PIL Image object."""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return Image.open(io.BytesIO(response.content))
        except Exception as e:
            print(f"Failed to download image: {e}")
            return None

    @classmethod
    def validate_device_type(cls, width: int, height: int) -> str:
        """Determine if resolution matches iPhone or iPad."""
        resolution = (width, height)

        if resolution in cls.IPHONE_RESOLUTIONS:
            return "iPhone"
        elif resolution in cls.IPAD_RESOLUTIONS:
            return "iPad"

        # Check aspect ratio if exact resolution not found
        aspect_ratio = width / height if height > 0 else 0

        # iPhone typically has ~9:16 portrait or ~16:9 landscape
        if 0.5 <= aspect_ratio <= 0.7 or 1.4 <= aspect_ratio <= 2.0:
            return "iPhone (probable)"
        # iPad typically has ~3:4 portrait or ~4:3 landscape
        elif 0.7 <= aspect_ratio <= 0.8 or 1.25 <= aspect_ratio <= 1.4:
            return "iPad (probable)"
        else:
            return "Unknown"


@pytest.mark.asyncio
async def test_screenshot_extraction_and_validation():
    """Test screenshot extraction for both iPhone and iPad with resolution validation."""
    wbs_config = WBSConfig()
    extractor = CombinedExtractor(wbs_config)
    validator = ScreenshotValidator()

    # Test with Apple Books which should have both iPhone and iPad screenshots
    url = "https://apps.apple.com/us/app/apple-books/id364709193"

    print("\nTesting Screenshot Extraction and Validation")
    print("=" * 60)

    # Test 1: iTunes API extraction
    print("\n1. iTunes API Screenshot Extraction:")
    print("-" * 40)

    result = await extractor.fetch_combined(url, skip_web_scraping=True)
    assert result.success, f"Failed to extract app data: {result.error}"

    metadata = result.app_metadata
    print(f"App: {metadata.name}")
    print(f"iPhone Screenshots: {len(metadata.screenshots)}")
    print(f"iPad Screenshots: {len(metadata.ipad_screenshots)}")

    # Validate iPhone screenshots
    print("\n2. iPhone Screenshot Validation:")
    print("-" * 40)

    if metadata.screenshots:
        # Check first screenshot URL resolution
        first_url = str(metadata.screenshots[0])
        url_resolution = validator.extract_resolution_from_url(first_url)
        print(f"First iPhone screenshot URL: {first_url}")
        print(f"Resolution from URL: {url_resolution}")

        # Download and validate actual image
        print("\nDownloading first iPhone screenshot...")
        image = validator.download_image(first_url)
        assert image is not None, "Failed to download iPhone screenshot"

        actual_resolution = image.size
        print(f"Actual image resolution: {actual_resolution}")
        device_type = validator.validate_device_type(
            actual_resolution[0], actual_resolution[1]
        )
        print(f"Device type validation: {device_type}")

        assert "iPhone" in device_type, f"Expected iPhone screenshot, got {device_type}"
        print("✓ iPhone screenshot validation passed")

    # Validate iPad screenshots
    print("\n3. iPad Screenshot Validation:")
    print("-" * 40)

    if metadata.ipad_screenshots:
        # Check first iPad screenshot
        first_url = str(metadata.ipad_screenshots[0])
        url_resolution = validator.extract_resolution_from_url(first_url)
        print(f"First iPad screenshot URL: {first_url}")
        print(f"Resolution from URL: {url_resolution}")

        # Download and validate actual image
        print("\nDownloading first iPad screenshot...")
        image = validator.download_image(first_url)
        assert image is not None, "Failed to download iPad screenshot"

        actual_resolution = image.size
        print(f"Actual image resolution: {actual_resolution}")
        device_type = validator.validate_device_type(
            actual_resolution[0], actual_resolution[1]
        )
        print(f"Device type validation: {device_type}")

        assert "iPad" in device_type, f"Expected iPad screenshot, got {device_type}"
        print("✓ iPad screenshot validation passed")
    else:
        print("No iPad screenshots found in iTunes API")


@pytest.mark.asyncio
async def test_web_scraping_screenshots():
    """Test screenshot extraction via web scraping."""
    wbs_config = WBSConfig()
    extractor = CombinedExtractor(wbs_config)
    validator = ScreenshotValidator()

    # Test with an app that might have different screenshots on web
    url = "https://apps.apple.com/us/app/procreate/id425073498"

    print("\n\n4. Web Scraping Screenshot Test:")
    print("=" * 60)

    # Clear cache to force web scraping
    extractor.cache.clear()

    result = await extractor.fetch_combined(url, skip_web_scraping=False)
    assert result.success, f"Failed to extract app data: {result.error}"

    metadata = result.app_metadata
    print(f"App: {metadata.name}")
    print(f"Data sources: {', '.join([ds.value for ds in result.data_sources_used])}")
    print(f"iPhone Screenshots: {len(metadata.screenshots)}")
    print(f"iPad Screenshots: {len(metadata.ipad_screenshots)}")

    # Validate at least one screenshot from web scraping
    if metadata.screenshots:
        url_to_test = str(metadata.screenshots[0])
        print(f"\nValidating web-scraped screenshot: {url_to_test[:80]}...")

        image = validator.download_image(url_to_test)
        if image:
            resolution = image.size
            device_type = validator.validate_device_type(resolution[0], resolution[1])
            print(f"Resolution: {resolution}, Device: {device_type}")
            assert "iPhone" in device_type or "Unknown" not in device_type


@pytest.mark.asyncio
async def test_app_without_ipad_support():
    """Test app that only has iPhone screenshots."""
    wbs_config = WBSConfig()
    extractor = CombinedExtractor(wbs_config)

    # WhatsApp is iPhone-only
    url = "https://apps.apple.com/us/app/whatsapp-messenger/id310633997"

    print("\n\n5. iPhone-Only App Test:")
    print("=" * 60)

    result = await extractor.fetch_combined(url, skip_web_scraping=True)
    assert result.success

    metadata = result.app_metadata
    print(f"App: {metadata.name}")
    print(f"iPhone Screenshots: {len(metadata.screenshots)}")
    print(f"iPad Screenshots: {len(metadata.ipad_screenshots)}")

    assert len(metadata.screenshots) > 0, "Should have iPhone screenshots"
    assert len(metadata.ipad_screenshots) == 0, "Should not have iPad screenshots"
    print("✓ iPhone-only app correctly identified")


def test_resolution_detection():
    """Unit test for resolution detection logic."""
    validator = ScreenshotValidator()

    print("\n\n6. Resolution Detection Unit Tests:")
    print("=" * 60)

    test_cases = [
        # (width, height, expected_device)
        (1320, 2868, "iPhone"),  # 6.9" iPhone
        (2048, 2732, "iPad"),  # 12.9" iPad
        (392, 696, "iPhone"),  # iPhone thumbnail
        (576, 768, "iPad"),  # iPad thumbnail
        (1000, 1000, "Unknown"),  # Square (unusual)
    ]

    for width, height, expected in test_cases:
        result = validator.validate_device_type(width, height)
        print(f"{width}x{height} -> {result}")
        assert (
            expected in result
        ), f"Expected {expected} for {width}x{height}, got {result}"

    print("✓ All resolution detection tests passed")


def test_url_resolution_extraction():
    """Test extracting resolution from App Store URLs."""
    validator = ScreenshotValidator()

    print("\n\n7. URL Resolution Extraction Tests:")
    print("=" * 60)

    test_urls = [
        ("https://example.com/image/392x696bb.png", (392, 696)),
        ("https://example.com/image/2048x2732bb.jpg", (2048, 2732)),
        ("https://example.com/image/no-resolution.png", None),
    ]

    for url, expected in test_urls:
        result = validator.extract_resolution_from_url(url)
        print(f"URL: {url}")
        print(f"Extracted: {result}")
        assert result == expected, f"Expected {expected}, got {result}"

    print("✓ All URL extraction tests passed")


@pytest.mark.asyncio
async def test_batch_screenshot_validation():
    """Test multiple apps to ensure consistent screenshot handling."""
    wbs_config = WBSConfig()
    extractor = CombinedExtractor(wbs_config)

    print("\n\n8. Batch Screenshot Validation:")
    print("=" * 60)

    apps = [
        ("Pages", "https://apps.apple.com/us/app/pages/id409201541"),
        ("GoodNotes", "https://apps.apple.com/us/app/goodnotes-5/id1444383602"),
        ("Notability", "https://apps.apple.com/us/app/notability/id360593530"),
    ]

    results = []
    for name, app_url in apps:
        result = await extractor.fetch_combined(app_url, skip_web_scraping=True)
        if result.success:
            m = result.app_metadata
            results.append(
                {
                    "name": name,
                    "iphone_count": len(m.screenshots),
                    "ipad_count": len(m.ipad_screenshots),
                }
            )

    # Display results
    print(f"{'App':<15} | {'iPhone':<7} | {'iPad':<7}")
    print("-" * 35)
    for r in results:
        print(f"{r['name']:<15} | {r['iphone_count']:<7} | {r['ipad_count']:<7}")

    # At least some apps should have both types
    has_both = any(r["iphone_count"] > 0 and r["ipad_count"] > 0 for r in results)
    assert has_both, "At least one app should have both iPhone and iPad screenshots"
    print("\n✓ Batch validation completed successfully")


if __name__ == "__main__":
    # Run all tests
    print("Running Screenshot Validation Tests")
    print("=" * 80)

    # Run async tests
    asyncio.run(test_screenshot_extraction_and_validation())
    asyncio.run(test_web_scraping_screenshots())
    asyncio.run(test_app_without_ipad_support())
    asyncio.run(test_batch_screenshot_validation())

    # Run sync tests
    test_resolution_detection()
    test_url_resolution_extraction()

    print("\n\n✅ All screenshot validation tests completed successfully!")
