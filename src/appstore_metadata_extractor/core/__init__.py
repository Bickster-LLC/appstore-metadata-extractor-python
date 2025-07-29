"""Core module for AppStore Metadata Extractor.

This module contains shared business logic used by both CLI and web interfaces.
"""

from .cache import CacheManager, RateLimiter
from .exceptions import (
    ExtractionError,
    RateLimitError,
    ValidationError,
)
from .extractors import (
    BaseExtractor,
    CombinedExtractor,
    ITunesAPIExtractor,
    WebScraperExtractor,
)
from .models import (
    AppMetadata,
    ExtendedAppMetadata,
    ExtractionMode,
    ExtractionResult,
    WBSBoundaries,
    WBSConfig,
    WBSSuccess,
)
from .security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_password_reset_token,
    generate_verification_token,
    get_password_hash,
    get_password_strength_message,
    hash_token,
    validate_password_complexity,
    verify_password,
)
from .wbs_validator import WBSValidator

__all__ = [
    # Extractors
    "BaseExtractor",
    "ITunesAPIExtractor",
    "WebScraperExtractor",
    "CombinedExtractor",
    # Models
    "AppMetadata",
    "ExtendedAppMetadata",
    "ExtractionMode",
    "ExtractionResult",
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
    # Security
    "verify_password",
    "get_password_hash",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "hash_token",
    "generate_verification_token",
    "generate_password_reset_token",
    "validate_password_complexity",
    "get_password_strength_message",
]
