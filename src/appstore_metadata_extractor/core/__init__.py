"""Core module for AppStore Metadata Extractor.

This module contains shared business logic used by both CLI and web interfaces.
"""

from .cache import CacheManager, RateLimiter
from .client import CompositeAppStoreClient
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
from .rankings import AppStoreRankingFetcher, ChartKind, ChartSnapshot, RankingEntry
from .reviews import AppStoreReviewExtractor, ReviewBatch, SortOrder
from .search import AppStoreSearcher, SearchHit, SearchResults

# Security module removed - only needed for web API, not standalone package
from .wbs_validator import WBSValidator

__all__ = [
    # Extractors
    "BaseExtractor",
    "ITunesAPIExtractor",
    "WebScraperExtractor",
    "CombinedExtractor",
    # New extractors
    "AppStoreSearcher",
    "AppStoreReviewExtractor",
    "AppStoreRankingFetcher",
    "CompositeAppStoreClient",
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
    # New models
    "SearchHit",
    "SearchResults",
    "ReviewBatch",
    "SortOrder",
    "RankingEntry",
    "ChartSnapshot",
    "ChartKind",
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
