#!/usr/bin/env python3
"""
Basic usage example for appstore-metadata-extractor
"""

from appstore_metadata_extractor import AppStoreScraper


def main():
    # Initialize the scraper
    scraper = AppStoreScraper()

    # Example App Store URL
    url = "https://apps.apple.com/us/app/github/id1477376905"

    # Extract metadata
    print("Extracting metadata...")
    metadata = scraper.extract(url)

    # Display results
    print(f"\nApp: {metadata.title}")
    print(f"Developer: {metadata.developer}")
    print(f"Version: {metadata.version}")
    print(f"Rating: {metadata.rating} ({metadata.ratings_count} ratings)")
    print(f"Price: {metadata.price}")
    print(f"Category: {metadata.category}")
    print(f"Last Updated: {metadata.release_date}")

    # Access description
    if metadata.description:
        print("\nDescription (first 200 chars):")
        print(metadata.description[:200] + "...")


if __name__ == "__main__":
    main()
