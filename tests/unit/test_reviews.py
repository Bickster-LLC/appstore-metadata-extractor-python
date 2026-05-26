"""Unit tests for AppStoreReviewExtractor (core/reviews.py)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from appstore_metadata_extractor.core.cache import CacheManager, RateLimiter
from appstore_metadata_extractor.core.reviews import (
    AppStoreReviewExtractor,
    ReviewBatch,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def reviews_payload() -> Dict[str, Any]:
    with (FIXTURES / "reviews_whatsapp_page1.json").open() as fh:
        return json.load(fh)


@pytest.fixture
def extractor() -> AppStoreReviewExtractor:
    return AppStoreReviewExtractor(
        rate_limiter=RateLimiter(),
        cache_manager=CacheManager(),
    )


def _aiohttp_response(*, status: int = 200, payload: Any = None) -> MagicMock:
    response = MagicMock()
    response.status = status
    if status >= 400:
        from aiohttp import ClientResponseError

        err = ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=status,
            message=f"HTTP {status}",
        )
        response.raise_for_status = MagicMock(side_effect=err)
    else:
        response.raise_for_status = MagicMock()
    response.text = AsyncMock(
        return_value=json.dumps(payload) if payload is not None else ""
    )
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=response)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _patch_pages(extractor: AppStoreReviewExtractor, page_responses: List[MagicMock]):
    """Return a session whose .get(...) returns one mock per call, in order."""
    session = MagicMock()
    session.get = MagicMock(side_effect=page_responses)
    return patch.object(extractor, "_get_session", AsyncMock(return_value=session))


class TestReviewParsing:
    """Map RSS entry → Review correctly."""

    @pytest.mark.asyncio
    async def test_parses_real_fixture(self, extractor, reviews_payload):
        with _patch_pages(extractor, [_aiohttp_response(payload=reviews_payload)]):
            batch = await extractor.fetch_reviews(
                app_id="310633997", max_pages=1, early_stop_on_empty=False
            )

        assert isinstance(batch, ReviewBatch)
        assert batch.app_id == "310633997"
        assert batch.country == "us"
        assert batch.sort == "mostrecent"
        assert batch.pages_fetched == 1
        # Fixture has 50 review entries — all should parse.
        assert batch.total_reviews == 50
        first = batch.reviews[0]
        assert first.author
        assert 1 <= first.rating <= 5
        assert first.content  # may be short but should not be empty
        # Helpful count must coerce to int.
        assert isinstance(first.helpful_count, int)

    def test_parse_entry_rejects_non_review(self):
        """Entries without im:rating (e.g. legacy feed-metadata entry 0)
        must be filtered out, not returned as fake reviews."""
        feed_meta = {
            "id": {"label": "feed-self"},
            "title": {"label": "WhatsApp Messenger"},
            "updated": {"label": "2024-01-01T00:00:00Z"},
        }
        assert AppStoreReviewExtractor._parse_entry(feed_meta) is None


class TestPagination:
    """End-of-data signals: 404 or empty entries."""

    @pytest.mark.asyncio
    async def test_stops_on_404(self, extractor, reviews_payload):
        page1 = _aiohttp_response(payload=reviews_payload)
        page2 = _aiohttp_response(status=404)
        with _patch_pages(extractor, [page1, page2]):
            batch = await extractor.fetch_reviews(app_id="310633997", max_pages=5)

        assert batch.pages_fetched == 2
        assert any("404" in n for n in batch.notes)
        # Reviews from page 1 still present.
        assert batch.total_reviews == 50

    @pytest.mark.asyncio
    async def test_stops_on_empty_page(self, extractor, reviews_payload):
        empty_payload = {"feed": {"entry": []}}
        page1 = _aiohttp_response(payload=reviews_payload)
        page2 = _aiohttp_response(payload=empty_payload)
        with _patch_pages(extractor, [page1, page2]):
            batch = await extractor.fetch_reviews(
                app_id="310633997", max_pages=5, early_stop_on_empty=True
            )

        assert batch.pages_fetched == 2
        assert any("empty" in n for n in batch.notes)

    @pytest.mark.asyncio
    async def test_dedup_across_pages(self, extractor, reviews_payload):
        # Same fixture twice → all dups, count stays at 50.
        page1 = _aiohttp_response(payload=reviews_payload)
        page2 = _aiohttp_response(payload=reviews_payload)
        page3 = _aiohttp_response(status=404)
        with _patch_pages(extractor, [page1, page2, page3]):
            batch = await extractor.fetch_reviews(app_id="310633997", max_pages=3)

        assert batch.pages_fetched == 3
        # All page-2 entries duplicate page-1 → still 50 unique reviews.
        assert batch.total_reviews == 50

    @pytest.mark.asyncio
    async def test_max_pages_clamped_to_10(self, extractor):
        """max_pages > 10 should not exceed Apple's hard cap."""
        # 11 404 responses; only 1 should actually be requested.
        pages = [_aiohttp_response(status=404) for _ in range(20)]
        with _patch_pages(extractor, pages):
            batch = await extractor.fetch_reviews(app_id="310633997", max_pages=99)
        # First page is 404 → only 1 page actually fetched.
        assert batch.pages_fetched == 1


class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_rate_limiter_invoked_once_per_page(self, reviews_payload):
        rl = RateLimiter()
        extractor = AppStoreReviewExtractor(
            rate_limiter=rl, cache_manager=CacheManager()
        )
        page1 = _aiohttp_response(payload=reviews_payload)
        page2 = _aiohttp_response(status=404)
        with _patch_pages(extractor, [page1, page2]):
            with patch.object(rl, "consume", wraps=rl.consume) as spy:
                await extractor.fetch_reviews(app_id="310633997", max_pages=3)
        # One real fetch + one 404 fetch = 2 rate-limit consumes.
        assert spy.call_count == 2


class TestCaching:
    @pytest.mark.asyncio
    async def test_cache_hit_skips_http(self, extractor, reviews_payload):
        page1 = _aiohttp_response(payload=reviews_payload)
        # Only one response — a second call without cache would error.
        with _patch_pages(extractor, [page1]):
            await extractor.fetch_reviews(
                app_id="310633997", max_pages=1, early_stop_on_empty=False
            )

        # Now call again with no responses queued — should be served from cache.
        empty_session = MagicMock()
        empty_session.get = MagicMock(
            side_effect=AssertionError("should not call HTTP on cache hit")
        )
        with patch.object(
            extractor, "_get_session", AsyncMock(return_value=empty_session)
        ):
            batch = await extractor.fetch_reviews(
                app_id="310633997", max_pages=1, early_stop_on_empty=False
            )
        assert batch.total_reviews == 50


class TestBatchFetch:
    @pytest.mark.asyncio
    async def test_fetch_batch_runs_for_all_apps(self, extractor, reviews_payload):
        async def fake_fetch(app_id, country="us", sort="mostrecent", max_pages=10):
            return ReviewBatch(
                app_id=app_id,
                country=country,
                sort=sort,
                pages_fetched=1,
                total_reviews=1,
            )

        with patch.object(extractor, "fetch_reviews", side_effect=fake_fetch):
            results = await extractor.fetch_reviews_batch(
                app_ids=["1", "2", "3"], max_concurrent=2
            )
        assert set(results.keys()) == {"1", "2", "3"}
        assert all(r.total_reviews == 1 for r in results.values())
