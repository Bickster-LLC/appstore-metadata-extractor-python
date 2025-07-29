from datetime import UTC, datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class AppMetadata(BaseModel):
    app_id: str = Field(..., description="Apple App Store ID")
    url: HttpUrl = Field(..., description="App Store URL")
    title: str = Field(..., description="App title/name")
    subtitle: Optional[str] = Field(None, description="App subtitle")
    developer: str = Field(..., description="Developer name")
    category: str = Field(..., description="App category")
    price: Optional[str] = Field(None, description="App price")
    in_app_purchases: bool = Field(False, description="Has in-app purchases")
    description: Optional[str] = Field(None, description="App description")
    version: str = Field(..., description="Current app version")
    version_date: Optional[datetime] = Field(None, description="Version release date")
    size: Optional[str] = Field(None, description="App size")
    languages: List[str] = Field(
        default_factory=list, description="Supported languages"
    )
    age_rating: Optional[str] = Field(None, description="Age rating")
    rating: Optional[float] = Field(None, description="Average user rating")
    rating_count: Optional[int] = Field(None, description="Number of ratings")
    screenshots: List[str] = Field(default_factory=list, description="Screenshot URLs")
    icon_url: Optional[HttpUrl] = Field(None, description="App icon URL")
    whats_new: Optional[str] = Field(None, description="What's new in this version")
    scraped_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Scrape timestamp"
    )

    model_config = ConfigDict()


class AppInput(BaseModel):
    name: str = Field(..., description="App name for reference")
    url: HttpUrl = Field(..., description="App Store URL")


class ScrapeResult(BaseModel):
    success: bool
    app_metadata: Optional[AppMetadata] = None
    error: Optional[str] = None
    error_details: Optional[Dict] = None


class BatchScrapeResult(BaseModel):
    total: int
    successful: int
    failed: int
    results: List[ScrapeResult]
    duration_seconds: float
