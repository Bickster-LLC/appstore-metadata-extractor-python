from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class DataSource(str, Enum):
    ITUNES_API = "itunes_api"
    WEB_SCRAPE = "web_scrape"
    COMBINED = "combined"


class PrivacyDetail(BaseModel):
    category: str = Field(..., description="Privacy category name")
    data_types: List[str] = Field(
        default_factory=list, description="Types of data collected"
    )


class AppPrivacy(BaseModel):
    data_used_to_track: List[PrivacyDetail] = Field(default_factory=list)
    data_linked_to_you: List[PrivacyDetail] = Field(default_factory=list)
    data_not_linked_to_you: List[PrivacyDetail] = Field(default_factory=list)
    privacy_details_url: Optional[HttpUrl] = None


class Review(BaseModel):
    author: str
    rating: int = Field(..., ge=1, le=5)
    title: Optional[str] = None
    content: str
    date: datetime
    version: Optional[str] = None
    helpful_count: int = 0


class RatingDistribution(BaseModel):
    five_stars: int = 0
    four_stars: int = 0
    three_stars: int = 0
    two_stars: int = 0
    one_star: int = 0


class RelatedApp(BaseModel):
    app_id: str
    name: str
    developer: str
    icon_url: HttpUrl
    rating: Optional[float] = None
    price: str = "Free"
    category: str


class VersionHistory(BaseModel):
    version: str
    release_date: datetime
    release_notes: Optional[str] = None


class AppMetadataCombined(BaseModel):
    # Core identifiers
    app_id: str = Field(..., description="Apple App Store ID")
    bundle_id: Optional[str] = Field(None, description="App bundle identifier")
    url: HttpUrl = Field(..., description="App Store URL")

    # Basic info (available from both sources)
    name: str = Field(..., description="App name")
    subtitle: Optional[str] = Field(None, description="App subtitle/tagline - WEB ONLY")
    developer_name: str = Field(..., description="Developer name")
    developer_id: Optional[str] = Field(None, description="Developer ID")
    developer_url: Optional[HttpUrl] = Field(None, description="Developer page URL")

    # Categories
    primary_category: str = Field(..., description="Primary category name")
    primary_category_id: Optional[int] = Field(None, description="Primary category ID")
    categories: List[str] = Field(default_factory=list, description="All categories")
    category_ids: List[int] = Field(
        default_factory=list, description="All category IDs"
    )

    # Pricing
    price: float = Field(0.0, description="Price in local currency")
    formatted_price: str = Field("Free", description="Formatted price string")
    currency: str = Field("USD", description="Currency code")
    in_app_purchases: Optional[bool] = Field(None, description="Has IAPs - WEB ONLY")
    in_app_purchase_list: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of IAPs with names and prices - WEB ONLY",
    )

    # Version info
    current_version: str = Field(..., description="Current version number")
    current_version_release_date: Optional[datetime] = Field(
        None, description="Release date"
    )
    release_notes: Optional[str] = Field(None, description="What's new in this version")
    version_history: List[VersionHistory] = Field(
        default_factory=list, description="Previous versions - WEB ONLY"
    )

    # Content
    description: str = Field(..., description="Full app description")

    # Technical details
    file_size_bytes: Optional[int] = Field(None, description="Size in bytes")
    file_size_formatted: Optional[str] = Field(None, description="Human-readable size")
    minimum_os_version: Optional[str] = Field(None, description="Minimum iOS version")
    supported_devices: List[str] = Field(
        default_factory=list, description="Compatible devices"
    )

    # Languages
    language_codes: List[str] = Field(
        default_factory=list, description="ISO language codes"
    )
    languages: List[str] = Field(
        default_factory=list, description="Human-readable languages"
    )

    # Ratings and reviews
    content_rating: str = Field(..., description="Age rating")
    content_advisories: List[str] = Field(
        default_factory=list, description="Content warnings"
    )
    average_rating: Optional[float] = Field(None, description="Average user rating")
    rating_count: Optional[int] = Field(None, description="Total number of ratings")
    average_rating_current_version: Optional[float] = Field(
        None, description="Rating for current version"
    )
    rating_count_current_version: Optional[int] = Field(
        None, description="Ratings for current version"
    )
    rating_distribution: Optional[RatingDistribution] = Field(
        None, description="Star breakdown - WEB ONLY"
    )
    reviews: List[Review] = Field(
        default_factory=list, description="User reviews - WEB ONLY"
    )

    # Media
    icon_url: HttpUrl = Field(..., description="App icon URL")
    icon_urls: Dict[str, HttpUrl] = Field(
        default_factory=dict, description="Multiple icon sizes"
    )
    screenshots: List[HttpUrl] = Field(
        default_factory=list, description="iPhone screenshots"
    )
    ipad_screenshots: List[HttpUrl] = Field(
        default_factory=list, description="iPad screenshots"
    )

    # Support links (WEB ONLY)
    app_support_url: Optional[HttpUrl] = Field(
        None, description="App support URL - WEB ONLY"
    )
    privacy_policy_url: Optional[HttpUrl] = Field(
        None, description="Privacy policy URL - WEB ONLY"
    )
    developer_website_url: Optional[HttpUrl] = Field(
        None, description="Developer website URL - WEB ONLY"
    )

    # Privacy (WEB ONLY)
    privacy: Optional[AppPrivacy] = Field(
        None, description="Privacy information - WEB ONLY"
    )

    # Related content (WEB ONLY)
    developer_apps: List[RelatedApp] = Field(
        default_factory=list, description="Other apps by developer - WEB ONLY"
    )
    similar_apps: List[RelatedApp] = Field(
        default_factory=list, description="You might also like - WEB ONLY"
    )

    # Rankings (WEB ONLY)
    rankings: Dict[str, int] = Field(
        default_factory=dict, description="Chart positions - WEB ONLY"
    )

    # Metadata
    initial_release_date: Optional[datetime] = Field(
        None, description="First release date"
    )
    last_updated: Optional[datetime] = Field(
        None, description="Last update to any field"
    )
    data_source: DataSource = Field(..., description="Source of the data")
    scraped_at: datetime = Field(
        default_factory=datetime.utcnow, description="When data was collected"
    )

    # Features and capabilities
    features: List[str] = Field(
        default_factory=list, description="App features/capabilities"
    )
    is_game_center_enabled: bool = Field(False, description="Game Center support")
    is_vpp_device_based_licensing_enabled: bool = Field(
        False, description="VPP support"
    )

    # Additional URLs
    support_url: Optional[HttpUrl] = Field(None, description="Support website")
    marketing_url: Optional[HttpUrl] = Field(None, description="Marketing website")

    # Raw data storage (for fields we might miss)
    raw_itunes_data: Optional[Dict[str, Any]] = Field(
        None, description="Raw iTunes API response"
    )
    raw_web_data: Optional[Dict[str, Any]] = Field(None, description="Raw scraped data")

    model_config = ConfigDict()


class CombinedScrapeResult(BaseModel):
    success: bool
    app_metadata: Optional[AppMetadataCombined] = None
    error: Optional[str] = None
    error_details: Optional[Dict] = None
    data_sources_used: List[DataSource] = Field(default_factory=list)
    warnings: List[str] = Field(
        default_factory=list, description="Non-fatal issues encountered"
    )
