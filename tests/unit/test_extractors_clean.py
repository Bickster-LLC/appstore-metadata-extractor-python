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

    @staticmethod
    def _minimal_itunes_record() -> dict:
        """Return a minimal valid iTunes Lookup response record.

        Includes only the fields _parse_itunes_data treated as required prior
        to v0.3.0; the new mappings layer on top.
        """
        return {
            "trackId": 1,
            "trackName": "Test App",
            "artistName": "Test Dev",
            "artistId": 2,
            "primaryGenreName": "Games",
            "primaryGenreId": 6014,
            "currentVersionReleaseDate": "2026-01-01T00:00:00Z",
            "version": "1.0.0",
            "artworkUrl512": "https://example.com/icon-512.png",
        }

    def test_parse_itunes_data_maps_new_fields(self, itunes_extractor):
        """The new high-value iTunes fields are mapped into ExtendedAppMetadata.

        Apple's lookup response carries genres, genreIds, features,
        supportedDevices, languageCodesISO2A, isGameCenterEnabled,
        isVppDeviceBasedLicensingEnabled, advisories, artworkUrl60/100,
        and sellerUrl — none of which were consumed before. genreIds is a
        ``list[str]`` even though primaryGenreId is an ``int``, so values must
        be coerced when populating ``category_ids: List[int]``.
        """
        record = self._minimal_itunes_record() | {
            "genres": ["Games", "Strategy"],
            "genreIds": ["6014", "7015"],
            "features": ["iosUniversal"],
            "supportedDevices": ["iPhone10-iPhone10", "iPadAir-iPadAir"],
            "languageCodesISO2A": ["EN", "ES", "FR"],
            "isGameCenterEnabled": True,
            "isVppDeviceBasedLicensingEnabled": True,
            "advisories": ["Mild Violence", "Infrequent/Mild Mature Themes"],
            "artworkUrl60": "https://example.com/icon-60.png",
            "artworkUrl100": "https://example.com/icon-100.png",
            "sellerUrl": "https://example.com/",
        }
        m = itunes_extractor._parse_itunes_data(
            record, "https://apps.apple.com/us/app/test/id1"
        )

        assert m.categories == ["Games", "Strategy"]
        assert m.category_ids == [6014, 7015]
        assert m.features == ["iosUniversal"]
        assert m.supported_devices == ["iPhone10-iPhone10", "iPadAir-iPadAir"]
        assert m.language_codes == ["EN", "ES", "FR"]
        assert m.is_game_center_enabled is True
        assert m.is_vpp_device_based_licensing_enabled is True
        assert m.content_advisories == [
            "Mild Violence",
            "Infrequent/Mild Mature Themes",
        ]
        assert str(m.icon_urls["60"]) == "https://example.com/icon-60.png"
        assert str(m.icon_urls["100"]) == "https://example.com/icon-100.png"
        assert str(m.icon_urls["512"]) == "https://example.com/icon-512.png"
        assert str(m.developer_website_url) == "https://example.com/"

    def test_parse_itunes_data_defaults_when_new_fields_missing(self, itunes_extractor):
        """Records missing the new keys still parse, with safe defaults.

        Older cached responses and apps that omit certain optional fields
        (e.g. sellerUrl, advisories) must not break extraction.
        """
        m = itunes_extractor._parse_itunes_data(
            self._minimal_itunes_record(),
            "https://apps.apple.com/us/app/test/id1",
        )
        assert m.categories == []
        assert m.category_ids == []
        assert m.features == []
        assert m.supported_devices == []
        assert m.language_codes == []
        assert m.is_game_center_enabled is False
        assert m.is_vpp_device_based_licensing_enabled is False
        assert m.content_advisories == []
        # icon_urls always carries the 512 entry because artworkUrl512 is in the
        # minimal record; the 60/100 keys are absent here.
        assert "512" in m.icon_urls
        assert "60" not in m.icon_urls
        assert m.developer_website_url is None

    def test_parse_itunes_data_skips_non_numeric_genre_ids(self, itunes_extractor):
        """Non-numeric entries in genreIds are skipped, not coerced to error.

        Apple has historically returned a mix of numeric strings; defensive
        parsing avoids a ValueError on a stray non-numeric value.
        """
        record = self._minimal_itunes_record() | {
            "genreIds": ["6014", "not-a-number", "7015"],
        }
        m = itunes_extractor._parse_itunes_data(
            record, "https://apps.apple.com/us/app/test/id1"
        )
        assert m.category_ids == [6014, 7015]


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

    # --- Svelte screenshot extraction --------------------------------------

    @staticmethod
    def _svelte_picture(
        orient: str, w: int, h: int, base_path: str = "/image/x.png"
    ) -> str:
        """Build a Svelte-style <picture> with an srcset URL of the given size.

        The Apple Svelte page wraps screenshots/icons in
        ``<div class="artwork-component artwork-component--orientation-XXX">``
        and emits one or more ``<source srcset="…WxHbb.webp …">`` entries.
        """
        url = f"https://is1-ssl.mzstatic.com{base_path}/{w}x{h}bb.webp"
        return (
            f'<div class="artwork-component artwork-component--aspect-ratio '
            f'artwork-component--orientation-{orient} svelte-1fla0gl">'
            f'<picture class="svelte-1fla0gl">'
            f'<source type="image/webp" srcset="{url}"></source>'
            f"</picture></div>"
        )

    def test_extract_screenshots_svelte_iphone(self, web_extractor):
        """iPhone portrait screenshots are read from Svelte <source srcset>.

        Apple migrated the product page to a Svelte frontend; the screenshots
        live in <picture><source srcset="…600x1300bb.webp"> inside an ancestor
        ``div.artwork-component--orientation-portrait``. The svelte-XXXXX
        class hashes are volatile, so the stable ``orientation-portrait`` token
        and the resolution pattern in the URL are matched instead.
        """
        from bs4 import BeautifulSoup

        html = (
            self._svelte_picture("portrait", 600, 1300, "/image/a.png/")
            + self._svelte_picture("portrait", 600, 1300, "/image/b.png/")
            # Icon (square) — must be filtered out
            + self._svelte_picture("square", 96, 96, "/image/icon.png/")
        )
        soup = BeautifulSoup(html, "lxml")
        shots = web_extractor._extract_screenshots(soup)
        assert len(shots) == 2
        for url in shots:
            assert "mzstatic.com" in str(url)
            assert "600x1300" in str(url)

    def test_extract_ipad_screenshots_svelte_portrait_and_landscape(
        self, web_extractor
    ):
        """iPad screenshots are matched at both portrait (~3:4) and landscape (~4:3) aspect."""
        from bs4 import BeautifulSoup

        html = (
            # iPad portrait 3:4
            self._svelte_picture("portrait", 1286, 1714, "/image/p1.png/")
            + self._svelte_picture("portrait", 1286, 1714, "/image/p2.png/")
            # iPad landscape 4:3
            + self._svelte_picture("landscape", 1286, 964, "/image/l1.png/")
            # iPhone-aspect picture should NOT be classified as iPad
            + self._svelte_picture("portrait", 600, 1300, "/image/iphone.png/")
            # Icon — filtered out
            + self._svelte_picture("square", 96, 96, "/image/icon.png/")
        )
        soup = BeautifulSoup(html, "lxml")
        shots = web_extractor._extract_ipad_screenshots(soup)
        assert len(shots) == 3
        urls = [str(u) for u in shots]
        assert any("1286x1714" in u for u in urls)
        assert any("1286x964" in u for u in urls)
        # The iPhone-aspect one must be excluded from iPad results
        assert not any("600x1300" in u for u in urls)

    def test_extract_screenshots_svelte_dedup_keeps_highest_resolution(
        self, web_extractor
    ):
        """When a <source srcset> lists multiple sizes for one image, return the largest."""
        from bs4 import BeautifulSoup

        # One picture with both 1x and 2x variants in the srcset; same base path.
        base = "/image/x.png/"
        html = (
            '<div class="artwork-component artwork-component--orientation-portrait">'
            "<picture>"
            f'<source type="image/webp" srcset='
            f'"https://is1-ssl.mzstatic.com{base}600x1300bb.webp 1x, '
            f'https://is1-ssl.mzstatic.com{base}1200x2600bb.webp 2x">'
            "</source></picture></div>"
        )
        soup = BeautifulSoup(html, "lxml")
        shots = web_extractor._extract_screenshots(soup)
        assert len(shots) == 1
        assert "1200x2600" in str(shots[0])

    def test_extract_screenshots_svelte_empty_when_only_icons(self, web_extractor):
        """A page with only square (icon) artworks yields zero screenshots."""
        from bs4 import BeautifulSoup

        html = self._svelte_picture(
            "square", 96, 96, "/image/a.png/"
        ) + self._svelte_picture("square", 512, 512, "/image/b.png/")
        soup = BeautifulSoup(html, "lxml")
        assert web_extractor._extract_screenshots(soup) == []
        assert web_extractor._extract_ipad_screenshots(soup) == []

    def test_extract_screenshots_legacy_section_still_works(self, web_extractor):
        """The legacy ``section--screenshots`` markup is still supported."""
        from bs4 import BeautifulSoup

        html = (
            '<section class="section--screenshots">'
            '<img src="https://example.com/shot1.png">'
            '<img src="https://example.com/shot2.png">'
            "</section>"
        )
        soup = BeautifulSoup(html, "lxml")
        shots = web_extractor._extract_screenshots(soup)
        assert len(shots) == 2

    def test_extract_screenshots_absent(self, web_extractor):
        """Pages with no screenshot pictures return an empty list."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup("<div>nothing here</div>", "lxml")
        assert web_extractor._extract_screenshots(soup) == []
        assert web_extractor._extract_ipad_screenshots(soup) == []


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
