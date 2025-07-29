"""
Metadata Change Monitoring with WBS Framework
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

from .models_combined import AppMetadataCombined
from .wbs_extractor import ExtractionMode, WBSConfig, WBSMetadataExtractor


class MetadataChange(BaseModel):
    """Represents a detected change in app metadata"""

    app_id: str
    app_name: str
    field: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    change_type: str  # "added", "removed", "modified"
    detected_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def is_version_change(self) -> bool:
        return self.field == "current_version"

    @property
    def is_price_change(self) -> bool:
        return self.field == "price" or self.field == "formatted_price"


class ChangeDetectionResult(BaseModel):
    """Result of change detection with WBS compliance info"""

    app_id: str
    changes_detected: List[MetadataChange] = Field(default_factory=list)
    wbs_compliant: bool = True
    compliance_violations: List[str] = Field(default_factory=list)

    @property
    def has_critical_changes(self) -> bool:
        """Check if any critical changes (version, price) were detected"""
        return any(
            change.is_version_change or change.is_price_change
            for change in self.changes_detected
        )


class WBSChangeMonitor:
    """Monitor app metadata changes with WBS compliance tracking"""

    def __init__(self, wbs_config: WBSConfig, storage_path: str = "./metadata_history"):
        self.wbs_config = wbs_config
        self.extractor = WBSMetadataExtractor(wbs_config)
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)

        # Fields to monitor for changes
        self.monitored_fields = {
            # Critical fields - always alert
            "current_version",
            "price",
            "formatted_price",
            # Important fields - track changes
            "name",
            "subtitle",
            "developer_name",
            "rating_count",
            "average_rating",
            "description",
            "release_notes",
            # Optional fields
            "in_app_purchases",
            "file_size_formatted",
        }

    async def check_for_changes(self, app_url: str) -> ChangeDetectionResult:
        """Check an app for metadata changes"""
        app_id = self._extract_app_id(app_url)
        result = ChangeDetectionResult(app_id=app_id)

        # Extract current metadata with WBS validation
        extraction = await self.extractor.extract_with_wbs(
            app_url, mode=ExtractionMode.COMPLETE
        )

        # Check WBS compliance first
        if not extraction.meets_boundaries:
            result.wbs_compliant = False
            result.compliance_violations.append("Extraction failed boundary checks")

        if not extraction.meets_success_criteria:
            result.wbs_compliant = False
            result.compliance_violations.append("Extraction failed success criteria")

        # If extraction failed entirely, we can't check for changes
        if not extraction.success or not extraction.metadata:
            result.wbs_compliant = False
            result.compliance_violations.append(
                f"Extraction failed: {', '.join(extraction.errors)}"
            )
            return result

        current_metadata = extraction.metadata

        # Load previous metadata
        previous_metadata = self._load_previous_metadata(app_id)

        if previous_metadata:
            # Compare and detect changes
            changes = self._compare_metadata(previous_metadata, current_metadata)
            result.changes_detected = changes

            # Alert on critical changes
            if result.has_critical_changes:
                await self._send_alert(result, current_metadata)

        # Save current metadata for future comparisons
        self._save_metadata(app_id, current_metadata)

        return result

    async def monitor_apps_continuously(
        self,
        app_urls: List[str],
        check_interval_minutes: int = 60,
        max_iterations: Optional[int] = None,
    ) -> None:
        """Continuously monitor apps for changes"""
        iteration = 0

        while max_iterations is None or iteration < max_iterations:
            print(
                f"\n[{datetime.utcnow().isoformat()}] Starting monitoring iteration {iteration + 1}"
            )

            all_results = []
            for url in app_urls:
                try:
                    result = await self.check_for_changes(url)
                    all_results.append(result)

                    # Report findings
                    if result.changes_detected:
                        print(
                            f"\n✓ {result.app_id}: {len(result.changes_detected)} changes detected"
                        )
                        for change in result.changes_detected:
                            emoji = (
                                "🚨"
                                if change.is_version_change or change.is_price_change
                                else "📝"
                            )
                            print(
                                f"  {emoji} {change.field}: {change.old_value} → {change.new_value}"
                            )
                    else:
                        print(f"✓ {result.app_id}: No changes")

                    # Report compliance violations
                    if not result.wbs_compliant:
                        print(
                            f"  ⚠️  WBS Violations: {', '.join(result.compliance_violations)}"
                        )

                except Exception as e:
                    print(f"✗ Error monitoring {url}: {str(e)}")

            # Generate compliance report
            compliant_count = sum(1 for r in all_results if r.wbs_compliant)
            print(
                f"\n📊 Compliance: {compliant_count}/{len(all_results)} apps monitored successfully"
            )

            # Wait for next iteration
            iteration += 1
            if max_iterations is None or iteration < max_iterations:
                print(f"\n⏰ Next check in {check_interval_minutes} minutes...")
                await asyncio.sleep(check_interval_minutes * 60)

    def _compare_metadata(
        self, old: AppMetadataCombined, new: AppMetadataCombined
    ) -> List[MetadataChange]:
        """Compare two metadata objects and return list of changes"""
        changes = []

        for field in self.monitored_fields:
            if hasattr(old, field) and hasattr(new, field):
                old_value = getattr(old, field)
                new_value = getattr(new, field)

                # Convert to comparable strings
                old_str = str(old_value) if old_value is not None else None
                new_str = str(new_value) if new_value is not None else None

                if old_str != new_str:
                    change_type = "modified"
                    if old_str is None:
                        change_type = "added"
                    elif new_str is None:
                        change_type = "removed"

                    changes.append(
                        MetadataChange(
                            app_id=new.app_id,
                            app_name=new.name,
                            field=field,
                            old_value=old_str,
                            new_value=new_str,
                            change_type=change_type,
                        )
                    )

        return changes

    async def _send_alert(
        self, result: ChangeDetectionResult, metadata: AppMetadataCombined
    ) -> None:
        """Send alert for critical changes"""
        # In a real implementation, this could:
        # - Send email/Slack notifications
        # - Write to a monitoring dashboard
        # - Trigger webhooks
        # - Log to external monitoring system

        alert_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "app_id": result.app_id,
            "app_name": metadata.name,
            "critical_changes": [
                {
                    "field": change.field,
                    "old_value": change.old_value,
                    "new_value": change.new_value,
                    "is_version": change.is_version_change,
                    "is_price": change.is_price_change,
                }
                for change in result.changes_detected
                if change.is_version_change or change.is_price_change
            ],
            "all_changes_count": len(result.changes_detected),
            "wbs_compliant": result.wbs_compliant,
            "violations": result.compliance_violations,
        }

        # Save alert to file (in production, send to monitoring system)
        alert_file = (
            self.storage_path / f"alerts_{datetime.utcnow().strftime('%Y%m%d')}.jsonl"
        )
        with open(alert_file, "a") as f:
            f.write(json.dumps(alert_data) + "\n")

        print(f"\n🚨 ALERT: Critical changes detected for {metadata.name}!")

    def _load_previous_metadata(self, app_id: str) -> Optional[AppMetadataCombined]:
        """Load previous metadata from storage"""
        metadata_file = self.storage_path / f"{app_id}_metadata.json"
        if metadata_file.exists():
            with open(metadata_file, "r") as f:
                data = json.load(f)
                # Remove raw data to avoid reconstruction issues
                data.pop("raw_itunes_data", None)
                data.pop("raw_web_data", None)
                return AppMetadataCombined(**data)
        return None

    def _save_metadata(self, app_id: str, metadata: AppMetadataCombined) -> None:
        """Save metadata to storage"""
        metadata_file = self.storage_path / f"{app_id}_metadata.json"
        # Don't save raw data to reduce file size
        data = metadata.model_dump(exclude={"raw_itunes_data", "raw_web_data"})
        with open(metadata_file, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def _extract_app_id(self, url: str) -> str:
        """Extract app ID from URL"""
        import re

        match = re.search(r"/id(\d+)", url)
        return match.group(1) if match else url
