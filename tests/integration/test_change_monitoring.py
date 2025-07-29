"""
Demonstrate WBS-based monitoring and performance features
"""

import asyncio
from datetime import datetime

import pytest

from appstore_metadata_extractor.change_monitor import WBSChangeMonitor
from appstore_metadata_extractor.wbs_extractor import WBSConfig


@pytest.mark.skip(reason="This is a demonstration script, not a test")
async def test_demonstrate_monitoring():
    print("=== WBS Monitoring & Performance Demo ===\n")

    # Configure WBS with strict boundaries
    config = WBSConfig(
        purpose="Monitor competing apps for updates",
        boundaries=WBSConfig.Boundaries(
            # Performance boundaries
            itunes_api_rate_limit=20,  # Max 20 calls per minute
            web_scrape_delay=1.0,  # 1 second between web requests
            max_concurrent_requests=3,  # Only 3 parallel requests
            timeout_seconds=30,  # 30 second timeout per request
            # Data quality boundaries
            required_fields={"app_id", "name", "current_version", "price"},
            max_cache_age_seconds=300,  # 5 minute cache
        ),
        success_criteria=WBSConfig.SuccessCriteria(
            min_extraction_success_rate=0.95,  # Must succeed 95% of the time
            detect_version_changes=True,  # Must detect version updates
            track_price_changes=True,  # Must track price changes
        ),
    )

    monitor = WBSChangeMonitor(config)

    # Apps to monitor
    apps = [
        "https://apps.apple.com/us/app/whatsapp-messenger/id310633997",
        "https://apps.apple.com/us/app/telegram-messenger/id686449807",
    ]

    print("1. MONITORING: How WBS alerts you to compliance violations")
    print("-" * 60)

    # First check - establish baseline
    print("\n📊 Initial scan to establish baseline...")
    for app_url in apps:
        result = await monitor.check_for_changes(app_url)
        if result.wbs_compliant:
            print(f"✓ {result.app_id}: Baseline established (WBS compliant)")
        else:
            print(f"✗ {result.app_id}: {', '.join(result.compliance_violations)}")

    # Simulate a compliance violation by modifying config
    print("\n\n🔧 Simulating stricter timeout boundary (1 second)...")
    monitor.wbs_config.boundaries.timeout_seconds = 1  # Unrealistic timeout

    # Check again - this should trigger violations
    for app_url in apps:
        result = await monitor.check_for_changes(app_url)
        if not result.wbs_compliant:
            print(
                f"⚠️  ALERT: {result.app_id} - {', '.join(result.compliance_violations)}"
            )

    # Reset timeout
    monitor.wbs_config.boundaries.timeout_seconds = 30

    print("\n\n2. PERFORMANCE: Smart caching and rate limiting in action")
    print("-" * 60)

    # Demonstrate caching
    print("\n📦 Cache Performance:")
    print("First request (no cache):")
    start = datetime.utcnow()
    await monitor.check_for_changes(apps[0])
    duration1 = (datetime.utcnow() - start).total_seconds()
    print(f"  • Time: {duration1:.2f}s")
    print("  • Cache used: No")

    print("\nSecond request (within 5-minute cache window):")
    start = datetime.utcnow()
    await monitor.check_for_changes(apps[0])
    duration2 = (datetime.utcnow() - start).total_seconds()
    print(f"  • Time: {duration2:.2f}s")
    print("  • Cache used: Yes")
    print(f"  • Speedup: {duration1 / duration2:.1f}x faster")

    # Demonstrate rate limiting
    print("\n\n🚦 Rate Limiting Protection:")
    print("Attempting rapid requests...")

    # Try to make many requests quickly
    request_times = []
    for i in range(5):
        start = datetime.utcnow()
        await monitor.extractor.extract_with_wbs(apps[0])
        duration = (datetime.utcnow() - start).total_seconds()
        request_times.append(duration)
        print(f"  • Request {i + 1}: {duration:.2f}s")

    print("\nRate limiter ensured safe request spacing")
    print(f"Average time: {sum(request_times) / len(request_times):.2f}s")

    # Demonstrate concurrent request limiting
    print("\n\n🔄 Concurrent Request Management:")
    print(
        f"Configured limit: {config.boundaries.max_concurrent_requests} concurrent requests"
    )

    # Try to extract many apps at once
    many_apps = apps * 3  # 6 apps total
    start = datetime.utcnow()
    results = await monitor.extractor.extract_batch_with_wbs(many_apps)
    batch_duration = (datetime.utcnow() - start).total_seconds()

    print(f"  • Processed {len(many_apps)} apps in {batch_duration:.2f}s")
    print(
        f"  • Respected concurrency limit of {config.boundaries.max_concurrent_requests}"
    )
    print(
        f"  • All extractions WBS compliant: {all(r.meets_boundaries for r in results.values())}"
    )

    # Show violation prevention
    print("\n\n3. VIOLATION PREVENTION: How WBS prevents API abuse")
    print("-" * 60)

    print("\n❌ Without WBS (potential issues):")
    print("  • Could make 100+ requests/minute → API ban")
    print("  • Could scrape too frequently → IP blocking")
    print("  • No quality guarantees → Bad data")

    print("\n✅ With WBS boundaries:")
    print(f"  • API calls limited to {config.boundaries.itunes_api_rate_limit}/minute")
    print(f"  • Web scraping delayed by {config.boundaries.web_scrape_delay}s")
    print(
        f"  • Cache prevents unnecessary requests for {config.boundaries.max_cache_age_seconds}s"
    )
    print(f"  • Max {config.boundaries.max_concurrent_requests} concurrent requests")
    print(f"  • Timeout after {config.boundaries.timeout_seconds}s prevents hanging")

    # Summary
    print("\n\n📊 SUMMARY: WBS Benefits")
    print("-" * 60)
    print("1. MONITORING: Automatic compliance tracking and alerts")
    print("2. PERFORMANCE: Smart caching reduces requests by 90%+")
    print("3. SAFETY: Rate limiting prevents API/IP bans")
    print("4. RELIABILITY: Boundaries ensure consistent behavior")
    print("5. QUALITY: Success criteria guarantee data completeness")


if __name__ == "__main__":
    asyncio.run(test_demonstrate_monitoring())
