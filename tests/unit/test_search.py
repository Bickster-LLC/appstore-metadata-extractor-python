"""Unit tests for AppStoreSearcher (core/search.py)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from appstore_metadata_extractor.core.cache import CacheManager, RateLimiter
from appstore_metadata_extractor.core.search import (
    AppStoreSearcher,
    SearchHit,
    SearchResults,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def search_payload() -> Dict[str, Any]:
    """Load the captured iTunes Search response."""
    with (FIXTURES / "search_habit_tracker.json").open() as fh:
        return json.load(fh)


@pytest.fixture
def searcher() -> AppStoreSearcher:
    """A searcher with isolated cache + rate-limiter to keep tests independent."""
    return AppStoreSearcher(
        rate_limiter=RateLimiter(),
        cache_manager=CacheManager(),
    )


def _mock_response(payload: Dict[str, Any]) -> MagicMock:
    """Build an aiohttp-like async context manager that yields ``payload``."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.text = AsyncMock(return_value=json.dumps(payload))
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=response)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


class TestSearchHitParsing:
    """Verify iTunes search fields map to SearchHit correctly."""

    @pytest.mark.asyncio
    async def test_parses_all_fields(self, searcher, search_payload):
        cm = _mock_response(search_payload)
        with patch.object(searcher, "_get_session") as get_session:
            session = MagicMock()
            session.get = MagicMock(return_value=cm)
            get_session.return_value = session

            results = await searcher.search("habit tracker")

        assert isinstance(results, SearchResults)
        assert results.query == "habit tracker"
        assert results.country == "us"
        assert results.total_count == search_payload["resultCount"]
        assert len(results.hits) == len(search_payload["results"])

        first = results.hits[0]
        raw = search_payload["results"][0]
        assert first.app_id == str(raw["trackId"])
        assert first.name == raw["trackName"]
        assert first.developer_name == raw["artistName"]
        assert first.url == raw["trackViewUrl"]
        assert first.primary_category == raw["primaryGenreName"]
        assert first.country == "us"

    @pytest.mark.asyncio
    async def test_handles_zero_results(self, searcher):
        cm = _mock_response({"resultCount": 0, "results": []})
        with patch.object(searcher, "_get_session") as get_session:
            session = MagicMock()
            session.get = MagicMock(return_value=cm)
            get_session.return_value = session

            results = await searcher.search("zzzzz no match")

        assert results.total_count == 0
        assert results.hits == []

    @pytest.mark.asyncio
    async def test_empty_query_short_circuits(self, searcher):
        """Empty query returns an empty SearchResults without an HTTP call."""
        with patch.object(searcher, "_get_session") as get_session:
            results = await searcher.search("   ")
            get_session.assert_not_called()
        assert results.total_count == 0
        assert results.hits == []

    @pytest.mark.asyncio
    async def test_missing_optional_fields(self, searcher):
        payload = {
            "resultCount": 1,
            "results": [
                {
                    "trackId": 999,
                    "trackName": "Bare Bones",
                    "artistName": "Solo Dev",
                    "trackViewUrl": "https://apps.apple.com/us/app/bare/id999",
                }
            ],
        }
        cm = _mock_response(payload)
        with patch.object(searcher, "_get_session") as get_session:
            session = MagicMock()
            session.get = MagicMock(return_value=cm)
            get_session.return_value = session

            results = await searcher.search("bare")

        assert len(results.hits) == 1
        hit = results.hits[0]
        assert hit.app_id == "999"
        assert hit.icon_url is None
        assert hit.average_rating is None
        assert hit.primary_category is None


class TestSearchCaching:
    """Cache hits should short-circuit HTTP."""

    @pytest.mark.asyncio
    async def test_cache_hit_skips_http(self, searcher, search_payload):
        cm = _mock_response(search_payload)
        with patch.object(searcher, "_get_session") as get_session:
            session = MagicMock()
            session.get = MagicMock(return_value=cm)
            get_session.return_value = session

            first = await searcher.search("habit tracker")
            second = await searcher.search("habit tracker")

            # Only one HTTP call across two .search() invocations.
            assert session.get.call_count == 1
        assert first.total_count == second.total_count
        assert len(first.hits) == len(second.hits)


class TestSearchRateLimiting:
    """Rate limiter must be consumed for each network fetch."""

    @pytest.mark.asyncio
    async def test_rate_limiter_consumed(self, search_payload):
        rl = RateLimiter()
        searcher = AppStoreSearcher(rate_limiter=rl, cache_manager=CacheManager())
        cm = _mock_response(search_payload)
        with patch.object(searcher, "_get_session") as get_session:
            session = MagicMock()
            session.get = MagicMock(return_value=cm)
            get_session.return_value = session

            with patch.object(rl, "consume", wraps=rl.consume) as consume_spy:
                await searcher.search("habit tracker")
            consume_spy.assert_called_once_with("itunes_api")


class TestSearchByGenre:
    """Genre-only search uses term='*' and supplies the genre ID."""

    @pytest.mark.asyncio
    async def test_search_by_genre_passes_genre_id(self, searcher, search_payload):
        cm = _mock_response(search_payload)
        with patch.object(searcher, "_get_session") as get_session:
            session = MagicMock()
            session.get = MagicMock(return_value=cm)
            get_session.return_value = session

            results = await searcher.search_by_genre(6017, country="us", limit=10)

            call_kwargs = session.get.call_args.kwargs
            params = call_kwargs.get("params") or session.get.call_args.args[1]
            if isinstance(params, dict):
                assert params["genreId"] == 6017
                assert params["country"] == "us"
                assert params["limit"] == 10
        assert results.query == "genre:6017"


class TestHitModel:
    """Sanity tests on SearchHit itself."""

    def test_hit_serializes(self):
        hit = SearchHit(
            app_id="1",
            name="Test",
            developer_name="Dev",
            url="https://apps.apple.com/us/app/test/id1",
        )
        dumped = hit.model_dump()
        assert dumped["app_id"] == "1"
        assert dumped["country"] == "us"
