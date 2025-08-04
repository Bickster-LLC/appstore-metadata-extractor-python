"""Core data models for AppStore Metadata Extractor."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


# Enums
class DataSource(str, Enum):
    """Source of metadata extraction."""

    ITUNES_API = "itunes_api"
    WEB_SCRAPE = "web_scrape"
    COMBINED = "combined"


class InAppPurchaseType(str, Enum):
    """Type of in-app purchase."""

    CONSUMABLE = "consumable"
    NON_CONSUMABLE = "non_consumable"
    AUTO_RENEWABLE_SUBSCRIPTION = "auto_renewable_subscription"
    NON_RENEWING_SUBSCRIPTION = "non_renewing_subscription"
    UNKNOWN = "unknown"


class ExtractionMode(str, Enum):
    """Extraction strategy mode."""

    FAST = "fast"  # iTunes API only
    COMPLETE = "complete"  # iTunes + Web scraping
    SMART = "smart"  # Decide based on requirements


# In-App Purchase Model
class InAppPurchase(BaseModel):
    """Individual in-app purchase item."""

    name: str = Field(..., description="Name of the IAP item")
    price: str = Field(..., description="Formatted price (e.g., '$9.99')")
    price_value: Optional[float] = Field(None, description="Numeric price value")
    currency: Optional[str] = Field(None, description="Currency code")
    type: InAppPurchaseType = Field(
        default=InAppPurchaseType.UNKNOWN, description="Type of IAP"
    )
    description: Optional[str] = Field(None, description="IAP description")


# WBS Framework Models
class WBSBoundaries(BaseModel):
    """Boundaries/constraints for WBS framework."""

    # Rate limiting
    itunes_api_rate_limit: int = Field(
        default=20, description="Max API calls per minute"
    )
    web_scrape_delay: float = Field(
        default=1.0, description="Seconds between web requests"
    )

    # Data freshness
    max_cache_age_seconds: int = Field(
        default=300, description="Maximum age for cached data (5 min)"
    )
    min_update_interval_seconds: int = Field(
        default=300, description="Minimum time between updates"
    )

    # Field requirements
    required_fields: Set[str] = Field(
        default={
            "app_id",
            "name",
            "current_version",
            "developer_name",
            "price",
            "icon_url",
        },
        description="Fields that must be present",
    )
    optional_fields: Set[str] = Field(
        default={"subtitle", "description", "whats_new"},
        description="Fields that are nice to have",
    )

    # Resource limits
    max_concurrent_requests: int = Field(default=5, description="Max parallel requests")
    max_retries: int = Field(default=3, description="Max retry attempts")
    timeout_seconds: int = Field(default=30, description="Request timeout")
    memory_limit_mb: int = Field(default=500, description="Max memory usage in MB")


class WBSSuccess(BaseModel):
    """Success criteria for WBS framework."""

    # Completeness requirements
    min_required_fields_ratio: float = Field(
        default=1.0, description="All required fields must be present"
    )
    min_optional_fields_ratio: float = Field(
        default=0.0, description="Optional fields are optional"
    )

    # Quality requirements
    min_extraction_success_rate: float = Field(
        default=0.95, description="95% success rate"
    )
    max_error_rate: float = Field(default=0.05, description="Max 5% errors allowed")
    max_response_time_seconds: float = Field(
        default=30.0, description="Max response time"
    )

    # Tracking requirements
    detect_version_changes: bool = Field(
        default=True, description="Must detect version updates"
    )
    track_price_changes: bool = Field(
        default=True, description="Must track price changes"
    )

    @field_validator("min_extraction_success_rate", "max_error_rate")
    @classmethod
    def validate_rate(cls, v: float) -> float:
        if not 0 <= v <= 1:
            raise ValueError("Rate must be between 0 and 1")
        return v


class WBSConfig(BaseModel):
    """Complete WBS framework configuration."""

    # WHAT: Core purpose
    what: str = Field(
        "Extract and track App Store metadata", description="Core purpose"
    )

    # BOUNDARIES: Constraints
    boundaries: WBSBoundaries = Field(default_factory=WBSBoundaries)

    # SUCCESS: Criteria
    success: WBSSuccess = Field(default_factory=WBSSuccess)


# Core App Metadata Models
class AppMetadata(BaseModel):
    """Core app metadata - simplified version for basic operations."""

    # Identifiers
    app_id: str = Field(..., description="Apple App Store ID")
    bundle_id: Optional[str] = Field(None, description="App bundle identifier")
    url: HttpUrl = Field(..., description="App Store URL")

    # Basic info
    name: str = Field(..., description="App name")
    subtitle: Optional[str] = Field(None, description="App subtitle/tagline")
    developer_name: str = Field(..., description="Developer name")
    developer_id: Optional[str] = Field(None, description="Developer ID")

    # Category
    category: str = Field(..., description="Primary category")
    category_id: Optional[int] = Field(None, description="Category ID")

    # Pricing
    price: float = Field(default=0.0, description="Price in USD")
    formatted_price: str = Field(default="Free", description="Formatted price string")
    currency: str = Field(default="USD", description="Currency code")
    in_app_purchases: bool = Field(default=False, description="Has in-app purchases")
    in_app_purchase_list: List[InAppPurchase] = Field(
        default_factory=list, description="List of in-app purchases"
    )

    # Version
    current_version: str = Field(..., description="Current version number")
    version_date: Optional[datetime] = Field(None, description="Version release date")
    whats_new: Optional[str] = Field(None, description="What's new in this version")

    # Content
    description: Optional[str] = Field(None, description="App description")

    # Technical
    file_size_bytes: Optional[int] = Field(None, description="Size in bytes")
    minimum_os_version: Optional[str] = Field(None, description="Minimum iOS version")

    # Ratings
    content_rating: str = Field(default="4+", description="Age rating")
    average_rating: Optional[float] = Field(None, description="Average user rating")
    rating_count: Optional[int] = Field(None, description="Total number of ratings")

    # Media
    icon_url: HttpUrl = Field(..., description="App icon URL")
    screenshots: List[HttpUrl] = Field(
        default_factory=list, description="Screenshot URLs"
    )

    # Support links
    app_support_url: Optional[HttpUrl] = Field(None, description="App support URL")
    privacy_policy_url: Optional[HttpUrl] = Field(
        None, description="Privacy policy URL"
    )
    developer_website_url: Optional[HttpUrl] = Field(
        None, description="Developer website URL"
    )

    # Metadata
    data_source: DataSource = Field(..., description="Source of the data")
    extracted_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Extraction timestamp"
    )

    model_config = ConfigDict()


class ExtendedAppMetadata(AppMetadata):
    """Extended app metadata with additional fields from web scraping."""

    # Additional developer info
    developer_url: Optional[HttpUrl] = Field(None, description="Developer page URL")

    # Extended categories
    categories: List[str] = Field(default_factory=list, description="All categories")
    category_ids: List[int] = Field(
        default_factory=list, description="All category IDs"
    )

    # Version history
    initial_release_date: Optional[datetime] = Field(
        None, description="First release date"
    )
    last_updated: Optional[datetime] = Field(None, description="Last update date")

    # Languages
    language_codes: List[str] = Field(
        default_factory=list, description="ISO language codes"
    )
    languages: List[str] = Field(
        default_factory=list, description="Human-readable languages"
    )

    # Extended ratings
    average_rating_current_version: Optional[float] = Field(
        None, description="Rating for current version"
    )
    rating_count_current_version: Optional[int] = Field(
        None, description="Ratings for current version"
    )

    # Additional media
    ipad_screenshots: List[HttpUrl] = Field(
        default_factory=list, description="iPad screenshots"
    )

    # Features
    features: List[str] = Field(
        default_factory=list, description="App features/capabilities"
    )
    is_game_center_enabled: bool = Field(
        default=False, description="Game Center support"
    )

    # URLs
    support_url: Optional[HttpUrl] = Field(None, description="Support website")
    marketing_url: Optional[HttpUrl] = Field(None, description="Marketing website")

    # Raw data (for debugging/analysis)
    raw_data: Optional[Dict[str, Any]] = Field(None, description="Raw response data")


# Extraction Results
class ExtractionResult(BaseModel):
    """Result of a metadata extraction operation."""

    # Core data
    app_id: str
    metadata: Optional[AppMetadata] = None
    success: bool = False

    # Errors and warnings
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    # WBS compliance tracking
    wbs_compliant: bool = Field(
        default=False, description="Whether extraction met WBS criteria"
    )
    wbs_violations: List[str] = Field(
        default_factory=list, description="List of WBS violations"
    )
    required_fields_present: Set[str] = Field(default_factory=set)
    optional_fields_present: Set[str] = Field(default_factory=set)

    # Performance metrics
    extraction_duration_seconds: float = 0.0
    data_source: Optional[DataSource] = None
    extraction_method: Optional[ExtractionMode] = None

    # Cache info
    from_cache: bool = False
    cache_age_seconds: Optional[float] = None

    def add_error(self, error: str) -> None:
        """Add an error to the result."""
        self.errors.append(error)
        self.success = False

    def add_warning(self, warning: str) -> None:
        """Add a warning to the result."""
        self.warnings.append(warning)

    def add_wbs_violation(self, violation: str) -> None:
        """Add a WBS violation."""
        self.wbs_violations.append(violation)
        self.wbs_compliant = False


class BatchExtractionResult(BaseModel):
    """Result of batch extraction operations."""

    total: int
    successful: int
    failed: int
    results: List[ExtractionResult]
    duration_seconds: float
    wbs_compliant: bool = Field(
        default=False, description="Whether all extractions were WBS compliant"
    )

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        return self.successful / self.total if self.total > 0 else 0.0


# Change Detection Models
class FieldChange(BaseModel):
    """Represents a change in a single field."""

    field_name: str
    old_value: Any
    new_value: Any
    change_type: str  # 'added', 'removed', 'modified'
    detected_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict()


class AppChangeLog(BaseModel):
    """Log of changes detected for an app."""

    app_id: str
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    changes: List[FieldChange]
    version_changed: bool = False
    price_changed: bool = False
    metadata_before: Optional[AppMetadata] = None
    metadata_after: Optional[AppMetadata] = None

    model_config = ConfigDict()
