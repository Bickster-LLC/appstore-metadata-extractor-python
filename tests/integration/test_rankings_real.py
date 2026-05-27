"""Integration tests for AppStoreRankingFetcher against real Apple feeds."""

from __future__ import annotations

import pytest

from appstore_metadata_extractor.core.rankings import AppStoreRankingFetcher

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_fetch_top_free_us() -> None:
    fetcher = AppStoreRankingFetcher()
    try:
        snapshot = await fetcher.fetch_chart("top-free", country="us", limit=100)
    finally:
        await fetcher.close()
    assert len(snapshot.entries) >= 50
    first = snapshot.entries[0]
    assert first.rank == 1
    assert first.app_id
    assert first.name


@pytest.mark.asyncio
async def test_fetch_top_paid_respects_limit() -> None:
    fetcher = AppStoreRankingFetcher()
    try:
        snapshot = await fetcher.fetch_chart("top-paid", country="us", limit=10)
    finally:
        await fetcher.close()
    assert len(snapshot.entries) <= 10
    assert len(snapshot.entries) > 0


@pytest.mark.asyncio
async def test_find_app_rank_returns_int_or_none() -> None:
    """A guaranteed-absent ID should return None; we don't assume any specific
    real app is in the top-100 at all times."""
    fetcher = AppStoreRankingFetcher()
    try:
        rank = await fetcher.find_app_rank("0", "top-free", country="us", limit=10)
    finally:
        await fetcher.close()
    assert rank is None
