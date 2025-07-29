"""Custom exceptions for AppStore Metadata Extractor."""

from typing import Any, List, Optional


class AppStoreExtractorError(Exception):
    """Base exception for all extractor errors."""


class ExtractionError(AppStoreExtractorError):
    """Raised when extraction fails."""

    def __init__(
        self, message: str, url: Optional[str] = None, cause: Optional[Exception] = None
    ):
        self.url = url
        self.cause = cause
        super().__init__(message)


class RateLimitError(AppStoreExtractorError):
    """Raised when rate limit is exceeded."""

    def __init__(self, service: str, retry_after: Optional[int] = None):
        self.service = service
        self.retry_after = retry_after
        message = f"Rate limit exceeded for {service}"
        if retry_after:
            message += f". Retry after {retry_after} seconds"
        super().__init__(message)


class ValidationError(AppStoreExtractorError):
    """Raised when data validation fails."""

    def __init__(self, field: str, value: Any, expected: str):
        self.field = field
        self.value = value
        self.expected = expected
        super().__init__(
            f"Validation failed for {field}: expected {expected}, got {type(value).__name__}"
        )


class WBSViolationError(AppStoreExtractorError):
    """Raised when WBS constraints are violated."""

    def __init__(self, violations: List[str]):
        self.violations = violations
        message = f"WBS violations detected: {'; '.join(violations)}"
        super().__init__(message)


class CacheError(AppStoreExtractorError):
    """Raised when cache operations fail."""


class NetworkError(AppStoreExtractorError):
    """Raised when network operations fail."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        self.status_code = status_code
        super().__init__(message)
