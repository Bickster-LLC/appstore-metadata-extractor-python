__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .combined_scraper import CombinedAppStoreScraper

# Import from core module
from .core import (  # Extractors; Models; Validation; Cache
    AppMetadata,
    BaseExtractor,
    CacheManager,
    CombinedExtractor,
    ExtendedAppMetadata,
    ExtractionMode,
    ExtractionResult,
    ITunesAPIExtractor,
    RateLimiter,
    WBSConfig,
    WBSValidator,
    WebScraperExtractor,
)

# Legacy imports for backward compatibility
from .scraper import AppStoreScraper
from .wbs_extractor import WBSMetadataExtractor

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
    # Legacy exports
    "AppStoreScraper",
    "CombinedAppStoreScraper",
    "WBSMetadataExtractor",
]
