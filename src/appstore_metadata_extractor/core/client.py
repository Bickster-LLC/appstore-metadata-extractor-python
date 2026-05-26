"""Composite App Store client bundling search, metadata, reviews, and rankings.

Shares a single ``RateLimiter`` and ``CacheManager`` across all four
extractors so the per-IP Apple budget is honored on every call.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from .cache import CacheManager, RateLimiter, get_cache_manager, get_rate_limiter
from .extractors import CombinedExtractor
from .models import WBSConfig
from .rankings import AppStoreRankingFetcher
from .reviews import AppStoreReviewExtractor
from .search import AppStoreSearcher


class CompositeAppStoreClient:
    """One-stop client wrapping the four App Store extractors.

    Example:
        client = CompositeAppStoreClient(country="us")
        try:
            hits = await client.search.search("habit tracker")
            for hit in hits.hits:
                meta = client.metadata.fetch(hit.url)
                reviews = await client.reviews.fetch_reviews(hit.app_id)
                rank = await client.rankings.find_app_rank(
                    hit.app_id, "top-free"
                )
        finally:
            await client.close()
    """

    def __init__(
        self,
        country: str = "us",
        rate_limiter: Optional[RateLimiter] = None,
        cache_manager: Optional[CacheManager] = None,
        wbs_config: Optional[WBSConfig] = None,
        timeout: int = 30,
    ) -> None:
        self.country = country
        self.rate_limiter = rate_limiter or get_rate_limiter()
        self.cache_manager = cache_manager or get_cache_manager()
        self.wbs_config = wbs_config or WBSConfig(
            what="CompositeAppStoreClient default configuration"
        )

        # Metadata extractor (existing) uses its own constructor signature.
        self.metadata = CombinedExtractor(self.wbs_config, timeout=timeout)

        # New extractors all share the rate limiter and cache.
        self.search = AppStoreSearcher(
            rate_limiter=self.rate_limiter,
            cache_manager=self.cache_manager,
            timeout=timeout,
        )
        self.reviews = AppStoreReviewExtractor(
            rate_limiter=self.rate_limiter,
            cache_manager=self.cache_manager,
            timeout=timeout,
        )
        self.rankings = AppStoreRankingFetcher(
            rate_limiter=self.rate_limiter,
            cache_manager=self.cache_manager,
            timeout=timeout,
        )

    async def close(self) -> None:
        """Release HTTP sessions on the three new extractors.

        ``CombinedExtractor`` creates aiohttp sessions per-call and closes
        them immediately, so it does not need an explicit close.
        """
        await asyncio.gather(
            self.search.close(),
            self.reviews.close(),
            self.rankings.close(),
        )

    async def __aenter__(self) -> "CompositeAppStoreClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()
