#!/usr/bin/env python3
"""
Monitor apps for version changes example
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from appstore_metadata_extractor import CombinedExtractor


class AppMonitor:
    def __init__(self, history_dir: str = "app_history"):
        self.extractor = CombinedExtractor()
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(exist_ok=True)

    async def check_app(self, url: str, app_name: str) -> dict:
        """Check a single app for changes"""
        # Extract current metadata
        result = await self.extractor.extract(url)

        if not result.success:
            return {"app": app_name, "status": "error", "error": str(result.error)}

        metadata = result.metadata
        history_file = self.history_dir / f"{app_name.replace(' ', '_')}.json"

        # Load previous data if exists
        previous_version = None
        if history_file.exists():
            with open(history_file) as f:
                history = json.load(f)
                previous_version = history.get("version")

        # Check for version change
        version_changed = previous_version and previous_version != metadata.version

        # Save current data
        current_data = {
            "app_name": app_name,
            "url": url,
            "version": metadata.version,
            "previous_version": previous_version,
            "last_checked": datetime.now().isoformat(),
            "rating": metadata.rating,
            "ratings_count": metadata.ratings_count,
            "release_date": metadata.release_date,
        }

        with open(history_file, "w") as f:
            json.dump(current_data, f, indent=2)

        return {
            "app": app_name,
            "status": "updated" if version_changed else "unchanged",
            "current_version": metadata.version,
            "previous_version": previous_version,
            "version_changed": version_changed,
        }

    async def monitor_apps(self, apps: list) -> list:
        """Monitor multiple apps for changes"""
        tasks = [self.check_app(app["url"], app["name"]) for app in apps]
        return await asyncio.gather(*tasks)


async def main():
    # Apps to monitor
    apps_to_monitor = [
        {"name": "GitHub", "url": "https://apps.apple.com/us/app/github/id1477376905"},
        {"name": "Slack", "url": "https://apps.apple.com/us/app/slack/id618783545"},
        {"name": "Notion", "url": "https://apps.apple.com/us/app/notion/id1232780281"},
    ]

    monitor = AppMonitor()

    print("🔍 Checking apps for updates...")
    results = await monitor.monitor_apps(apps_to_monitor)

    # Display results
    print("\n📊 Monitoring Results:")
    print("-" * 50)

    for result in results:
        if result["status"] == "error":
            print(f"❌ {result['app']}: Error - {result['error']}")
        elif result["status"] == "updated":
            print(f"🆕 {result['app']}: VERSION UPDATED!")
            print(f"   {result['previous_version']} → {result['current_version']}")
        else:
            print(f"✅ {result['app']}: No changes (v{result['current_version']})")

    print("\nHistory saved in ./app_history/")


if __name__ == "__main__":
    asyncio.run(main())
