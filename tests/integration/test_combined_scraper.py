import asyncio
import json
from datetime import UTC, datetime

import pytest

from appstore_metadata_extractor.combined_scraper import CombinedAppStoreScraper


@pytest.mark.asyncio
async def test_combined_scraper():
    scraper = CombinedAppStoreScraper()

    # Test with WhatsApp
    url = "https://apps.apple.com/us/app/whatsapp-messenger/id310633997"

    print("Testing Combined Scraper")
    print("=" * 50)

    # Test 1: iTunes API only (fast)
    print("\n1. iTunes API only (fast mode):")
    print("-" * 30)
    result = await scraper.fetch_combined(url, skip_web_scraping=True)

    if result.success:
        metadata = result.app_metadata
        print(f"✓ App: {metadata.name}")
        print(f"✓ Version: {metadata.current_version}")
        print(f"✓ Developer: {metadata.developer_name}")
        print(f"✓ Price: {metadata.formatted_price}")
        print(
            f"✓ Rating: {metadata.average_rating} ({metadata.rating_count:,} ratings)"
        )
        print(f"✓ File Size: {metadata.file_size_formatted}")
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
    else:
        print(f"✗ Error: {result.error}")

    # Test 2: Combined data (iTunes + Web)
    print("\n\n2. Combined data (iTunes API + Web scraping):")
    print("-" * 30)
    result = await scraper.fetch_combined(url, skip_web_scraping=False)

    if result.success:
        metadata = result.app_metadata
        print(f"✓ App: {metadata.name}")
        print(f"✓ Subtitle: {metadata.subtitle}")
        print(f"✓ Version: {metadata.current_version}")
        print(f"✓ Release Date: {metadata.current_version_release_date}")
        print(f"✓ Developer: {metadata.developer_name}")
        print(f"✓ Price: {metadata.formatted_price}")
        print(f"✓ In-App Purchases: {metadata.in_app_purchases}")
        print(
            f"✓ Rating: {metadata.average_rating} ({metadata.rating_count:,} ratings)"
        )
        print(f"✓ File Size: {metadata.file_size_formatted}")
        print(f"✓ Bundle ID: {metadata.bundle_id}")
        print(f"✓ Categories: {', '.join(metadata.categories)}")
        print(f"✓ Languages: {len(metadata.languages)} supported")

        if metadata.privacy:
            print(
                f"✓ Privacy data available: {len(metadata.privacy.data_used_to_track)} tracking categories"
            )

        if metadata.similar_apps:
            print(f"✓ Similar apps: {len(metadata.similar_apps)} found")

        if metadata.developer_apps:
            print(f"✓ Developer's other apps: {len(metadata.developer_apps)} found")

        print(
            f"\nData sources: {', '.join([ds.value for ds in result.data_sources_used])}"
        )

        if result.warnings:
            print(f"\nWarnings: {', '.join(result.warnings)}")

        # Save full data to file
        output_data = {
            "metadata": metadata.model_dump(
                exclude={"raw_itunes_data", "raw_web_data"}
            ),
            "data_sources": [ds.value for ds in result.data_sources_used],
            "warnings": result.warnings,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        with open("combined_output.json", "w") as f:
            json.dump(output_data, f, indent=2, default=str)

        print("\n✓ Full data saved to combined_output.json")

        # Show what's new
        if metadata.release_notes:
            print(f"\nWhat's New in v{metadata.current_version}:")
            print("-" * 30)
            print(
                metadata.release_notes[:200] + "..."
                if len(metadata.release_notes) > 200
                else metadata.release_notes
            )
    else:
        print(f"✗ Error: {result.error}")

    # Test 3: Multiple apps comparison
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
        result = await scraper.fetch_combined(app_url, skip_web_scraping=True)
        if result.success:
            m = result.app_metadata
            print(
                f"{name:15} | v{m.current_version:10} | {m.file_size_formatted:10} | ⭐ {m.average_rating:.1f} ({m.rating_count:,})"
            )


if __name__ == "__main__":
    asyncio.run(test_combined_scraper())
