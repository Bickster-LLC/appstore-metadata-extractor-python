"""Apple iTunes chart RSS client.

Pulls current chart positions from:

    https://itunes.apple.com/<cc>/rss/<chart>/limit=<N>/json
    https://itunes.apple.com/<cc>/rss/<chart>/limit=<N>/genre=<id>/json

This used to call the newer ``rss.marketingtools.apple.com`` endpoint, but
that endpoint silently 404s when a genre is supplied — so genre-filtered
charts could not actually be fetched. The legacy ``itunes.apple.com`` RSS is
the only Apple endpoint that still supports both overall and genre-filtered
charts at the time of writing.

Chart kinds are mapped to the legacy path segments:
``top-free`` → ``topfreeapplications``,
``top-paid`` → ``toppaidapplications``,
``top-grossing`` → ``topgrossingapplications``.

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
    """Async client for the iTunes chart RSS feed."""

    BASE_URL = "https://itunes.apple.com"
    DEFAULT_CACHE_TTL = 60 * 60  # 1 hour

    # Map the public chart kind to the legacy iTunes RSS path segment.
    _CHART_PATH_SEGMENT: Dict[str, str] = {
        "top-free": "topfreeapplications",
        "top-paid": "toppaidapplications",
        "top-grossing": "topgrossingapplications",
    }

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

        chart_segment = self._CHART_PATH_SEGMENT[chart]
        path = f"/{country}/rss/{chart_segment}/limit={clamped_limit}"
        if genre_id:
            path += f"/genre={genre_id}"
        path += "/json"
        url = f"{self.BASE_URL}{path}"

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
        """Parse the legacy iTunes RSS chart payload.

        Each entry sits under ``feed.entry`` and uses the typical Apple RSS
        namespaces (``im:name``, ``im:artist``, ``im:image``, ``category``).
        Rank is implicit in the entry order — the feed itself doesn't carry
        an explicit rank field — so we enumerate.
        """
        feed = payload.get("feed", {}) if isinstance(payload, dict) else {}
        raw_entries = feed.get("entry") or []
        # Apple occasionally returns a single entry as a dict, not a list.
        if isinstance(raw_entries, dict):
            raw_entries = [raw_entries]
        if not isinstance(raw_entries, list):
            raw_entries = []

        def _label(node: Any) -> Optional[str]:
            if isinstance(node, dict):
                value = node.get("label")
                return str(value) if value is not None else None
            return None

        entries: List[RankingEntry] = []
        for rank, item in enumerate(raw_entries, start=1):
            if not isinstance(item, dict):
                continue

            id_node = item.get("id") or {}
            id_attrs = id_node.get("attributes") if isinstance(id_node, dict) else None
            app_id = id_attrs.get("im:id") if isinstance(id_attrs, dict) else None
            if not app_id:
                continue
            apps_url = _label(id_node) if isinstance(id_node, dict) else None

            name = _label(item.get("im:name")) or ""
            developer_name = _label(item.get("im:artist")) or ""

            # The category node holds the primary genre id under
            # ``attributes['im:id']``. The legacy feed only lists this single
            # primary genre — secondary genres are not provided.
            category = item.get("category") or {}
            cat_attrs = (
                category.get("attributes") if isinstance(category, dict) else None
            )
            genre_ids: List[str] = []
            if isinstance(cat_attrs, dict):
                primary = cat_attrs.get("im:id")
                if primary is not None:
                    genre_ids.append(str(primary))

            # ``im:image`` is a list of icon URLs ordered low→high resolution.
            artwork_url: Optional[str] = None
            images = item.get("im:image")
            if isinstance(images, list) and images:
                artwork_url = _label(images[-1])

            entries.append(
                RankingEntry(
                    rank=rank,
                    app_id=str(app_id),
                    name=name,
                    developer_name=developer_name,
                    genre_ids=genre_ids,
                    artwork_url=artwork_url,
                    url=apps_url,
                )
            )

        return ChartSnapshot(
            chart=chart,
            country=country,
            genre_id=genre_id,
            entries=entries,
        )
