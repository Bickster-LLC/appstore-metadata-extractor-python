"""Integration tests for AppStoreSearcher against the real iTunes Search API.

Marked ``integration``; opt-in via ``pytest -m integration``.
"""

from __future__ import annotations

import pytest

from appstore_metadata_extractor.core.search import AppStoreSearcher

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_search_returns_results_for_common_term() -> None:
    searcher = AppStoreSearcher()
    try:
        results = await searcher.search("habit tracker", country="us", limit=25)
    finally:
        await searcher.close()

    assert results.total_count > 0
    assert len(results.hits) >= 5
    for hit in results.hits[:5]:
        assert hit.app_id
        assert hit.name
        assert hit.url.startswith("https://")


@pytest.mark.asyncio
async def test_empty_term_returns_empty_hits() -> None:
    searcher = AppStoreSearcher()
    try:
        results = await searcher.search("", country="us")
    finally:
        await searcher.close()
    assert results.hits == []


@pytest.mark.asyncio
async def test_genre_search_returns_lifestyle_apps() -> None:
    """Genre 6012 = Lifestyle. Result count should be >0."""
    searcher = AppStoreSearcher()
    try:
        results = await searcher.search_by_genre(6012, country="us", limit=10)
    finally:
        await searcher.close()
    assert results.total_count > 0
    assert len(results.hits) > 0
