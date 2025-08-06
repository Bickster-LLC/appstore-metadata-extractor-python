# \!/usr/bin/env python3
"""
Basic usage example for appstore-metadata-extractor.

This script demonstrates how to use the package to extract app metadata.
"""

from appstore_metadata_extractor import CombinedExtractor, WBSConfig


def main():
    """Run basic extraction example."""
    # Initialize with default configuration
    config = WBSConfig()
    extractor = CombinedExtractor(config)

    # Example App Store URLs
    urls = [
        "https://apps.apple.com/us/app/whatsapp-messenger/id310633997",
        "https://apps.apple.com/us/app/chatgpt/id6448311069",
    ]

    print("App Store Metadata Extractor - Basic Example")
    print("=" * 50)

    for url in urls:
        print(f"\nExtracting metadata for: {url}")
        print("-" * 50)

        try:
            # Extract metadata (uses both iTunes API and web scraping)
            metadata = extractor.fetch(url)

            # Display basic information
            print(f"📱 App Name: {metadata.name}")
            print(f"👤 Developer: {metadata.developer_name}")
            print(f"📌 Version: {metadata.current_version}")
            print(f"💰 Price: {metadata.formatted_price}")
            print(
                f"⭐ Rating: {metadata.average_rating:.1f}/5.0 ({metadata.rating_count:,} ratings)"
            )

            # Additional data from web scraping
            if metadata.subtitle:
                print(f"📝 Subtitle: {metadata.subtitle}")

            # Screenshots
            print(f"🖼️  Screenshots: {len(metadata.screenshots)}")

            # In-App Purchases
            if metadata.in_app_purchases:
                print(f"💳 In-App Purchases: Yes")
                if metadata.in_app_purchase_list:
                    print(f"   - {len(metadata.in_app_purchase_list)} items available")
                    for iap in metadata.in_app_purchase_list[:3]:  # Show first 3
                        print(f"   - {iap.name}: {iap.price}")
            else:
                print(f"💳 In-App Purchases: No")

            # Languages
            if metadata.languages:
                print(f"🌍 Languages: {len(metadata.languages)} supported")
                print(f"   - {', '.join(metadata.languages[:5])}")
                if len(metadata.languages) > 5:
                    print(f"   - and {len(metadata.languages) - 5} more...")

        except Exception as e:
            print(f"❌ Error extracting metadata: {e}")

    # Demonstrate iTunes-only mode (faster)
    print("\n\n" + "=" * 50)
    print("iTunes API Only Mode (faster, less data)")
    print("=" * 50)

    url = urls[0]
    print(f"\nExtracting (iTunes only): {url}")

    try:
        # Skip web scraping for faster extraction
        metadata = extractor.fetch(url, skip_web_scraping=True)

        print(f"📱 App Name: {metadata.name}")
        print(f"📌 Version: {metadata.current_version}")
        print(f"🖼️  Screenshots: {len(metadata.screenshots)}")
        print(
            f"📝 Subtitle: {metadata.subtitle or 'Not available (web scraping skipped)'}"
        )
        print(
            f"💳 IAPs: {metadata.in_app_purchases or 'Not available (web scraping skipped)'}"
        )

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
