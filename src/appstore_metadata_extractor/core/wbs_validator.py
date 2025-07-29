"""WBS (What-Boundaries-Success) framework validator."""

from typing import List, Optional, Set

from .models import AppMetadata, BatchExtractionResult, ExtractionResult, WBSConfig


class WBSValidator:
    """Validates extraction results against WBS constraints."""

    def __init__(self, config: WBSConfig):
        """
        Initialize validator with WBS configuration.

        Args:
            config: WBS configuration defining boundaries and success criteria
        """
        self.config = config
        self.violations: List[str] = []

    def validate(self, result: ExtractionResult) -> bool:
        """
        Validate extraction result against WBS constraints.

        Args:
            result: Extraction result to validate

        Returns:
            True if WBS compliant, False otherwise
        """
        self.violations = []

        # Check boundaries
        boundaries_ok = self._check_boundaries(result)

        # Check success criteria
        success_ok = self._check_success_criteria(result)

        # Update result
        result.wbs_compliant = boundaries_ok and success_ok
        result.wbs_violations = self.violations.copy()

        return result.wbs_compliant

    def validate_batch(self, batch_result: BatchExtractionResult) -> bool:
        """
        Validate batch extraction results.

        Args:
            batch_result: Batch extraction result

        Returns:
            True if all extractions are WBS compliant
        """
        all_compliant = True

        # Check overall success rate
        if batch_result.success_rate < self.config.success.min_extraction_success_rate:
            self.violations.append(
                f"Batch success rate {batch_result.success_rate:.2%} below required "
                f"{self.config.success.min_extraction_success_rate:.2%}"
            )
            all_compliant = False

        # Check individual results
        for result in batch_result.results:
            if not self.validate(result):
                all_compliant = False

        batch_result.wbs_compliant = all_compliant
        return all_compliant

    def _check_boundaries(self, result: ExtractionResult) -> bool:
        """Check if extraction respected boundaries."""
        boundaries_ok = True

        # Check timeout
        if result.extraction_duration_seconds > self.config.boundaries.timeout_seconds:
            self.violations.append(
                f"Extraction took {result.extraction_duration_seconds:.1f}s, "
                f"exceeding {self.config.boundaries.timeout_seconds}s timeout"
            )
            boundaries_ok = False

        # Check required fields if metadata present
        if result.metadata:
            present_fields = self._get_present_fields(result.metadata)
            result.required_fields_present = (
                present_fields & self.config.boundaries.required_fields
            )
            result.optional_fields_present = (
                present_fields & self.config.boundaries.optional_fields
            )

            missing_required = (
                self.config.boundaries.required_fields - result.required_fields_present
            )
            if missing_required:
                self.violations.append(
                    f"Missing required fields: {', '.join(sorted(missing_required))}"
                )
                boundaries_ok = False

        return boundaries_ok

    def _check_success_criteria(self, result: ExtractionResult) -> bool:
        """Check if extraction meets success criteria."""
        success_ok = True

        # If extraction failed, it doesn't meet success criteria
        if not result.success:
            self.violations.append("Extraction failed")
            return False

        # Check response time
        if (
            result.extraction_duration_seconds
            > self.config.success.max_response_time_seconds
        ):
            self.violations.append(
                f"Response time {result.extraction_duration_seconds:.1f}s exceeds "
                f"maximum {self.config.success.max_response_time_seconds}s"
            )
            success_ok = False

        # Check field completeness if metadata present
        if result.metadata:
            # Required fields ratio
            required_ratio = (
                len(result.required_fields_present)
                / len(self.config.boundaries.required_fields)
                if self.config.boundaries.required_fields
                else 1.0
            )

            if required_ratio < self.config.success.min_required_fields_ratio:
                self.violations.append(
                    f"Required fields ratio {required_ratio:.2%} below minimum "
                    f"{self.config.success.min_required_fields_ratio:.2%}"
                )
                success_ok = False

            # Optional fields ratio (only if we have optional fields defined)
            if self.config.boundaries.optional_fields:
                optional_ratio = len(result.optional_fields_present) / len(
                    self.config.boundaries.optional_fields
                )

                if optional_ratio < self.config.success.min_optional_fields_ratio:
                    self.violations.append(
                        f"Optional fields ratio {optional_ratio:.2%} below minimum "
                        f"{self.config.success.min_optional_fields_ratio:.2%}"
                    )
                    success_ok = False

        return success_ok

    def _get_present_fields(self, metadata: AppMetadata) -> Set[str]:
        """Get set of non-null fields from metadata."""
        present_fields = set()

        # Convert to dict and check non-null fields
        data = metadata.model_dump()
        for field, value in data.items():
            if value is not None:
                # Handle special cases
                if isinstance(value, list) and len(value) > 0:
                    present_fields.add(field)
                elif isinstance(value, str) and value.strip():
                    present_fields.add(field)
                elif not isinstance(value, (list, str)):
                    present_fields.add(field)

        return present_fields

    def get_violations(self) -> List[str]:
        """Get list of WBS violations from last validation."""
        return self.violations.copy()

    def create_compliant_result(
        self,
        app_id: str,
        metadata: Optional[AppMetadata] = None,
        duration: float = 0.0,
        from_cache: bool = False,
    ) -> ExtractionResult:
        """
        Create a WBS-compliant extraction result.

        Args:
            app_id: App Store ID
            metadata: Extracted metadata
            duration: Extraction duration in seconds
            from_cache: Whether result came from cache

        Returns:
            ExtractionResult that meets WBS criteria
        """
        result = ExtractionResult(
            app_id=app_id,
            metadata=metadata,
            success=metadata is not None,
            extraction_duration_seconds=duration,
            from_cache=from_cache,
            wbs_compliant=False,  # Will be updated by validate()
        )

        if metadata:
            result.data_source = metadata.data_source

        # Validate and update compliance status
        self.validate(result)

        return result

    def enforce_boundaries(self) -> None:
        """
        Enforce boundaries before extraction.
        Raises WBSViolationError if boundaries cannot be met.
        """
        # This would be called before extraction to ensure
        # rate limits, resource limits, etc. are respected
        # For now, it's a placeholder for pre-extraction checks

    def get_wbs_report(self, result: ExtractionResult) -> dict:
        """
        Generate detailed WBS compliance report.

        Args:
            result: Extraction result to report on

        Returns:
            Dictionary with detailed compliance information
        """
        return {
            "wbs_compliant": result.wbs_compliant,
            "boundaries": {
                "timeout_seconds": {
                    "limit": self.config.boundaries.timeout_seconds,
                    "actual": result.extraction_duration_seconds,
                    "compliant": result.extraction_duration_seconds
                    <= self.config.boundaries.timeout_seconds,
                },
                "required_fields": {
                    "expected": list(self.config.boundaries.required_fields),
                    "present": list(result.required_fields_present),
                    "missing": list(
                        self.config.boundaries.required_fields
                        - result.required_fields_present
                    ),
                    "compliant": len(result.required_fields_present)
                    == len(self.config.boundaries.required_fields),
                },
            },
            "success_criteria": {
                "extraction_succeeded": result.success,
                "response_time": {
                    "limit": self.config.success.max_response_time_seconds,
                    "actual": result.extraction_duration_seconds,
                    "compliant": result.extraction_duration_seconds
                    <= self.config.success.max_response_time_seconds,
                },
            },
            "violations": result.wbs_violations,
            "warnings": result.warnings,
            "errors": result.errors,
        }
