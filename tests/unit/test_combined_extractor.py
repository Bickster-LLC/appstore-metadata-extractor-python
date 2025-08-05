"""Unit tests for CombinedExtractor."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from appstore_metadata_extractor.core import (
    AppMetadata,
    CombinedExtractor,
    DataSource,
    ExtendedAppMetadata,
    ExtractionMode,
    ExtractionResult,
    InAppPurchase,
    InAppPurchaseType,
    WBSConfig,
)


class TestCombinedExtractor:
    """Test CombinedExtractor class."""

    @pytest.fixture
    def wbs_config(self):
        """Create a WBS config for testing."""
        return WBSConfig()

    @pytest.fixture
    def combined_extractor(self, wbs_config):
        """Create a CombinedExtractor instance."""
        return CombinedExtractor(wbs_config)

    @pytest.fixture
    def mock_itunes_metadata(self):
        """Create mock iTunes API metadata."""
        return AppMetadata(
            app_id="123456789",
            bundle_id="com.example.app",
            url="https://apps.apple.com/app/id123456789",
            name="Test App",
            developer_name="Test Developer",
            category="Games",
            current_version="1.0.0",
            price=0.0,
            formatted_price="Free",
            currency="USD",
            icon_url="https://example.com/icon.png",
            data_source=DataSource.ITUNES_API,
            extracted_at=datetime.now(UTC),
        )

    @pytest.fixture
    def mock_web_metadata(self):
        """Create mock web scraping metadata with additional fields."""
        return ExtendedAppMetadata(
            app_id="123456789",
            url="https://apps.apple.com/app/id123456789",
            name="Test App",
            subtitle="Amazing Test App",
            developer_name="Test Developer",
            category="Games",
            current_version="1.0.0",
            price=0.0,
            formatted_price="Free",
            currency="USD",
            in_app_purchases=True,
            in_app_purchase_list=[
                InAppPurchase(
                    name="Premium Subscription",
                    price="$9.99",
                    price_value=9.99,
                    currency="USD",
                    type=InAppPurchaseType.AUTO_RENEWABLE_SUBSCRIPTION,
                )
            ],
            icon_url="https://example.com/icon.png",
            app_support_url="https://example.com/support",
            privacy_policy_url="https://example.com/privacy",
            developer_website_url="https://example.com",
            data_source=DataSource.WEB_SCRAPE,
            extracted_at=datetime.now(UTC),
        )

    @pytest.mark.asyncio
    async def test_extract_with_mode_itunes_only(
        self, combined_extractor, mock_itunes_metadata
    ):
        """Test extraction with iTunes API only mode."""
        url = "https://apps.apple.com/app/id123456789"

        # Mock iTunes extractor
        mock_result = ExtractionResult(
            app_id="123456789",
            success=True,
            metadata=mock_itunes_metadata,
            data_source=DataSource.ITUNES_API,
        )

        combined_extractor.itunes_extractor.extract = AsyncMock(
            return_value=mock_result
        )

        result = await combined_extractor.extract_with_mode(url, skip_web_scraping=True)

        assert result == mock_result
        combined_extractor.itunes_extractor.extract.assert_called_once_with(url)

    @pytest.mark.asyncio
    async def test_extract_with_mode_combined(
        self, combined_extractor, mock_itunes_metadata
    ):
        """Test extraction with combined mode."""
        url = "https://apps.apple.com/app/id123456789"

        # Mock extract method
        mock_result = ExtractionResult(
            app_id="123456789",
            success=True,
            metadata=mock_itunes_metadata,
            data_source=DataSource.COMBINED,
        )

        combined_extractor.extract = AsyncMock(return_value=mock_result)

        result = await combined_extractor.extract_with_mode(
            url, skip_web_scraping=False
        )

        assert result == mock_result
        combined_extractor.extract.assert_called_once_with(url)

    def test_fetch_synchronous_success(self, combined_extractor, mock_itunes_metadata):
        """Test synchronous fetch method with successful extraction."""
        url = "https://apps.apple.com/app/id123456789"

        mock_result = ExtractionResult(
            app_id="123456789",
            success=True,
            metadata=mock_itunes_metadata,
            data_source=DataSource.ITUNES_API,
        )

        with patch.object(
            combined_extractor, "extract_with_mode", new_callable=AsyncMock
        ) as mock_extract:
            mock_extract.return_value = mock_result

            metadata = combined_extractor.fetch(url, skip_web_scraping=True)

            assert metadata == mock_itunes_metadata
            assert metadata.bundle_id == "com.example.app"

    def test_fetch_synchronous_failure(self, combined_extractor):
        """Test synchronous fetch method with failed extraction."""
        url = "https://apps.apple.com/app/id123456789"

        mock_result = ExtractionResult(
            app_id="123456789",
            success=False,
            errors=["Network error", "Timeout"],
        )

        with patch.object(
            combined_extractor, "extract_with_mode", new_callable=AsyncMock
        ) as mock_extract:
            mock_extract.return_value = mock_result

            with pytest.raises(
                Exception, match="Failed to fetch metadata: Network error, Timeout"
            ):
                combined_extractor.fetch(url)

    @pytest.mark.asyncio
    async def test_fetch_batch_async(self, combined_extractor, mock_itunes_metadata):
        """Test async batch extraction."""
        urls = [
            "https://apps.apple.com/app/id123456789",
            "https://apps.apple.com/app/id987654321",
        ]

        mock_results = [
            ExtractionResult(
                app_id="123456789",
                success=True,
                metadata=mock_itunes_metadata,
            ),
            ExtractionResult(
                app_id="987654321",
                success=False,
                errors=["Not found"],
            ),
        ]

        with patch.object(
            combined_extractor, "extract_with_mode", new_callable=AsyncMock
        ) as mock_extract:
            mock_extract.side_effect = mock_results

            results = await combined_extractor.fetch_batch_async(
                urls, skip_web_scraping=True
            )

            assert len(results) == 2
            assert results[0].success is True
            assert results[1].success is False

    def test_merge_metadata(
        self, combined_extractor, mock_itunes_metadata, mock_web_metadata
    ):
        """Test metadata merging logic."""
        merged = combined_extractor._merge_metadata(
            mock_itunes_metadata, mock_web_metadata
        )

        # iTunes fields should be preserved
        assert merged.bundle_id == "com.example.app"
        assert merged.name == "Test App"

        # Web-only fields should be added
        assert merged.subtitle == "Amazing Test App"
        assert merged.in_app_purchases is True
        assert len(merged.in_app_purchase_list) == 1
        assert str(merged.app_support_url) == "https://example.com/support"
        assert str(merged.privacy_policy_url) == "https://example.com/privacy"
        assert str(merged.developer_website_url) == "https://example.com/"

        # Source should be marked as combined
        assert merged.data_source == DataSource.COMBINED

    @pytest.mark.asyncio
    async def test_fetch_combined_backward_compatibility(
        self, combined_extractor, mock_web_metadata
    ):
        """Test fetch_combined method returns backward-compatible result."""
        url = "https://apps.apple.com/app/id123456789"

        mock_result = ExtractionResult(
            app_id="123456789",
            success=True,
            metadata=mock_web_metadata,
            data_source=DataSource.COMBINED,
            warnings=["Some warning"],
        )

        with patch.object(
            combined_extractor, "extract_with_mode", new_callable=AsyncMock
        ) as mock_extract:
            mock_extract.return_value = mock_result

            result = await combined_extractor.fetch_combined(url)

            assert result.success is True
            assert result.app_metadata is not None
            assert result.app_metadata.bundle_id == mock_web_metadata.bundle_id
            # Check IAP list is converted to dict format
            assert len(result.app_metadata.in_app_purchase_list) == 1
            iap = result.app_metadata.in_app_purchase_list[0]
            assert iap["name"] == "Premium Subscription"
            assert iap["price"] == "$9.99"
            assert iap["price_value"] == "9.99"  # Should be string
            assert result.data_sources_used == [DataSource.COMBINED]
            assert result.warnings == ["Some warning"]

    def test_has_all_required_fields(self, combined_extractor):
        """Test checking for required fields."""
        # Create result with all required fields
        result = ExtractionResult(
            app_id="123",
            success=True,
            required_fields_present={
                "app_id",
                "name",
                "current_version",
                "developer_name",
                "price",
                "icon_url",
            },
        )

        assert combined_extractor._has_all_required_fields(result) is True

        # Create result missing some required fields
        result.required_fields_present = {"app_id", "name"}
        assert combined_extractor._has_all_required_fields(result) is False
