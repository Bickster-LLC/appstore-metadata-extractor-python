"""Apple Marketing Tools chart RSS client.

Pulls current chart positions from:

    https://rss.marketingtools.apple.com/api/v2/<cc>/apps/<chart>/<limit>/apps.json
    https://rss.marketingtools.apple.com/api/v2/<cc>/apps/<chart>/<limit>/<genre_id>.json

The legacy hostname ``rss.applemarketingtools.com`` still resolves but
issues a 301 redirect; this client uses the canonical hostname.

Returns a *snapshot* — historical tracking is the consumer's responsibility.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Dict, List, Literal, Optional

import aiohttp
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from .cache import CacheManager, RateLimiter, get_cache_manager, get_rate_limiter
from .exceptions import NetworkError

ChartKind = Literal["top-free", "top-paid", "top-grossing"]

_RATE_LIMIT_SERVICE = "itunes_api"
_RATE_LIMIT_CALLS_PER_MINUTE = 20


class RankingEntry(BaseModel):
    """One entry in a chart, 1-indexed."""

    rank: int = Field(..., ge=1)
    app_id: str
    name: str
    developer_name: str
    genre_ids: List[str] = Field(default_factory=list)
    artwork_url: Optional[str] = None
    url: Optional[str] = Field(None, description="apps.apple.com URL if provided")


class ChartSnapshot(BaseModel):
    """Single point-in-time snapshot of a chart."""

    chart: ChartKind
    country: str
    genre_id: Optional[str] = Field(None, description="None for overall chart")
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    entries: List[RankingEntry] = Field(default_factory=list)


class AppStoreRankingFetcher:
    """Async client for the Apple Marketing Tools chart RSS feed."""

    BASE_URL = "https://rss.marketingtools.apple.com/api/v2"
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
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def fetch_chart(
        self,
        chart: ChartKind,
        country: str = "us",
        genre_id: Optional[str] = None,
        limit: int = 100,
    ) -> ChartSnapshot:
        """Get the current top-N apps in a chart."""
        clamped_limit = min(max(limit, 1), 200)
        cache_key = f"chart:{country}:{chart}:{genre_id or 'all'}:{clamped_limit}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return ChartSnapshot.model_validate(cached)

        suffix = f"{genre_id}.json" if genre_id else "apps.json"
        url = f"{self.BASE_URL}/{country}/apps/{chart}/{clamped_limit}/{suffix}"

        self.rate_limiter.consume(_RATE_LIMIT_SERVICE)

        session = await self._get_session()
        try:
            async with session.get(url, allow_redirects=True) as response:
                response.raise_for_status()
                text = await response.text()
        except aiohttp.ClientError as exc:
            raise NetworkError(
                f"Chart RSS request failed: {exc}", getattr(exc, "status", None)
            ) from exc

        try:
            payload = json.loads(text) if text else {}
        except json.JSONDecodeError as exc:
            raise NetworkError(f"Chart RSS returned invalid JSON: {exc}", None) from exc

        snapshot = self._parse(
            chart=chart, country=country, genre_id=genre_id, payload=payload
        )
        self.cache.set(cache_key, snapshot.model_dump(mode="json"), ttl=self.cache_ttl)
        return snapshot

    async def find_app_rank(
        self,
        app_id: str,
        chart: ChartKind,
        country: str = "us",
        genre_id: Optional[str] = None,
        limit: int = 100,
    ) -> Optional[int]:
        """Return the rank of an app within the requested chart, or None if absent."""
        snapshot = await self.fetch_chart(
            chart=chart, country=country, genre_id=genre_id, limit=limit
        )
        for entry in snapshot.entries:
            if entry.app_id == str(app_id):
                return entry.rank
        return None

    @staticmethod
    def _parse(
        chart: ChartKind,
        country: str,
        genre_id: Optional[str],
        payload: Dict[str, Any],
    ) -> ChartSnapshot:
        feed = payload.get("feed", {}) if isinstance(payload, dict) else {}
        raw_results = feed.get("results") or []

        entries: List[RankingEntry] = []
        for rank, item in enumerate(raw_results, start=1):
            if not isinstance(item, dict):
                continue
            raw_id = item.get("id")
            if not raw_id:
                continue

            # Genres can be missing, [], or [{genreId, name}].
            genres_raw = item.get("genres") or []
            genre_ids: List[str] = []
            for g in genres_raw:
                if isinstance(g, dict):
                    g_id = g.get("genreId") or g.get("id")
                    if g_id is not None:
                        genre_ids.append(str(g_id))

            entries.append(
                RankingEntry(
                    rank=rank,
                    app_id=str(raw_id),
                    name=item.get("name", ""),
                    developer_name=item.get("artistName", ""),
                    genre_ids=genre_ids,
                    artwork_url=item.get("artworkUrl100"),
                    url=item.get("url"),
                )
            )

        return ChartSnapshot(
            chart=chart,
            country=country,
            genre_id=genre_id,
            entries=entries,
        )
