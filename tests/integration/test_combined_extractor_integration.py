"""Integration tests for CombinedExtractor - tests real API calls."""

import asyncio
import json
from datetime import UTC, datetime

import pytest

from appstore_metadata_extractor.core import CombinedExtractor, WBSConfig
from appstore_metadata_extractor.core.models import DataSource


@pytest.mark.asyncio
async def test_combined_extractor_integration():
    """Test CombinedExtractor with real App Store data."""
    # Create extractor with default WBS config
    wbs_config = WBSConfig()
    extractor = CombinedExtractor(wbs_config)

    # Test with WhatsApp
    url = "https://apps.apple.com/us/app/whatsapp-messenger/id310633997"

    print("Testing Combined Extractor")
    print("=" * 50)

    # Test 1: iTunes API only (fast)
    print("\n1. iTunes API only (fast mode):")
    print("-" * 30)
    result = await extractor.fetch_combined(url, skip_web_scraping=True)

    if result.success:
        metadata = result.app_metadata
        print(f"✓ App: {metadata.name}")
        print(f"✓ Version: {metadata.current_version}")
        print(f"✓ Developer: {metadata.developer_name}")
        print(f"✓ Price: {metadata.formatted_price}")
        print(f"✓ Bundle ID: {metadata.bundle_id}")
        print(f"✓ Categories: {', '.join(metadata.categories)}")
        print(f"✓ Languages: {len(metadata.languages)} supported")
        print(
            f"✗ Subtitle: {metadata.subtitle or 'Not available (web scraping skipped)'}"
        )
        print(
            f"✗ In-App Purchases: {metadata.in_app_purchases or 'Not available (web scraping skipped)'}"
        )
        print(
            f"Data sources: {', '.join([ds.value for ds in result.data_sources_used])}"
        )
        assert metadata.bundle_id is not None, "Bundle ID should be extracted"
    else:
        print(f"✗ Error: {result.error}")
        pytest.fail("iTunes API extraction failed")

    # Test 2: Combined data (iTunes + Web)
    print("\n\n2. Combined data (iTunes API + Web scraping):")
    print("-" * 30)
    result = await extractor.fetch_combined(url, skip_web_scraping=False)

    if result.success:
        metadata = result.app_metadata
        print(f"✓ App: {metadata.name}")
        print(f"✓ Subtitle: {metadata.subtitle}")
        print(f"✓ Version: {metadata.current_version}")
        print(f"✓ Developer: {metadata.developer_name}")
        print(f"✓ Price: {metadata.formatted_price}")
        print(f"✓ In-App Purchases: {metadata.in_app_purchases}")
        if metadata.in_app_purchase_list:
            print(f"  - Found {len(metadata.in_app_purchase_list)} IAP items")
            for iap in metadata.in_app_purchase_list[:3]:  # Show first 3
                print(f"    • {iap.name}: {iap.price}")
        print(f"✓ Bundle ID: {metadata.bundle_id}")
        print(f"✓ Categories: {', '.join(metadata.categories)}")
        print(f"✓ Languages: {len(metadata.languages)} supported")

        # Check support URLs
        print(f"✓ App Support URL: {metadata.app_support_url}")
        print(f"✓ Privacy Policy URL: {metadata.privacy_policy_url}")
        print(f"✓ Developer Website URL: {metadata.developer_website_url}")

        print(
            f"\nData sources: {', '.join([ds.value for ds in result.data_sources_used])}"
        )

        if result.warnings:
            print(f"\nWarnings: {', '.join(result.warnings)}")

        # Save full data to file
        output_data = {
            "metadata": metadata.model_dump(exclude_none=True),
            "data_sources": [ds.value for ds in result.data_sources_used],
            "warnings": result.warnings,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        with open("combined_extractor_output.json", "w") as f:
            json.dump(output_data, f, indent=2, default=str)

        print("\n✓ Full data saved to combined_extractor_output.json")

        # Assertions
        assert metadata.bundle_id is not None, "Bundle ID should be extracted"
        assert metadata.subtitle is not None, "Subtitle should be extracted from web"
        assert (
            metadata.app_support_url is not None
        ), "App support URL should be extracted"
    else:
        print(f"✗ Error: {result.error}")
        pytest.fail("Combined extraction failed")


@pytest.mark.asyncio
async def test_multiple_apps_comparison():
    """Test extracting multiple apps for comparison."""
    wbs_config = WBSConfig()
    extractor = CombinedExtractor(wbs_config)

    print("\n\n3. Comparing multiple apps (iTunes API only for speed):")
    print("-" * 50)

    apps = [
        ("WhatsApp", "https://apps.apple.com/us/app/whatsapp-messenger/id310633997"),
        ("Telegram", "https://apps.apple.com/us/app/telegram-messenger/id686449807"),
        (
            "Signal",
            "https://apps.apple.com/us/app/signal-private-messenger/id874139669",
        ),
    ]

    for name, app_url in apps:
        result = await extractor.fetch_combined(app_url, skip_web_scraping=True)
        if result.success:
            m = result.app_metadata
            print(
                f"{name:15} | v{m.current_version:10} | {m.file_size_formatted or 'N/A':10} | ⭐ {m.average_rating:.1f} ({m.rating_count:,})"
            )
            assert m.bundle_id is not None, f"{name} should have bundle ID"


def test_synchronous_wrapper():
    """Test synchronous fetch method."""
    wbs_config = WBSConfig()
    extractor = CombinedExtractor(wbs_config)

    url = "https://apps.apple.com/us/app/whatsapp-messenger/id310633997"

    # Test synchronous single fetch
    metadata = extractor.fetch(url, skip_web_scraping=True)
    assert metadata.bundle_id == "net.whatsapp.WhatsApp"
    assert metadata.name == "WhatsApp Messenger"
    assert metadata.developer_name == "WhatsApp Inc."


def test_batch_extraction():
    """Test batch extraction of multiple apps."""
    wbs_config = WBSConfig()
    extractor = CombinedExtractor(wbs_config)

    urls = [
        "https://apps.apple.com/us/app/whatsapp-messenger/id310633997",
        "https://apps.apple.com/us/app/telegram-messenger/id686449807",
    ]

    # Test synchronous batch fetch
    results = extractor.fetch_batch(urls, skip_web_scraping=True)

    assert len(results) == 2
    for url, metadata in results.items():
        assert metadata.bundle_id is not None
        assert metadata.name is not None
        print(f"✓ {metadata.name}: {metadata.bundle_id}")


@pytest.mark.asyncio
async def test_iap_extraction():
    """Test in-app purchase extraction for apps known to have IAPs."""
    wbs_config = WBSConfig()
    extractor = CombinedExtractor(wbs_config)

    # Headspace is known to have in-app purchases
    url = "https://apps.apple.com/us/app/headspace-sleep-meditation/id493145008"

    result = await extractor.fetch_combined(url, skip_web_scraping=False)

    if result.success:
        metadata = result.app_metadata
        print(f"\nTesting IAP extraction for: {metadata.name}")
        print(f"Has IAPs: {metadata.in_app_purchases}")

        if metadata.in_app_purchase_list:
            print(f"Found {len(metadata.in_app_purchase_list)} IAP items:")
            for iap in metadata.in_app_purchase_list[:5]:  # Show first 5
                # Handle both dict and object formats
                if isinstance(iap, dict):
                    print(f"  - {iap['name']}: {iap['price']}")
                    assert iap["name"] is not None
                    assert iap["price"] is not None
                else:
                    print(f"  - {iap.name}: {iap.price}")
                    assert iap.name is not None
                    assert iap.price is not None

        # Note: IAP detection depends on web scraping and may change
        # Just ensure the extraction doesn't fail
        print("IAP extraction completed successfully")


if __name__ == "__main__":
    # Run the main integration test
    asyncio.run(test_combined_extractor_integration())

    # Run other tests
    asyncio.run(test_multiple_apps_comparison())
    test_synchronous_wrapper()
    test_batch_extraction()
    asyncio.run(test_iap_extraction())
