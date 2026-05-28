"""Clean unit tests for the extractors module - only working tests."""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from appstore_metadata_extractor.core.exceptions import ValidationError
from appstore_metadata_extractor.core.extractors import (
    BaseExtractor,
    CombinedExtractor,
    ITunesAPIExtractor,
    WebScraperExtractor,
)
from appstore_metadata_extractor.core.models import (
    AppMetadata,
    DataSource,
    ExtractionMode,
    ExtractionResult,
    WBSConfig,
)


def test_apply_country_to_url_rewrites_storefront() -> None:
    """WebScraperExtractor rewrites the /<cc>/app/ segment to match country."""
    url = "https://apps.apple.com/us/app/whatsapp-messenger/id310633997"
    rewritten = WebScraperExtractor._apply_country_to_url(url, "gb")
    assert rewritten == "https://apps.apple.com/gb/app/whatsapp-messenger/id310633997"


def test_apply_country_to_url_idempotent_for_same_country() -> None:
    """Rewriting to the same country leaves the URL unchanged."""
    url = "https://apps.apple.com/us/app/foo/id1"
    assert WebScraperExtractor._apply_country_to_url(url, "us") == url


def test_apply_country_to_url_unchanged_when_no_storefront() -> None:
    """URLs without a /<cc>/app/ segment are returned unchanged."""
    url = "https://apps.apple.com/app/id1"
    assert WebScraperExtractor._apply_country_to_url(url, "gb") == url


class ConcreteExtractor(BaseExtractor):
    """Concrete implementation of BaseExtractor for testing."""

    async def extract(self, url: str, country: str = "us") -> ExtractionResult:
        """Simple extract implementation."""
        return ExtractionResult(
            app_id="123456789",
            success=True,
            metadata=AppMetadata(
                app_id="123456789",
                url=url,
                name="Test App",
                developer_name="Test Developer",
                category="Games",
                current_version="1.0.0",
                icon_url="https://example.com/icon.png",
                data_source=DataSource.ITUNES_API,
                extracted_at=datetime.now(UTC),
            ),
        )


class TestBaseExtractor:
    """Test BaseExtractor abstract class."""

    @pytest.fixture
    def wbs_config(self):
        """Create a WBS config for testing."""
        return WBSConfig()

    @pytest.fixture
    def concrete_extractor(self, wbs_config):
        """Create a concrete extractor instance."""
        return ConcreteExtractor(wbs_config)

    def test_init(self, concrete_extractor, wbs_config):
        """Test base extractor initialization."""
        assert concrete_extractor.wbs_config == wbs_config
        assert concrete_extractor.timeout == 30
        assert concrete_extractor.validator is not None
        assert concrete_extractor.cache is not None
        assert concrete_extractor.rate_limiter is not None
        assert "User-Agent" in concrete_extractor.headers

    @pytest.mark.asyncio
    async def test_extract_with_validation(self, concrete_extractor):
        """Test extraction with WBS validation."""
        with patch.object(concrete_extractor.validator, "enforce_boundaries"):
            with patch.object(concrete_extractor.validator, "validate"):
                result = await concrete_extractor.extract_with_validation(
                    "https://apps.apple.com/app/id123456789"
                )

                assert result.success is True
                assert result.extraction_duration_seconds > 0
                concrete_extractor.validator.enforce_boundaries.assert_called_once()
                concrete_extractor.validator.validate.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_with_validation_error(self, concrete_extractor):
        """Test extraction with validation error."""
        with patch.object(
            concrete_extractor.validator, "enforce_boundaries"
        ) as mock_enforce:
            mock_enforce.side_effect = ValidationError("test", "value", "expected")

            result = await concrete_extractor.extract_with_validation(
                "https://apps.apple.com/app/id123456789"
            )

            assert result.success is False
            assert len(result.errors) > 0
            assert "Validation failed" in result.errors[0]


class TestITunesAPIExtractor:
    """Test ITunesAPIExtractor class - only working tests."""

    @pytest.fixture
    def wbs_config(self):
        """Create a WBS config for testing."""
        return WBSConfig()

    @pytest.fixture
    def itunes_extractor(self, wbs_config):
        """Create an ITunesAPIExtractor instance."""
        return ITunesAPIExtractor(wbs_config)

    def test_init(self, itunes_extractor):
        """Test iTunes extractor initialization."""
        assert itunes_extractor.base_url == "https://itunes.apple.com/lookup"
        assert hasattr(itunes_extractor, "rate_limiter")

    def test_extract_app_id(self, itunes_extractor):
        """Test extracting app ID from URL."""
        # Valid URLs
        assert (
            itunes_extractor._extract_app_id(
                "https://apps.apple.com/us/app/test/id123456789"
            )
            == "123456789"
        )
        assert (
            itunes_extractor._extract_app_id("https://apps.apple.com/app/id987654321")
            == "987654321"
        )

        # Invalid URLs
        assert (
            itunes_extractor._extract_app_id("https://apps.apple.com/us/app/test")
            is None
        )
        assert itunes_extractor._extract_app_id("https://example.com") is None

    @pytest.mark.asyncio
    async def test_extract_from_cache(self, itunes_extractor):
        """Test extraction returns cached data."""
        cached_metadata = {
            "app_id": "123456789",
            "name": "Cached App",
            "developer_name": "Cached Developer",
            "category": "Games",
            "current_version": "1.0.0",
            "icon_url": "https://example.com/icon.png",
            "url": "https://apps.apple.com/app/id123456789",
            "data_source": "itunes_api",
            "extracted_at": datetime.now(UTC).isoformat(),
        }

        with patch.object(itunes_extractor.cache, "get", return_value=cached_metadata):
            result = await itunes_extractor.extract(
                "https://apps.apple.com/us/app/test/id123456789"
            )

            assert result.success is True
            assert result.from_cache is True
            assert result.metadata.name == "Cached App"


class TestWebScraperExtractor:
    """Test WebScraperExtractor class - only working tests."""

    @pytest.fixture
    def wbs_config(self):
        """Create a WBS config for testing."""
        return WBSConfig()

    @pytest.fixture
    def web_extractor(self, wbs_config):
        """Create a WebScraperExtractor instance."""
        return WebScraperExtractor(wbs_config)

    def test_init(self, web_extractor):
        """Test web scraper initialization."""
        assert hasattr(web_extractor, "wbs_config")
        assert hasattr(web_extractor, "timeout")

    def test_extract_subtitle_new_svelte_format(self, web_extractor):
        """Subtitle is read from the Svelte <p class='subtitle'> element.

        Apple migrated the product page to a Svelte frontend; the subtitle
        moved from <h2 class='product-header__subtitle'> to
        <p class='subtitle svelte-XXXXX'>. The svelte-XXXXX hash is volatile,
        so only the stable 'subtitle' token is matched.
        """
        from bs4 import BeautifulSoup

        html = (
            '<section class="svelte-kps97o">'
            '<p class="subtitle svelte-kps97o">Simple. Reliable. Private.</p>'
            "</section>"
        )
        soup = BeautifulSoup(html, "lxml")
        assert web_extractor._extract_subtitle(soup) == "Simple. Reliable. Private."

    def test_extract_subtitle_legacy_format(self, web_extractor):
        """The legacy <h2 class='product-header__subtitle'> still works."""
        from bs4 import BeautifulSoup

        html = '<h2 class="product-header__subtitle">Legacy Subtitle</h2>'
        soup = BeautifulSoup(html, "lxml")
        assert web_extractor._extract_subtitle(soup) == "Legacy Subtitle"

    def test_extract_subtitle_absent(self, web_extractor):
        """No subtitle element returns None."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup("<div>no subtitle here</div>", "lxml")
        assert web_extractor._extract_subtitle(soup) is None

    def test_extract_in_app_purchases_new_svelte_format(self, web_extractor):
        """IAPs are read from the Svelte text-pair definition list.

        Apple migrated the product page to a Svelte frontend; the IAP list moved
        from <li class='list-with-numbers__item'> spans to
        <dt>In-App Purchases</dt><dd><details><ul><li>
        <div class='text-pair'><span>Name</span><span>$Price</span></div>.
        The svelte-XXXXX hashes are volatile, so only the stable 'text-pair'
        token and the dt label are matched. The trailing 'Learn More' row, which
        carries no price, must be skipped.
        """
        from bs4 import BeautifulSoup

        html = (
            "<dl>"
            "<dt>In-App Purchases</dt>"
            '<dd><details class="svelte-abc"><summary>Yes</summary><ul>'
            '<li class="svelte-xyz"><div class="text-pair svelte-xyz">'
            "<span>Monthly Plan</span><span>$9.99</span></div></li>"
            '<li class="svelte-xyz"><div class="text-pair svelte-xyz">'
            "<span>Lifetime</span><span>$49.99</span></div></li>"
            '<li class="svelte-xyz"><a href="#">Learn More</a></li>'
            "</ul></details></dd>"
            "</dl>"
        )
        soup = BeautifulSoup(html, "lxml")
        iaps = web_extractor._extract_in_app_purchases(soup)

        assert len(iaps) == 2
        assert iaps[0]["name"] == "Monthly Plan"
        assert iaps[0]["price"] == "$9.99"
        assert iaps[0]["price_value"] == 9.99
        assert iaps[0]["type"] == "auto_renewable_subscription"
        assert iaps[1]["name"] == "Lifetime"
        assert iaps[1]["type"] == "non_consumable"

    def test_extract_in_app_purchases_legacy_format(self, web_extractor):
        """The legacy list-with-numbers__item span structure still works."""
        from bs4 import BeautifulSoup

        html = (
            '<section class="section section--information">'
            "<dt>In-App Purchases</dt>"
            "<dd><ul>"
            '<li class="list-with-numbers__item">'
            '<span class="list-with-numbers__item__title">Pro Upgrade</span>'
            '<span class="list-with-numbers__item__price">$4.99</span>'
            "</li>"
            "</ul></dd>"
            "</section>"
        )
        soup = BeautifulSoup(html, "lxml")
        iaps = web_extractor._extract_in_app_purchases(soup)

        assert len(iaps) == 1
        assert iaps[0]["name"] == "Pro Upgrade"
        assert iaps[0]["price"] == "$4.99"

    def test_extract_in_app_purchases_absent(self, web_extractor):
        """No In-App Purchases section returns an empty list."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup("<dl><dt>Size</dt><dd>10 MB</dd></dl>", "lxml")
        assert web_extractor._extract_in_app_purchases(soup) == []

    def test_extract_privacy_policy_url_new_svelte_format(self, web_extractor):
        """Privacy Policy is read from a standalone Svelte anchor by exact text."""
        from bs4 import BeautifulSoup

        html = (
            '<a class="with-arrow svelte-abc" href="https://example.com/privacy">'
            "Privacy Policy</a>"
            '<a class="svelte-abc" href="https://example.com/other">'
            "developer’s privacy policy</a>"
        )
        soup = BeautifulSoup(html, "lxml")
        assert str(web_extractor._extract_privacy_policy_url(soup)) == (
            "https://example.com/privacy"
        )

    def test_extract_developer_website_url_new_svelte_format(self, web_extractor):
        """Developer Website is read from a standalone Svelte anchor by exact text."""
        from bs4 import BeautifulSoup

        html = (
            '<a class="with-arrow svelte-abc" href="https://example.com/">'
            "Developer Website</a>"
        )
        soup = BeautifulSoup(html, "lxml")
        assert str(web_extractor._extract_developer_website_url(soup)) == (
            "https://example.com/"
        )

    def test_extract_info_urls_absent(self, web_extractor):
        """Missing info links return None."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup("<div>nothing here</div>", "lxml")
        assert web_extractor._extract_privacy_policy_url(soup) is None
        assert web_extractor._extract_developer_website_url(soup) is None
        assert web_extractor._extract_app_support_url(soup) is None


class TestCombinedExtractor:
    """Test CombinedExtractor class - only working tests."""

    @pytest.fixture
    def wbs_config(self):
        """Create a WBS config for testing."""
        return WBSConfig()

    @pytest.fixture
    def combined_extractor(self, wbs_config):
        """Create a CombinedExtractor instance."""
        return CombinedExtractor(wbs_config)

    @pytest.mark.asyncio
    async def test_extract_complete_mode_both_success(self, combined_extractor):
        """Test complete mode with both sources successful."""
        # Mock iTunes result
        itunes_result = ExtractionResult(
            app_id="123456789",
            success=True,
            metadata=AppMetadata(
                app_id="123456789",
                url="https://apps.apple.com/app/id123456789",
                name="iTunes App",
                developer_name="Developer",
                category="Games",
                current_version="1.0.0",
                price=0.0,
                icon_url="https://example.com/icon.png",
                data_source=DataSource.ITUNES_API,
                extracted_at=datetime.now(UTC),
            ),
            data_source=DataSource.ITUNES_API,
        )

        # Mock web result with extended data
        from appstore_metadata_extractor.core.models import ExtendedAppMetadata

        web_result = ExtractionResult(
            app_id="123456789",
            success=True,
            metadata=ExtendedAppMetadata(
                app_id="123456789",
                url="https://apps.apple.com/app/id123456789",
                name="Web App",
                developer_name="Developer",
                category="Games",
                current_version="1.0.0",
                price=0.0,
                subtitle="Great game",
                whats_new="Bug fixes",
                icon_url="https://example.com/icon.png",
                data_source=DataSource.WEB_SCRAPE,
                extracted_at=datetime.now(UTC),
            ),
            data_source=DataSource.WEB_SCRAPE,
        )

        # Set mode to COMPLETE
        combined_extractor.default_mode = ExtractionMode.COMPLETE

        with patch.object(
            combined_extractor.itunes_extractor, "extract", return_value=itunes_result
        ):
            with patch.object(
                combined_extractor.web_extractor, "extract", return_value=web_result
            ):
                result = await combined_extractor.extract(
                    "https://apps.apple.com/app/id123456789"
                )

                assert result.success is True
                assert result.metadata.name == "iTunes App"  # iTunes takes precedence
                assert result.metadata.subtitle == "Great game"  # From web
                assert result.metadata.whats_new == "Bug fixes"  # From web
                assert result.data_source == DataSource.COMBINED
