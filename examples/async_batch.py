#!/usr/bin/env python3
"""
Async batch extraction example for appstore-metadata-extractor
"""

import asyncio
import json
from typing import List

from appstore_metadata_extractor import CombinedExtractor


async def extract_apps(urls: List[str]):
    """Extract metadata for multiple apps concurrently"""
    extractor = CombinedExtractor()

    print(f"Extracting metadata for {len(urls)} apps...")

    # Extract all apps concurrently
    results = await extractor.extract_batch(urls, max_concurrent=3)

    # Process results
    successful = []
    failed = []

    for url, result in results.items():
        if result.success:
            successful.append(
                {
                    "url": url,
                    "title": result.metadata.title,
                    "version": result.metadata.version,
                    "rating": result.metadata.rating,
                    "developer": result.metadata.developer,
                }
            )
        else:
            failed.append({"url": url, "error": str(result.error)})

    return successful, failed


async def main():
    # Example app URLs
    urls = [
        "https://apps.apple.com/us/app/github/id1477376905",
        "https://apps.apple.com/us/app/slack/id618783545",
        "https://apps.apple.com/us/app/notion/id1232780281",
        "https://apps.apple.com/us/app/spotify/id324684580",
        "https://apps.apple.com/us/app/discord/id985746746",
    ]

    # Extract metadata
    successful, failed = await extract_apps(urls)

    # Display results
    print(f"\n✅ Successfully extracted: {len(successful)} apps")
    for app in successful:
        print(f"  - {app['title']} (v{app['version']}) - ⭐ {app['rating']}")

    if failed:
        print(f"\n❌ Failed to extract: {len(failed)} apps")
        for failure in failed:
            print(f"  - {failure['url']}: {failure['error']}")

    # Save to JSON
    output = {
        "successful": successful,
        "failed": failed,
        "summary": {
            "total": len(urls),
            "successful": len(successful),
            "failed": len(failed),
        },
    }

    with open("extraction_results.json", "w") as f:
        json.dump(output, f, indent=2)

    print("\nResults saved to extraction_results.json")


if __name__ == "__main__":
    asyncio.run(main())
