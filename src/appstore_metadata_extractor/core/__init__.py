"""Core module for AppStore Metadata Extractor.

This module contains shared business logic used by both CLI and web interfaces.
"""

from .cache import CacheManager, RateLimiter
from .exceptions import ExtractionError, RateLimitError, ValidationError
from .extractors import (
    BaseExtractor,
    CombinedExtractor,
    ITunesAPIExtractor,
    WebScraperExtractor,
)
from .models import (
    AppMetadata,
    DataSource,
    ExtendedAppMetadata,
    ExtractionMode,
    ExtractionResult,
    InAppPurchase,
    InAppPurchaseType,
    WBSBoundaries,
    WBSConfig,
    WBSSuccess,
)

# Security module removed - only needed for web API, not standalone package
from .wbs_validator import WBSValidator

__all__ = [
    # Extractors
    "BaseExtractor",
    "ITunesAPIExtractor",
    "WebScraperExtractor",
    "CombinedExtractor",
    # Models
    "AppMetadata",
    "DataSource",
    "ExtendedAppMetadata",
    "ExtractionMode",
    "ExtractionResult",
    "InAppPurchase",
    "InAppPurchaseType",
    "WBSConfig",
    "WBSBoundaries",
    "WBSSuccess",
    # Validation
    "WBSValidator",
    # Cache
    "CacheManager",
    "RateLimiter",
    # Exceptions
    "ExtractionError",
    "RateLimitError",
    "ValidationError",
]
