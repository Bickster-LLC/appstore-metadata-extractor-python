"""Unit tests for AppStoreRankingFetcher (core/rankings.py)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from appstore_metadata_extractor.core.cache import CacheManager, RateLimiter
from appstore_metadata_extractor.core.rankings import (
    AppStoreRankingFetcher,
    ChartSnapshot,
    RankingEntry,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def chart_payload() -> Dict[str, Any]:
    with (FIXTURES / "chart_top_free_us.json").open() as fh:
        return json.load(fh)


@pytest.fixture
def fetcher() -> AppStoreRankingFetcher:
    return AppStoreRankingFetcher(
        rate_limiter=RateLimiter(), cache_manager=CacheManager()
    )


def _mock_response(payload: Dict[str, Any]) -> MagicMock:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.text = AsyncMock(return_value=json.dumps(payload))
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=response)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _patch_session(fetcher: AppStoreRankingFetcher, response_mock: MagicMock):
    session = MagicMock()
    session.get = MagicMock(return_value=response_mock)
    return patch.object(fetcher, "_get_session", AsyncMock(return_value=session))


class TestChartParsing:
    @pytest.mark.asyncio
    async def test_parses_real_fixture(self, fetcher, chart_payload):
        with _patch_session(fetcher, _mock_response(chart_payload)):
            snapshot = await fetcher.fetch_chart("top-free", country="us")

        assert isinstance(snapshot, ChartSnapshot)
        assert snapshot.chart == "top-free"
        assert snapshot.country == "us"
        assert len(snapshot.entries) == len(chart_payload["feed"]["entry"])

    @pytest.mark.asyncio
    async def test_rank_is_one_indexed(self, fetcher, chart_payload):
        with _patch_session(fetcher, _mock_response(chart_payload)):
            snapshot = await fetcher.fetch_chart("top-free", country="us")

        assert snapshot.entries[0].rank == 1
        assert snapshot.entries[1].rank == 2
        assert snapshot.entries[-1].rank == len(snapshot.entries)

    @pytest.mark.asyncio
    async def test_entry_fields_populated(self, fetcher, chart_payload):
        with _patch_session(fetcher, _mock_response(chart_payload)):
            snapshot = await fetcher.fetch_chart("top-free", country="us")

        first = snapshot.entries[0]
        raw_first = chart_payload["feed"]["entry"][0]
        assert first.app_id == str(raw_first["id"]["attributes"]["im:id"])
        assert first.name == raw_first["im:name"]["label"]
        assert first.developer_name == raw_first["im:artist"]["label"]
        # The legacy feed lists icon URLs low→high resolution; the parser
        # keeps the largest variant.
        assert first.artwork_url == raw_first["im:image"][-1]["label"]
        # ``category.attributes['im:id']`` is the primary genre id.
        assert first.genre_ids == [str(raw_first["category"]["attributes"]["im:id"])]


class TestFindAppRank:
    @pytest.mark.asyncio
    async def test_find_present_app(self, fetcher, chart_payload):
        first_app_id = str(
            chart_payload["feed"]["entry"][0]["id"]["attributes"]["im:id"]
        )
        with _patch_session(fetcher, _mock_response(chart_payload)):
            rank = await fetcher.find_app_rank(first_app_id, "top-free")
        assert rank == 1

    @pytest.mark.asyncio
    async def test_find_absent_app_returns_none(self, fetcher, chart_payload):
        with _patch_session(fetcher, _mock_response(chart_payload)):
            rank = await fetcher.find_app_rank("0000000000", "top-free")
        assert rank is None


class TestRequestUrl:
    """Verify the URL built for the iTunes RSS endpoint, including genre filter.

    The previous Marketing Tools endpoint silently 404'd when a genre id was
    supplied; the legacy ``itunes.apple.com`` URL is the only path Apple still
    accepts for category-specific charts. Capturing the constructed URL here
    locks the path format so accidental refactors do not regress to a 404.
    """

    @pytest.mark.asyncio
    async def test_url_without_genre(self, fetcher, chart_payload):
        session = MagicMock()
        session.get = MagicMock(return_value=_mock_response(chart_payload))
        with patch.object(fetcher, "_get_session", AsyncMock(return_value=session)):
            await fetcher.fetch_chart("top-free", country="us", limit=50)
        called_url = session.get.call_args.args[0]
        assert called_url == (
            "https://itunes.apple.com/us/rss/topfreeapplications/limit=50/json"
        )

    @pytest.mark.asyncio
    async def test_url_with_genre(self, fetcher, chart_payload):
        session = MagicMock()
        session.get = MagicMock(return_value=_mock_response(chart_payload))
        with patch.object(fetcher, "_get_session", AsyncMock(return_value=session)):
            await fetcher.fetch_chart(
                "top-paid", country="us", limit=20, genre_id="6005"
            )
        called_url = session.get.call_args.args[0]
        assert called_url == (
            "https://itunes.apple.com/us/rss/toppaidapplications"
            "/limit=20/genre=6005/json"
        )


class TestCaching:
    @pytest.mark.asyncio
    async def test_cache_hit_skips_http(self, fetcher, chart_payload):
        session = MagicMock()
        session.get = MagicMock(return_value=_mock_response(chart_payload))
        with patch.object(fetcher, "_get_session", AsyncMock(return_value=session)):
            await fetcher.fetch_chart("top-free", country="us")
            await fetcher.fetch_chart("top-free", country="us")
        assert session.get.call_count == 1


class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_rate_limiter_consumed(self, chart_payload):
        rl = RateLimiter()
        fetcher = AppStoreRankingFetcher(rate_limiter=rl, cache_manager=CacheManager())
        with _patch_session(fetcher, _mock_response(chart_payload)):
            with patch.object(rl, "consume", wraps=rl.consume) as spy:
                await fetcher.fetch_chart("top-free", country="us")
        spy.assert_called_once_with("itunes_api")


def test_ranking_entry_validates_rank_floor() -> None:
    """rank must be >= 1 — Pydantic validation."""
    with pytest.raises(Exception):
        RankingEntry(rank=0, app_id="1", name="x", developer_name="y")
