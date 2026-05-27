"""Unit smoke tests for CompositeAppStoreClient."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from appstore_metadata_extractor.core import (
    AppStoreRankingFetcher,
    AppStoreReviewExtractor,
    AppStoreSearcher,
    CombinedExtractor,
    CompositeAppStoreClient,
)
from appstore_metadata_extractor.core.cache import CacheManager, RateLimiter


def test_composite_uses_shared_rate_limiter_and_cache() -> None:
    rl = RateLimiter()
    cache = CacheManager()
    client = CompositeAppStoreClient(country="gb", rate_limiter=rl, cache_manager=cache)

    assert client.country == "gb"
    assert isinstance(client.metadata, CombinedExtractor)
    assert isinstance(client.search, AppStoreSearcher)
    assert isinstance(client.reviews, AppStoreReviewExtractor)
    assert isinstance(client.rankings, AppStoreRankingFetcher)

    # The new extractors share the same instances.
    assert client.search.rate_limiter is rl
    assert client.reviews.rate_limiter is rl
    assert client.rankings.rate_limiter is rl
    assert client.search.cache is cache
    assert client.reviews.cache is cache
    assert client.rankings.cache is cache


@pytest.mark.asyncio
async def test_composite_close_closes_three_extractors() -> None:
    client = CompositeAppStoreClient()
    client.search.close = AsyncMock()
    client.reviews.close = AsyncMock()
    client.rankings.close = AsyncMock()

    await client.close()

    client.search.close.assert_awaited_once()
    client.reviews.close.assert_awaited_once()
    client.rankings.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_composite_async_context_manager() -> None:
    client = CompositeAppStoreClient()
    client.search.close = AsyncMock()
    client.reviews.close = AsyncMock()
    client.rankings.close = AsyncMock()
    async with client as c:
        assert c is client
    client.search.close.assert_awaited_once()
