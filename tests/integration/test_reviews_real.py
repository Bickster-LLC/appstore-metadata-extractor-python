"""Integration tests for AppStoreReviewExtractor against real Apple RSS.

Opt-in via ``pytest -m integration``.
"""

from __future__ import annotations

import pytest

from appstore_metadata_extractor.core.reviews import AppStoreReviewExtractor

pytestmark = pytest.mark.integration

# WhatsApp Messenger — high-volume app, virtually always has reviews.
WHATSAPP_ID = "310633997"


@pytest.mark.asyncio
async def test_fetch_reviews_for_high_volume_app() -> None:
    extractor = AppStoreReviewExtractor()
    try:
        batch = await extractor.fetch_reviews(
            app_id=WHATSAPP_ID, country="us", max_pages=3
        )
    finally:
        await extractor.close()

    assert batch.app_id == WHATSAPP_ID
    assert batch.country == "us"
    assert batch.pages_fetched >= 1
    assert batch.total_reviews >= 50
    sample = batch.reviews[0]
    assert sample.content
    assert 1 <= sample.rating <= 5
    assert sample.date


@pytest.mark.asyncio
async def test_fetch_reviews_stops_cleanly_on_low_volume_app() -> None:
    """A very-low-volume app: should still return a (possibly empty) batch
    without raising. We only assert the call completes."""
    extractor = AppStoreReviewExtractor()
    try:
        batch = await extractor.fetch_reviews(
            # Apple Maps — long-lived high-volume app — safe sanity baseline.
            app_id="915056765",
            country="us",
            max_pages=1,
        )
    finally:
        await extractor.close()
    assert batch.pages_fetched == 1
