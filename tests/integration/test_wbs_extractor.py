"""
Test script for WBS-based App Store Metadata Extractor
"""

import asyncio
import json
from datetime import UTC, datetime

import pytest

from appstore_metadata_extractor.wbs_extractor import (
    ExtractionMode,
    WBSConfig,
    WBSMetadataExtractor,
)


@pytest.mark.asyncio
async def test_wbs_extractor():
    print("WBS Framework App Store Metadata Extractor")
    print("=" * 60)

    # Define WBS configuration
    config = WBSConfig(
        purpose="Track competing messaging apps metadata",
        target_apps=[
            "https://apps.apple.com/us/app/whatsapp-messenger/id310633997",
            "https://apps.apple.com/us/app/telegram-messenger/id686449807",
            "https://apps.apple.com/us/app/signal-private-messenger/id874139669",
        ],
        boundaries=WBSConfig.Boundaries(
            required_fields={
                "app_id",
                "name",
                "current_version",
                "developer_name",
                "price",
                "rating_count",
            },
            optional_fields={"subtitle", "in_app_purchases", "release_notes"},
            max_concurrent_requests=3,
            max_cache_age_seconds=300,  # 5 minutes
        ),
        success_criteria=WBSConfig.SuccessCriteria(
            min_required_fields_ratio=1.0,  # All required fields must be present
            min_optional_fields_ratio=0.5,  # At least half of optional fields
            min_extraction_success_rate=0.9,  # 90% success rate
            detect_version_changes=True,
        ),
    )

    extractor = WBSMetadataExtractor(config)

    print("\n1. Testing single app extraction with WBS validation:")
    print("-" * 50)

    # Test single app
    whatsapp_url = config.target_apps[0]
    result = await extractor.extract_with_wbs(
        whatsapp_url, mode=ExtractionMode.COMPLETE
    )

    if result.success and result.metadata:
        print(f"✓ App: {result.metadata.name}")
        print(f"✓ Version: {result.metadata.current_version}")
        print(f"✓ Extraction Time: {result.extraction_duration_seconds:.2f}s")
        print(f"✓ Data Source: {result.data_source}")
        print("\nWBS Compliance:")
        print(f"  • Meets Boundaries: {'✓' if result.meets_boundaries else '✗'}")
        print(
            f"  • Meets Success Criteria: {'✓' if result.meets_success_criteria else '✗'}"
        )
        print(
            f"  • Required Fields: {len(result.required_fields_present)}/{len(config.boundaries.required_fields)}"
        )
        print(
            f"  • Optional Fields: {len(result.optional_fields_present)}/{len(config.boundaries.optional_fields)}"
        )

        if result.warnings:
            print(f"  • Warnings: {', '.join(result.warnings)}")
    else:
        print(f"✗ Extraction failed: {', '.join(result.errors)}")

    print("\n2. Testing batch extraction with WBS compliance:")
    print("-" * 50)

    # Test batch extraction
    results = await extractor.extract_batch_with_wbs(
        config.target_apps, mode=ExtractionMode.SMART
    )

    # Display results
    print("\nExtraction Results:")
    print(f"{'App Name':<20} {'Version':<10} {'WBS Compliant':<15} {'Time (s)':<10}")
    print("-" * 60)

    for url, result in results.items():
        if result.success and result.metadata:
            compliant = (
                "✓"
                if (result.meets_boundaries and result.meets_success_criteria)
                else "✗"
            )
            print(
                f"{result.metadata.name:<20} {result.metadata.current_version:<10} {compliant:<15} {result.extraction_duration_seconds:<10.2f}"
            )
        else:
            app_name = f"App {result.app_id}" if result.app_id else "Unknown"
            print(
                f"{app_name:<20} {'Failed':<10} {'✗':<15} {result.extraction_duration_seconds:<10.2f}"
            )

    # Validate overall WBS compliance
    print("\n3. Overall WBS Compliance Report:")
    print("-" * 50)

    compliance_report = extractor.validate_wbs_compliance(results)

    print(f"✓ WBS Compliant: {'Yes' if compliance_report['wbs_compliant'] else 'No'}")
    print(f"✓ Success Rate: {compliance_report['success_rate']:.1%}")
    print(f"✓ Boundary Compliance: {compliance_report['boundary_compliance_rate']:.1%}")
    print(f"✓ Criteria Compliance: {compliance_report['criteria_compliance_rate']:.1%}")

    if compliance_report["violations"]:
        print("\nViolations found:")
        for violation in compliance_report["violations"]:
            print(
                f"  • App {violation['app_id']}: {', '.join(violation['errors'] or violation['warnings'])}"
            )

    # Test caching behavior
    print("\n4. Testing cache behavior (second extraction should be faster):")
    print("-" * 50)

    start_time = datetime.now(UTC)
    cached_result = await extractor.extract_with_wbs(
        whatsapp_url, mode=ExtractionMode.COMPLETE
    )
    cache_time = (datetime.now(UTC) - start_time).total_seconds()

    print(f"✓ First extraction: {result.extraction_duration_seconds:.2f}s")
    print(f"✓ Cached extraction: {cache_time:.2f}s")
    print(
        f"✓ Cache hit: {'Yes' if 'cache' in ' '.join(cached_result.warnings).lower() else 'No'}"
    )

    # Save WBS report
    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "config": {
            "purpose": config.purpose,
            "boundaries": {
                "required_fields": list(config.boundaries.required_fields),
                "optional_fields": list(config.boundaries.optional_fields),
                "rate_limits": {
                    "itunes_api": config.boundaries.itunes_api_rate_limit,
                    "web_scrape_delay": config.boundaries.web_scrape_delay,
                },
            },
            "success_criteria": {
                "min_required_fields_ratio": config.success_criteria.min_required_fields_ratio,
                "min_optional_fields_ratio": config.success_criteria.min_optional_fields_ratio,
                "min_extraction_success_rate": config.success_criteria.min_extraction_success_rate,
            },
        },
        "results": {
            url: {
                "success": r.success,
                "meets_boundaries": r.meets_boundaries,
                "meets_success_criteria": r.meets_success_criteria,
                "required_fields_present": list(r.required_fields_present),
                "optional_fields_present": list(r.optional_fields_present),
                "extraction_time": r.extraction_duration_seconds,
                "errors": r.errors,
                "warnings": r.warnings,
            }
            for url, r in results.items()
        },
        "compliance": compliance_report,
    }

    with open("wbs_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print("\n✓ WBS compliance report saved to wbs_report.json")

    # Demonstrate different extraction modes
    print("\n5. Comparing extraction modes:")
    print("-" * 50)

    for mode in [ExtractionMode.FAST, ExtractionMode.COMPLETE, ExtractionMode.SMART]:
        start = datetime.now(UTC)
        mode_result = await extractor.extract_with_wbs(whatsapp_url, mode=mode)
        duration = (datetime.now(UTC) - start).total_seconds()

        fields_count = len(mode_result.required_fields_present) + len(
            mode_result.optional_fields_present
        )
        print(
            f"{mode.value:<10} mode: {duration:.2f}s, {fields_count} fields extracted"
        )


if __name__ == "__main__":
    asyncio.run(test_wbs_extractor())
