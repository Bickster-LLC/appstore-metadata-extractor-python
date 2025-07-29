"""
App Store Metadata Extractor using WBS (What-Boundaries-Success) Framework
"""

import asyncio
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field, field_validator

from .combined_scraper import CombinedAppStoreScraper
from .models_combined import AppMetadataCombined, DataSource


class ExtractionMode(str, Enum):
    FAST = "fast"  # iTunes API only
    COMPLETE = "complete"  # iTunes + Web scraping
    SMART = "smart"  # Decide based on requirements


class WBSConfig(BaseModel):
    """Configuration defining the What-Boundaries-Success framework"""

    # WHAT: Core purpose configuration
    purpose: str = "Track competing app metadata changes"
    target_apps: List[str] = Field(
        default_factory=list, description="App IDs or URLs to track"
    )

    # BOUNDARIES: System constraints
    class Boundaries(BaseModel):
        # Rate limiting
        itunes_api_rate_limit: int = Field(
            default=20, description="Max API calls per minute"
        )
        web_scrape_delay: float = Field(
            default=1.0, description="Seconds between web requests"
        )

        # Data freshness
        max_cache_age_seconds: int = Field(
            3600, description="Maximum age for cached data"
        )
        min_update_interval_seconds: int = Field(
            300, description="Minimum time between updates"
        )

        # Field requirements
        required_fields: Set[str] = Field(
            default={"app_id", "name", "current_version", "developer_name", "price"},
            description="Fields that must be present",
        )
        optional_fields: Set[str] = Field(
            default={"subtitle", "privacy", "reviews", "similar_apps"},
            description="Fields that are nice to have",
        )

        # Resource limits
        max_concurrent_requests: int = Field(
            default=5, description="Max parallel requests"
        )
        max_retries: int = Field(default=3, description="Max retry attempts")
        timeout_seconds: int = Field(default=30, description="Request timeout")

    boundaries: Boundaries = Field(
        default_factory=lambda: WBSConfig.Boundaries(
            max_cache_age_seconds=3600, min_update_interval_seconds=300
        )
    )

    # SUCCESS: Criteria for valid outcomes
    class SuccessCriteria(BaseModel):
        # Completeness requirements
        min_required_fields_ratio: float = Field(
            default=1.0, description="All required fields must be present"
        )
        min_optional_fields_ratio: float = Field(
            default=0.5, description="At least half of optional fields"
        )

        # Quality requirements
        min_extraction_success_rate: float = Field(
            default=0.95, description="95% success rate"
        )
        max_error_rate: float = Field(default=0.05, description="Max 5% errors allowed")

        # Tracking requirements
        detect_version_changes: bool = Field(
            default=True, description="Must detect version updates"
        )
        track_price_changes: bool = Field(
            default=True, description="Must track price changes"
        )

        @field_validator("min_extraction_success_rate")
        @classmethod
        def validate_success_rate(cls, v: float) -> float:
            if not 0 <= v <= 1:
                raise ValueError("Success rate must be between 0 and 1")
            return v

    success_criteria: SuccessCriteria = Field(
        default_factory=lambda: WBSConfig.SuccessCriteria()
    )


class ExtractionResult(BaseModel):
    """Result of a WBS-compliant extraction"""

    app_id: str
    metadata: Optional[AppMetadataCombined] = None
    success: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    # WBS compliance
    meets_boundaries: bool = Field(
        False, description="Whether boundaries were respected"
    )
    meets_success_criteria: bool = Field(
        False, description="Whether success criteria were met"
    )
    required_fields_present: Set[str] = Field(default_factory=set)
    optional_fields_present: Set[str] = Field(default_factory=set)

    extraction_duration_seconds: float = 0.0
    data_source: Optional[DataSource] = None


class WBSMetadataExtractor:
    """App Store metadata extractor implementing WBS framework"""

    def __init__(self, config: WBSConfig):
        self.config = config
        self.scraper = CombinedAppStoreScraper(
            timeout=config.boundaries.timeout_seconds
        )
        self._rate_limiter = RateLimiter(
            itunes_limit=config.boundaries.itunes_api_rate_limit,
            web_delay=config.boundaries.web_scrape_delay,
        )
        self._cache: Dict[str, Any] = {}  # Simple in-memory cache

    async def extract_with_wbs(
        self, app_url: str, mode: ExtractionMode = ExtractionMode.SMART
    ) -> ExtractionResult:
        """Extract metadata following WBS principles"""
        start_time = datetime.now(UTC)
        result = ExtractionResult(
            app_id=self._extract_app_id(app_url),
            success=False,  # Will be updated if extraction succeeds
            meets_boundaries=False,  # Will be updated
            meets_success_criteria=False,  # Will be updated
        )

        try:
            # Check boundaries: Rate limiting
            await self._rate_limiter.check_and_wait()

            # Check boundaries: Cache freshness
            cached = self._get_from_cache(app_url)
            if cached and self._is_cache_valid(cached):
                result.metadata = cached["metadata"]
                result.success = True
                result.data_source = DataSource.COMBINED
                result.warnings.append("Served from cache")
            else:
                # Determine extraction mode based on requirements
                skip_web = self._should_skip_web_scraping(mode)

                # Perform extraction
                scrape_result = await self.scraper.fetch_combined(
                    app_url, skip_web_scraping=skip_web
                )

                if scrape_result.success and scrape_result.app_metadata:
                    result.metadata = scrape_result.app_metadata
                    result.success = True
                    result.data_source = scrape_result.app_metadata.data_source
                    result.warnings.extend(scrape_result.warnings)

                    # Cache the result
                    self._cache[app_url] = {
                        "metadata": result.metadata,
                        "timestamp": datetime.now(UTC),
                    }
                else:
                    result.success = False
                    result.errors.append(scrape_result.error or "Unknown error")

            # Validate against boundaries and success criteria
            if result.success and result.metadata:
                # Populate field presence first
                result.required_fields_present = self._get_present_fields(
                    result.metadata, self.config.boundaries.required_fields
                )
                result.optional_fields_present = self._get_present_fields(
                    result.metadata, self.config.boundaries.optional_fields
                )

                # Then check compliance
                result.meets_boundaries = self._check_boundaries(result)
                result.meets_success_criteria = self._check_success_criteria(result)

        except Exception as e:
            result.success = False
            result.errors.append(str(e))

        result.extraction_duration_seconds = (
            datetime.now(UTC) - start_time
        ).total_seconds()

        return result

    async def extract_batch_with_wbs(
        self, app_urls: List[str], mode: ExtractionMode = ExtractionMode.SMART
    ) -> Dict[str, ExtractionResult]:
        """Extract multiple apps respecting WBS boundaries"""
        results = {}

        # Respect concurrency boundaries
        semaphore = asyncio.Semaphore(self.config.boundaries.max_concurrent_requests)

        async def extract_with_semaphore(url: str) -> ExtractionResult:
            async with semaphore:
                return await self.extract_with_wbs(url, mode)

        # Create tasks for all apps
        tasks = [extract_with_semaphore(url) for url in app_urls]

        # Execute and collect results
        extraction_results = await asyncio.gather(*tasks, return_exceptions=True)

        for url, result in zip(app_urls, extraction_results):
            if isinstance(result, Exception):
                error_result = ExtractionResult(
                    app_id=self._extract_app_id(url),
                    success=False,
                    meets_boundaries=False,
                    meets_success_criteria=False,
                )
                error_result.errors.append(str(result))
                results[url] = error_result
            else:
                # Type narrowing: if not Exception, then it's ExtractionResult
                assert isinstance(result, ExtractionResult)
                results[url] = result

        return results

    def validate_wbs_compliance(self, results: Dict[str, ExtractionResult]) -> Dict:
        """Validate overall WBS compliance for a batch extraction"""
        total = len(results)
        successful = sum(1 for r in results.values() if r.success)
        meets_boundaries = sum(1 for r in results.values() if r.meets_boundaries)
        meets_criteria = sum(1 for r in results.values() if r.meets_success_criteria)

        success_rate = successful / total if total > 0 else 0

        return {
            "wbs_compliant": success_rate
            >= self.config.success_criteria.min_extraction_success_rate,
            "total_apps": total,
            "successful_extractions": successful,
            "success_rate": success_rate,
            "meets_boundaries": meets_boundaries,
            "meets_success_criteria": meets_criteria,
            "boundary_compliance_rate": meets_boundaries / total if total > 0 else 0,
            "criteria_compliance_rate": meets_criteria / total if total > 0 else 0,
            "violations": [
                {"app_id": r.app_id, "errors": r.errors, "warnings": r.warnings}
                for r in results.values()
                if not r.meets_boundaries or not r.meets_success_criteria
            ],
        }

    def _extract_app_id(self, url: str) -> str:
        """Extract app ID from URL"""
        import re

        match = re.search(r"/id(\d+)", url)
        return match.group(1) if match else url

    def _should_skip_web_scraping(self, mode: ExtractionMode) -> bool:
        """Determine if web scraping should be skipped"""
        if mode == ExtractionMode.FAST:
            return True
        elif mode == ExtractionMode.COMPLETE:
            return False
        else:  # SMART mode
            # Skip web scraping if optional fields aren't critical
            return len(self.config.boundaries.optional_fields) == 0

    def _is_cache_valid(self, cached_entry: Dict) -> bool:
        """Check if cached data is still valid"""
        age = (datetime.now(UTC) - cached_entry["timestamp"]).total_seconds()
        return bool(age < self.config.boundaries.max_cache_age_seconds)

    def _get_from_cache(self, app_url: str) -> Optional[Dict]:
        """Get data from cache if available"""
        return self._cache.get(app_url)

    def _check_boundaries(self, result: ExtractionResult) -> bool:
        """Check if extraction respected boundaries"""
        # Check extraction time (should be within timeout)
        if result.extraction_duration_seconds > self.config.boundaries.timeout_seconds:
            return False

        # Check that we have all required fields
        required_ratio = (
            len(result.required_fields_present)
            / len(self.config.boundaries.required_fields)
            if self.config.boundaries.required_fields
            else 1.0
        )

        if required_ratio < 1.0:
            return False

        # All boundaries respected
        return True

    def _check_success_criteria(self, result: ExtractionResult) -> bool:
        """Check if extraction meets success criteria"""
        if not result.success:
            return False

        # Check required fields ratio
        if self.config.boundaries.required_fields:
            required_ratio = len(result.required_fields_present) / len(
                self.config.boundaries.required_fields
            )
            if required_ratio < self.config.success_criteria.min_required_fields_ratio:
                return False

        # Check optional fields ratio
        if self.config.boundaries.optional_fields:
            optional_ratio = len(result.optional_fields_present) / len(
                self.config.boundaries.optional_fields
            )
            if optional_ratio < self.config.success_criteria.min_optional_fields_ratio:
                return False

        # All criteria met
        return True

    def _get_present_fields(
        self, metadata: AppMetadataCombined, field_set: Set[str]
    ) -> Set[str]:
        """Get which fields from the set are present in metadata"""
        present = set()
        for field in field_set:
            if hasattr(metadata, field):
                value = getattr(metadata, field)
                if value is not None:
                    present.add(field)
        return present


class RateLimiter:
    """Simple rate limiter for API calls"""

    def __init__(self, itunes_limit: int = 20, web_delay: float = 1.0):
        self.itunes_limit = itunes_limit
        self.web_delay = web_delay
        self.itunes_calls: List[datetime] = []
        self.last_web_call: Optional[datetime] = None

    async def check_and_wait(self) -> None:
        """Check rate limits and wait if necessary"""
        # For iTunes API: Check calls in the last minute
        now = datetime.now(UTC)
        self.itunes_calls = [
            call_time
            for call_time in self.itunes_calls
            if (now - call_time).total_seconds() < 60
        ]

        if len(self.itunes_calls) >= self.itunes_limit:
            # Wait until the oldest call is more than a minute old
            wait_time = 60 - (now - self.itunes_calls[0]).total_seconds()
            if wait_time > 0:
                await asyncio.sleep(wait_time)

        self.itunes_calls.append(now)

        # For web scraping: Ensure minimum delay
        if self.last_web_call:
            elapsed = (now - self.last_web_call).total_seconds()
            if elapsed < self.web_delay:
                await asyncio.sleep(self.web_delay - elapsed)

        self.last_web_call = now
