"""Apple RSS customer reviews client.

Pulls paginated reviews from:

    https://itunes.apple.com/<cc>/rss/customerreviews/page=<N>/id=<app_id>/sortby=<sort>/json

Apple caps pagination at 10 pages (~50 reviews each). Beyond page 10 the
endpoint returns 404. Some apps return fewer pages — we stop on 404 or on
an empty page.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any, Dict, List, Literal, Optional

import aiohttp
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from ..models_combined import Review
from .cache import CacheManager, RateLimiter, get_cache_manager, get_rate_limiter
from .exceptions import NetworkError

SortOrder = Literal["mostrecent", "mosthelpful"]

_RATE_LIMIT_SERVICE = "itunes_api"
_RATE_LIMIT_CALLS_PER_MINUTE = 20
_MAX_APPLE_PAGES = 10


class ReviewBatch(BaseModel):
    """Paginated review results for one app."""

    app_id: str
    country: str
    sort: SortOrder
    pages_fetched: int = Field(
        ..., description="Pages actually fetched (≤ requested max_pages)"
    )
    total_reviews: int = Field(..., description="len(reviews) after dedup")
    reviews: List[Review] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    has_more: bool = Field(
        False,
        description="True if we stopped at max_pages rather than end-of-data",
    )
    notes: List[str] = Field(
        default_factory=list,
        description="Diagnostic notes (e.g. 'page 5: 404 — end of data')",
    )


class AppStoreReviewExtractor:
    """Paginated review extractor.

    Shares the ``itunes_api`` rate-limit budget with other extractors.
    """

    BASE_URL_TEMPLATE = (
        "https://itunes.apple.com/{country}/rss/customerreviews/"
        "page={page}/id={app_id}/sortby={sort}/json"
    )
    DEFAULT_CACHE_TTL = 60 * 60 * 24  # 24 hours

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

    async def fetch_reviews(
        self,
        app_id: str,
        country: str = "us",
        sort: SortOrder = "mostrecent",
        max_pages: int = 10,
        early_stop_on_empty: bool = True,
    ) -> ReviewBatch:
        """Fetch reviews for a single app across multiple pages.

        Dedups by review id across pages (the RSS feed sometimes returns
        duplicates when reviews shift positions while paginating).

        Args:
            app_id: Apple track ID (the number after ``id`` in the App Store URL).
            country: ISO 3166-1 alpha-2 storefront code.
            sort: ``mostrecent`` or ``mosthelpful``.
            max_pages: Apple caps at 10; values >10 are clamped.
            early_stop_on_empty: Stop when a page returns no review entries.
        """
        max_pages = max(1, min(max_pages, _MAX_APPLE_PAGES))
        all_reviews: List[Review] = []
        seen_ids: set[str] = set()
        notes: List[str] = []
        pages_fetched = 0
        stopped_early = False

        for page in range(1, max_pages + 1):
            page_reviews, page_note, ended = await self._fetch_page(
                app_id=app_id, country=country, sort=sort, page=page
            )
            pages_fetched += 1
            if page_note:
                notes.append(page_note)
            for review, review_id in page_reviews:
                if review_id and review_id in seen_ids:
                    continue
                if review_id:
                    seen_ids.add(review_id)
                all_reviews.append(review)
            if ended:
                stopped_early = True
                break
            if early_stop_on_empty and not page_reviews:
                notes.append(f"page {page}: empty — stopping")
                stopped_early = True
                break

        has_more = (
            not stopped_early
            and pages_fetched == max_pages
            and pages_fetched < _MAX_APPLE_PAGES
        )

        return ReviewBatch(
            app_id=str(app_id),
            country=country,
            sort=sort,
            pages_fetched=pages_fetched,
            total_reviews=len(all_reviews),
            reviews=all_reviews,
            has_more=has_more,
            notes=notes,
        )

    async def fetch_reviews_batch(
        self,
        app_ids: List[str],
        country: str = "us",
        sort: SortOrder = "mostrecent",
        max_pages: int = 10,
        max_concurrent: int = 5,
    ) -> Dict[str, ReviewBatch]:
        """Fetch reviews for many apps concurrently.

        Concurrency is capped via ``asyncio.Semaphore``; the underlying
        rate-limit bucket is still global.
        """
        semaphore = asyncio.Semaphore(max(1, max_concurrent))

        async def run(app_id: str) -> tuple[str, ReviewBatch]:
            async with semaphore:
                batch = await self.fetch_reviews(
                    app_id=app_id,
                    country=country,
                    sort=sort,
                    max_pages=max_pages,
                )
                return app_id, batch

        results = await asyncio.gather(*(run(a) for a in app_ids))
        return dict(results)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def _fetch_page(
        self,
        app_id: str,
        country: str,
        sort: SortOrder,
        page: int,
    ) -> tuple[List[tuple[Review, Optional[str]]], Optional[str], bool]:
        """Fetch one page.

        Returns ``(reviews_with_ids, note, end_of_data)``.
        - ``end_of_data=True`` means stop pagination (404 or empty entries).
        """
        cache_key = f"reviews:{country}:{app_id}:{sort}:p{page}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            data = cached
        else:
            self.rate_limiter.consume(_RATE_LIMIT_SERVICE)
            url = self.BASE_URL_TEMPLATE.format(
                country=country, page=page, app_id=app_id, sort=sort
            )
            session = await self._get_session()
            try:
                async with session.get(url) as response:
                    if response.status == 404:
                        return [], f"page {page}: 404 — end of data", True
                    response.raise_for_status()
                    text = await response.text()
            except aiohttp.ClientError as exc:
                status = getattr(exc, "status", None)
                if status == 404:
                    return [], f"page {page}: 404 — end of data", True
                raise NetworkError(
                    f"Reviews feed request failed (page={page}): {exc}", status
                ) from exc

            try:
                data = json.loads(text) if text else {}
            except json.JSONDecodeError as exc:
                raise NetworkError(
                    f"Reviews feed returned invalid JSON (page={page}): {exc}",
                    None,
                ) from exc

            self.cache.set(cache_key, data, ttl=self.cache_ttl)

        feed = data.get("feed", {}) if isinstance(data, dict) else {}
        raw_entries = feed.get("entry", [])
        # Apple sometimes returns a single entry as a dict, not a list.
        if isinstance(raw_entries, dict):
            raw_entries = [raw_entries]
        if not isinstance(raw_entries, list):
            raw_entries = []

        parsed: List[tuple[Review, Optional[str]]] = []
        for entry in raw_entries:
            if not isinstance(entry, dict):
                continue
            review = self._parse_entry(entry)
            if review is None:
                continue
            review_id = (
                entry.get("id", {}).get("label")
                if isinstance(entry.get("id"), dict)
                else None
            )
            parsed.append((review, review_id))

        return parsed, None, False

    @staticmethod
    def _parse_entry(entry: Dict[str, Any]) -> Optional[Review]:
        """Convert one RSS entry into a Review.

        Returns None if the entry lacks review-specific fields (e.g. the
        legacy XML feed sometimes emits the feed metadata as entry 0). We
        treat presence of ``im:rating`` as the signal that this is a review.
        """
        rating_node = entry.get("im:rating")
        if not isinstance(rating_node, dict) or "label" not in rating_node:
            return None

        try:
            rating = int(rating_node["label"])
        except (TypeError, ValueError):
            return None
        if not 1 <= rating <= 5:
            return None

        def _label(node: Any) -> Optional[str]:
            if isinstance(node, dict):
                value = node.get("label")
                return str(value) if value is not None else None
            return None

        author_node = entry.get("author", {})
        author_name = ""
        if isinstance(author_node, dict):
            name_node = author_node.get("name")
            if isinstance(name_node, dict):
                author_name = str(name_node.get("label", ""))

        content = _label(entry.get("content")) or ""
        title = _label(entry.get("title"))
        version = _label(entry.get("im:version"))
        updated_label = _label(entry.get("updated"))

        if updated_label:
            try:
                review_date = datetime.fromisoformat(updated_label)
            except ValueError:
                review_date = datetime.now(UTC)
        else:
            review_date = datetime.now(UTC)

        helpful_label = _label(entry.get("im:voteSum"))
        try:
            helpful_count = int(helpful_label) if helpful_label else 0
        except (TypeError, ValueError):
            helpful_count = 0

        return Review(
            author=author_name or "Anonymous",
            rating=rating,
            title=title,
            content=content,
            date=review_date,
            version=version,
            helpful_count=helpful_count,
        )
