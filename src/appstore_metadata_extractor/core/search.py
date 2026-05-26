"""iTunes Search API client.

Discovers apps by keyword or genre via the public iTunes Search endpoint:

    https://itunes.apple.com/search?term=<query>&country=<cc>&entity=software

Documented at:
https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/index.html
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

import aiohttp
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from .cache import CacheManager, RateLimiter, get_cache_manager, get_rate_limiter
from .exceptions import NetworkError

# Shared rate-limit budget identifier — coordinated with iTunesAPIExtractor.
_RATE_LIMIT_SERVICE = "itunes_api"
_RATE_LIMIT_CALLS_PER_MINUTE = 20


class SearchHit(BaseModel):
    """A single search result.

    Subset of fields the iTunes Search API returns for each match.
    """

    app_id: str = Field(..., description="Apple track ID")
    bundle_id: Optional[str] = Field(None, description="App bundle identifier")
    name: str = Field(..., description="App name (trackName)")
    developer_name: str = Field(..., description="Developer/artist name")
    developer_id: Optional[str] = Field(None, description="Artist ID")
    url: str = Field(..., description="apps.apple.com URL (trackViewUrl)")
    icon_url: Optional[str] = Field(None, description="Best available artwork URL")
    average_rating: Optional[float] = Field(None, description="averageUserRating")
    rating_count: Optional[int] = Field(None, description="userRatingCount")
    price: Optional[float] = Field(None, description="Price in storefront currency")
    formatted_price: Optional[str] = Field(None, description="Formatted price string")
    primary_category: Optional[str] = Field(None, description="primaryGenreName")
    primary_category_id: Optional[int] = Field(None, description="primaryGenreId")
    description: Optional[str] = Field(None, description="Full description")
    country: str = Field("us", description="Storefront the result came from")


class SearchResults(BaseModel):
    """Paginated search results for one query."""

    query: str
    country: str
    total_count: int = Field(
        ..., description="resultCount from the API (may exceed len(hits))"
    )
    hits: List[SearchHit] = Field(default_factory=list)
    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the result was fetched",
    )


class AppStoreSearcher:
    """Async client for the iTunes Search API.

    Shares the ``itunes_api`` rate-limit bucket with ``ITunesAPIExtractor`` and
    other extractors so the per-IP budget is honored across calls.
    """

    BASE_URL = "https://itunes.apple.com/search"
    DEFAULT_CACHE_TTL = 60 * 60  # 1 hour

    def __init__(
        self,
        rate_limiter: Optional[RateLimiter] = None,
        cache_manager: Optional[CacheManager] = None,
        timeout: int = 30,
        cache_ttl: int = DEFAULT_CACHE_TTL,
    ) -> None:
        self.rate_limiter = rate_limiter or get_rate_limiter()
        self.cache = cache_manager or get_cache_manager()
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self._session: Optional[aiohttp.ClientSession] = None

        # Ensure the shared rate-limit bucket is configured.
        if _RATE_LIMIT_SERVICE not in self.rate_limiter.buckets:
            self.rate_limiter.configure(
                _RATE_LIMIT_SERVICE,
                max_requests=_RATE_LIMIT_CALLS_PER_MINUTE,
                time_window=60,
            )

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        """Release the underlying aiohttp session."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def search(
        self,
        query: str,
        country: str = "us",
        limit: int = 50,
        genre_id: Optional[int] = None,
    ) -> SearchResults:
        """Find apps matching a query in the chosen storefront.

        Args:
            query: Search term. Empty string is allowed and returns an empty
                result without an HTTP request.
            country: ISO 3166-1 alpha-2 storefront code.
            limit: Max results (iTunes hard cap is 200).
            genre_id: Optional genre/category to filter by.
        """
        if not query or not query.strip():
            return SearchResults(
                query=query,
                country=country,
                total_count=0,
                hits=[],
            )

        params: Dict[str, Any] = {
            "term": query,
            "country": country,
            "media": "software",
            "entity": "software",
            "limit": min(max(limit, 1), 200),
        }
        if genre_id is not None:
            params["genreId"] = genre_id

        return await self._fetch(query=query, country=country, params=params)

    async def search_by_genre(
        self,
        genre_id: int,
        country: str = "us",
        limit: int = 50,
    ) -> SearchResults:
        """Search using only a genre filter (no keyword)."""
        params: Dict[str, Any] = {
            "country": country,
            "media": "software",
            "entity": "software",
            "limit": min(max(limit, 1), 200),
            "genreId": genre_id,
            # iTunes Search requires a term; a wildcard keeps results broad.
            "term": "*",
        }
        return await self._fetch(
            query=f"genre:{genre_id}", country=country, params=params
        )

    async def _fetch(
        self,
        query: str,
        country: str,
        params: Dict[str, Any],
    ) -> SearchResults:
        cache_key = (
            "search:"
            f"{country}:{params.get('term', '')}:{params['limit']}:"
            f"{params.get('genreId', '')}"
        )

        cached = self.cache.get(cache_key)
        if cached is not None:
            return SearchResults.model_validate(cached)

        self.rate_limiter.consume(_RATE_LIMIT_SERVICE)

        session = await self._get_session()
        try:
            async with session.get(self.BASE_URL, params=params) as response:
                response.raise_for_status()
                text = await response.text()
                data = json.loads(text)
        except aiohttp.ClientError as exc:
            raise NetworkError(
                f"iTunes Search API request failed: {exc}",
                getattr(exc, "status", None),
            ) from exc

        results = self._parse(query=query, country=country, payload=data)
        self.cache.set(cache_key, results.model_dump(mode="json"), ttl=self.cache_ttl)
        return results

    @staticmethod
    def _parse(query: str, country: str, payload: Dict[str, Any]) -> SearchResults:
        raw_results = payload.get("results") or []
        hits: List[SearchHit] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            track_id = item.get("trackId")
            if track_id is None:
                # iTunes occasionally returns non-app entities; ignore.
                continue
            hits.append(
                SearchHit(
                    app_id=str(track_id),
                    bundle_id=item.get("bundleId"),
                    name=item.get("trackName") or item.get("collectionName") or "",
                    developer_name=item.get("artistName", ""),
                    developer_id=(
                        str(item["artistId"])
                        if item.get("artistId") is not None
                        else None
                    ),
                    url=item.get("trackViewUrl", ""),
                    icon_url=item.get("artworkUrl512")
                    or item.get("artworkUrl100")
                    or item.get("artworkUrl60"),
                    average_rating=item.get("averageUserRating"),
                    rating_count=item.get("userRatingCount"),
                    price=item.get("price"),
                    formatted_price=item.get("formattedPrice"),
                    primary_category=item.get("primaryGenreName"),
                    primary_category_id=item.get("primaryGenreId"),
                    description=item.get("description"),
                    country=country,
                )
            )

        return SearchResults(
            query=query,
            country=country,
            total_count=int(payload.get("resultCount", len(hits))),
            hits=hits,
        )
