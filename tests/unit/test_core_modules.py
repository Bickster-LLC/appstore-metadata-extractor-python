#!/usr/bin/env python3
"""Test script to verify core module refactoring works correctly."""

import asyncio

import pytest

from appstore_metadata_extractor import CombinedExtractor, WBSConfig, WBSValidator


@pytest.mark.asyncio
async def test_core_extraction():
    """Test the refactored core extraction functionality."""

    # Create WBS configuration
    wbs_config = WBSConfig(
        what="Test core module extraction",
        boundaries={
            "itunes_api_rate_limit": 20,
            "web_scrape_delay": 1.0,
            "required_fields": {
                "app_id",
                "name",
                "current_version",
                "developer_name",
                "icon_url",
            },
            "timeout_seconds": 30,
        },
        success={
            "min_extraction_success_rate": 0.95,
            "max_response_time_seconds": 30.0,
        },
    )

    # Create extractor
    extractor = CombinedExtractor(wbs_config)

    # Test URLs
    test_urls = [
        "https://apps.apple.com/us/app/facebook/id284882215",
        "https://apps.apple.com/us/app/whatsapp-messenger/id310633997",
    ]

    for url in test_urls:
        print(f"\n{'=' * 60}")
        print(f"Testing: {url}")
        print("=" * 60)

        try:
            # Extract with validation
            result = await extractor.extract_with_validation(url)

            # Print results
            print(f"Success: {result.success}")
            print(f"WBS Compliant: {result.wbs_compliant}")
            print(f"Data Source: {result.data_source}")
            print(f"Extraction Time: {result.extraction_duration_seconds:.2f}s")

            if result.metadata:
                print("\nExtracted Metadata:")
                print(f"  Name: {result.metadata.name}")
                print(f"  Version: {result.metadata.current_version}")
                print(f"  Developer: {result.metadata.developer_name}")
                print(f"  Price: {result.metadata.formatted_price}")
                print(f"  Rating: {result.metadata.average_rating}")

            print("\nField Coverage:")
            print(
                f"  Required fields: {len(result.required_fields_present)}/{len(wbs_config.boundaries.required_fields)}"
            )
            print(
                f"  Optional fields: {len(result.optional_fields_present)}/{len(wbs_config.boundaries.optional_fields)}"
            )

            if result.wbs_violations:
                print("\nWBS Violations:")
                for violation in result.wbs_violations:
                    print(f"  - {violation}")

            if result.errors:
                print("\nErrors:")
                for error in result.errors:
                    print(f"  - {error}")

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback

            traceback.print_exc()

    # Test WBS report generation
    print(f"\n{'=' * 60}")
    print("WBS Compliance Report Example")
    print("=" * 60)

    if "result" in locals() and result:
        validator = WBSValidator(wbs_config)
        report = validator.get_wbs_report(result)

        import json

        print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(test_core_extraction())
