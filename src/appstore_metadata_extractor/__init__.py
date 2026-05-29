__version__ = "0.2.4"
__author__ = "Bickster LLC"
__email__ = "support@bickster.com"

# Import from core module
from .core import (  # Extractors; Models; Validation; Cache
    AppMetadata,
    AppStoreRankingFetcher,
    AppStoreReviewExtractor,
    AppStoreSearcher,
    BaseExtractor,
    CacheManager,
    ChartKind,
    ChartSnapshot,
    CombinedExtractor,
    CompositeAppStoreClient,
    ExtendedAppMetadata,
    ExtractionMode,
    ExtractionResult,
    ITunesAPIExtractor,
    RankingEntry,
    RateLimiter,
    ReviewBatch,
    SearchHit,
    SearchResults,
    SortOrder,
    WBSConfig,
    WBSValidator,
    WebScraperExtractor,
)
from .models_combined import Review

# Legacy imports for backward compatibility
from .scraper import AppStoreScraper
from .wbs_extractor import WBSMetadataExtractor

# Create alias for CombinedExtractor to replace CombinedAppStoreScraper
CombinedAppStoreScraper = CombinedExtractor

__all__ = [
    # Core exports
    "BaseExtractor",
    "ITunesAPIExtractor",
    "WebScraperExtractor",
    "CombinedExtractor",
    "AppMetadata",
    "ExtendedAppMetadata",
    "ExtractionMode",
    "ExtractionResult",
    "WBSConfig",
    "WBSValidator",
    "CacheManager",
    "RateLimiter",
    # v0.2.0 — search, reviews, rankings, composite client
    "AppStoreSearcher",
    "SearchHit",
    "SearchResults",
    "AppStoreReviewExtractor",
    "Review",
    "ReviewBatch",
    "SortOrder",
    "AppStoreRankingFetcher",
    "RankingEntry",
    "ChartSnapshot",
    "ChartKind",
    "CompositeAppStoreClient",
    # Legacy exports
    "AppStoreScraper",
    "CombinedAppStoreScraper",
    "WBSMetadataExtractor",
]
