"""Core extractors for AppStore metadata."""

import asyncio
import json
import re
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

import aiohttp
from bs4 import BeautifulSoup, Tag
from pydantic import HttpUrl
from tenacity import retry, stop_after_attempt, wait_exponential

from .cache import get_cache_manager, get_rate_limiter
from .exceptions import ExtractionError, NetworkError, ValidationError
from .models import (
    AppMetadata,
    DataSource,
    ExtendedAppMetadata,
    ExtractionMode,
    ExtractionResult,
    WBSConfig,
)
from .wbs_validator import WBSValidator


class BaseExtractor(ABC):
    """Base class for all metadata extractors."""

    def __init__(self, wbs_config: WBSConfig, timeout: int = 30):
        """
        Initialize extractor with WBS configuration.

        Args:
            wbs_config: WBS framework configuration
            timeout: Request timeout in seconds
        """
        self.wbs_config = wbs_config
        self.timeout = timeout
        self.validator = WBSValidator(wbs_config)
        self.cache = get_cache_manager()
        self.rate_limiter = get_rate_limiter()

        # Common headers for web requests
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    @abstractmethod
    async def extract(self, url: str) -> ExtractionResult:
        """
        Extract metadata from App Store URL.

        Args:
            url: App Store URL

        Returns:
            ExtractionResult with metadata and WBS compliance status
        """

    async def extract_with_validation(self, url: str) -> ExtractionResult:
        """
        Extract metadata and validate against WBS constraints.

        Args:
            url: App Store URL

        Returns:
            WBS-validated extraction result

        Raises:
            WBSViolationError: If extraction violates WBS constraints
        """
        start_time = datetime.now(UTC)

        try:
            # Enforce pre-extraction boundaries
            self.validator.enforce_boundaries()

            # Perform extraction
            result = await self.extract(url)

            # Calculate duration
            duration = (datetime.now(UTC) - start_time).total_seconds()
            result.extraction_duration_seconds = duration

            # Validate result
            self.validator.validate(result)

            return result

        except Exception as e:
            # Create error result
            duration = (datetime.now(UTC) - start_time).total_seconds()
            result = ExtractionResult(
                app_id=self._extract_app_id(url) or "unknown",
                success=False,
                extraction_duration_seconds=duration,
            )
            result.add_error(str(e))

            # Validate even failed results
            self.validator.validate(result)

            return result

    def _extract_app_id(self, url: str) -> Optional[str]:
        """Extract app ID from App Store URL."""
        match = re.search(r"/id(\d+)", str(url))
        return match.group(1) if match else None

    async def _create_session(self) -> aiohttp.ClientSession:
        """Create aiohttp session with timeout."""
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        return aiohttp.ClientSession(timeout=timeout)


class ITunesAPIExtractor(BaseExtractor):
    """Extractor using iTunes Lookup API."""

    def __init__(self, wbs_config: WBSConfig, timeout: int = 30):
        super().__init__(wbs_config, timeout)
        self.base_url = "https://itunes.apple.com/lookup"

        # Configure rate limiter for iTunes API
        self.rate_limiter.configure(
            "itunes_api",
            max_requests=self.wbs_config.boundaries.itunes_api_rate_limit,
            time_window=60,
        )

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def extract(self, url: str) -> ExtractionResult:
        """Extract metadata using iTunes API."""
        app_id = self._extract_app_id(url)
        if not app_id:
            raise ValidationError("url", url, "valid App Store URL with app ID")

        # Check cache first
        cache_key = f"itunes:{app_id}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            result = ExtractionResult(
                app_id=app_id,
                metadata=AppMetadata(**cached_data),
                success=True,
                from_cache=True,
                cache_age_seconds=self.cache.get_age(cache_key),
                data_source=DataSource.ITUNES_API,
            )
            return result

        # Check rate limit
        self.rate_limiter.consume("itunes_api")

        async with await self._create_session() as session:
            params = {"id": app_id, "country": "us", "entity": "software"}

            try:
                async with session.get(self.base_url, params=params) as response:
                    response.raise_for_status()
                    text = await response.text()
                    data = json.loads(text)

                    if data["resultCount"] == 0:
                        raise ExtractionError(f"No app found with ID: {app_id}", url)

                    app_data = data["results"][0]
                    metadata = self._parse_itunes_data(app_data, url)

                    # Cache successful result
                    self.cache.set(
                        cache_key,
                        metadata.model_dump(),
                        ttl=self.wbs_config.boundaries.max_cache_age_seconds,
                    )

                    result = ExtractionResult(
                        app_id=app_id,
                        metadata=metadata,
                        success=True,
                        data_source=DataSource.ITUNES_API,
                        extraction_method=ExtractionMode.FAST,
                    )

                    # Track present fields
                    present_fields = self.validator._get_present_fields(metadata)
                    result.required_fields_present = (
                        present_fields & self.wbs_config.boundaries.required_fields
                    )
                    result.optional_fields_present = (
                        present_fields & self.wbs_config.boundaries.optional_fields
                    )

                    return result

            except aiohttp.ClientError as e:
                raise NetworkError(
                    f"iTunes API request failed: {e}", getattr(e, "status", None)
                )

    def _parse_itunes_data(self, data: Dict[str, Any], url: str) -> AppMetadata:
        """Parse iTunes API response into AppMetadata."""
        return AppMetadata(
            app_id=str(data.get("trackId", "")),
            bundle_id=data.get("bundleId"),
            url=HttpUrl(url),
            name=data.get("trackName", ""),
            subtitle=None,  # Not available in iTunes API
            developer_name=data.get("artistName", ""),
            developer_id=str(data.get("artistId", "")),
            category=data.get("primaryGenreName", ""),
            category_id=data.get("primaryGenreId"),
            price=data.get("price", 0.0),
            formatted_price=data.get("formattedPrice", "Free"),
            currency=data.get("currency", "USD"),
            in_app_purchases=False,  # Not directly available
            in_app_purchase_list=[],  # Not available from iTunes API
            current_version=data.get("version", ""),
            version_date=self._parse_date(data.get("currentVersionReleaseDate")),
            whats_new=data.get("releaseNotes"),
            description=data.get("description"),
            file_size_bytes=data.get("fileSizeBytes"),
            minimum_os_version=data.get("minimumOsVersion"),
            content_rating=data.get("contentAdvisoryRating", "4+"),
            average_rating=data.get("averageUserRating"),
            rating_count=data.get("userRatingCount"),
            icon_url=HttpUrl(data.get("artworkUrl512", data.get("artworkUrl100", ""))),
            screenshots=data.get("screenshotUrls", []),
            app_support_url=None,  # Not available from iTunes API
            privacy_policy_url=None,  # Not available from iTunes API
            developer_website_url=None,  # Not available from iTunes API
            data_source=DataSource.ITUNES_API,
            extracted_at=datetime.now(UTC),
        )

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO date string."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return None


class WebScraperExtractor(BaseExtractor):
    """Extractor using web scraping."""

    def __init__(self, wbs_config: WBSConfig, timeout: int = 30):
        super().__init__(wbs_config, timeout)

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def extract(self, url: str) -> ExtractionResult:
        """Extract metadata using web scraping."""
        app_id = self._extract_app_id(url)
        if not app_id:
            raise ValidationError("url", url, "valid App Store URL with app ID")

        # Add delay for web scraping
        await asyncio.sleep(self.wbs_config.boundaries.web_scrape_delay)

        async with await self._create_session() as session:
            try:
                async with session.get(url, headers=self.headers) as response:
                    response.raise_for_status()
                    html = await response.text()

                    metadata = self._parse_html(html, url)

                    result = ExtractionResult(
                        app_id=app_id,
                        metadata=metadata,
                        success=True,
                        data_source=DataSource.WEB_SCRAPE,
                        extraction_method=ExtractionMode.COMPLETE,
                    )

                    # Track present fields
                    present_fields = self.validator._get_present_fields(metadata)
                    result.required_fields_present = (
                        present_fields & self.wbs_config.boundaries.required_fields
                    )
                    result.optional_fields_present = (
                        present_fields & self.wbs_config.boundaries.optional_fields
                    )

                    return result

            except aiohttp.ClientError as e:
                raise NetworkError(
                    f"Web scraping request failed: {e}", getattr(e, "status", None)
                )

    def _parse_html(self, html: str, url: str) -> ExtendedAppMetadata:
        """Parse HTML into ExtendedAppMetadata."""
        soup = BeautifulSoup(html, "lxml")

        app_id = self._extract_app_id(url)
        if not app_id:
            raise ValueError(f"Could not extract app ID from URL: {url}")

        # Extract JSON-LD data
        json_ld_data = {}
        json_ld_elem = soup.find("script", type="application/ld+json")
        if json_ld_elem and hasattr(json_ld_elem, "string") and json_ld_elem.string:
            try:
                json_ld_data = json.loads(str(json_ld_elem.string))
            except Exception:
                pass

        # Build metadata from various sources
        # Extract all data first
        extracted_data: Dict[str, Any] = {
            "app_id": app_id,
            "url": HttpUrl(url),
            "name": self._extract_title(soup, json_ld_data),
            "developer_name": self._extract_developer(soup, json_ld_data),
            "category": self._extract_category(soup, json_ld_data),
            "price": self._extract_price(soup, json_ld_data),
            "formatted_price": self._extract_formatted_price(soup),
            "currency": "USD",
            "in_app_purchases": self._has_in_app_purchases(soup),
            "in_app_purchase_list": [],  # Will be populated below
            "current_version": self._extract_version(soup),
            "description": self._extract_description(soup, json_ld_data),
            "content_rating": self._extract_age_rating(soup, json_ld_data),
            "icon_url": self._extract_icon_url(soup, json_ld_data),
            "screenshots": self._extract_screenshots(soup),
            "app_support_url": self._extract_app_support_url(soup),
            "privacy_policy_url": self._extract_privacy_policy_url(soup),
            "developer_website_url": self._extract_developer_website_url(soup),
            "data_source": DataSource.WEB_SCRAPE,
        }

        # Add optional fields if they exist
        subtitle = self._extract_subtitle(soup)
        if subtitle:
            extracted_data["subtitle"] = subtitle

        whats_new = self._extract_whats_new(soup)
        if whats_new:
            extracted_data["whats_new"] = whats_new

        rating = self._extract_rating(soup, json_ld_data)
        if rating is not None:
            extracted_data["average_rating"] = rating

        rating_count = self._extract_rating_count(soup)
        if rating_count is not None:
            extracted_data["rating_count"] = rating_count

        languages = self._extract_languages(soup)
        if languages:
            extracted_data["languages"] = languages

        # Extract detailed IAP information if app has IAPs
        if extracted_data["in_app_purchases"]:
            iap_data = self._extract_in_app_purchases(soup)
            if iap_data:
                # Convert to InAppPurchase objects
                from .models import InAppPurchase, InAppPurchaseType

                iap_list = []
                for iap in iap_data:
                    iap_obj = InAppPurchase(
                        name=iap["name"],
                        price=iap["price"],
                        price_value=iap.get("price_value"),
                        currency=iap.get("currency"),
                        type=InAppPurchaseType(iap.get("type", "unknown")),
                        description=None,
                    )
                    iap_list.append(iap_obj)
                extracted_data["in_app_purchase_list"] = iap_list

        metadata = ExtendedAppMetadata(**extracted_data)

        return metadata

    def _extract_title(self, soup: BeautifulSoup, json_ld: Dict[str, Any]) -> str:
        """Extract app title."""
        if json_ld and "name" in json_ld:
            return str(json_ld["name"])

        title_elem = soup.find("h1", class_="product-header__title")
        if title_elem and title_elem.text:
            return str(title_elem.text).strip()

        return "Unknown"

    def _extract_subtitle(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract app subtitle."""
        subtitle_elem = soup.find("h2", class_="product-header__subtitle")
        if subtitle_elem and subtitle_elem.text:
            return str(subtitle_elem.text).strip()
        return None

    def _extract_developer(self, soup: BeautifulSoup, json_ld: Dict[str, Any]) -> str:
        """Extract developer name."""
        if json_ld and "author" in json_ld and "name" in json_ld["author"]:
            return str(json_ld["author"]["name"])

        dev_elem = soup.find("a", class_="link", href=re.compile(r"/developer/"))
        if dev_elem and dev_elem.text:
            return str(dev_elem.text).strip()

        return "Unknown"

    def _extract_category(self, soup: BeautifulSoup, json_ld: Dict[str, Any]) -> str:
        """Extract app category."""
        if json_ld and "applicationCategory" in json_ld:
            return str(json_ld["applicationCategory"])

        cat_elem = soup.find("a", class_="link", href=re.compile(r"/genre/"))
        if cat_elem and cat_elem.text:
            return str(cat_elem.text).strip()

        return "Unknown"

    def _extract_price(self, soup: BeautifulSoup, json_ld: Dict) -> float:
        """Extract app price."""
        if json_ld and "offers" in json_ld and "price" in json_ld["offers"]:
            try:
                return float(json_ld["offers"]["price"])
            except Exception:
                pass

        return 0.0

    def _extract_formatted_price(self, soup: BeautifulSoup) -> str:
        """Extract formatted price string."""
        price_elem = soup.find("li", class_="inline-list__item--price")
        if price_elem and price_elem.text:
            return str(price_elem.text).strip()
        return "Free"

    def _has_in_app_purchases(self, soup: BeautifulSoup) -> bool:
        """Check if app has in-app purchases."""
        # Look for the Information section
        info_section = soup.find("section", class_="section section--information")
        if not info_section:
            # Try alternative selector
            info_section = soup.find("section", {"class": re.compile("information")})

        if info_section and isinstance(info_section, Tag):
            # Look for dt element with "In-App Purchases" text
            iap_dt = info_section.find("dt", string=re.compile(r"In-App Purchases"))
            if iap_dt:
                return True

        # Fallback: search entire page
        iap_elem = soup.find(string=re.compile(r"In-App Purchases"))
        return bool(iap_elem)

    def _extract_in_app_purchases(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract detailed in-app purchase information."""
        iap_list = []

        # Look for the Information section
        info_section = soup.find("section", class_="section section--information")
        if not info_section:
            info_section = soup.find("section", {"class": re.compile("information")})

        if info_section and isinstance(info_section, Tag):
            # Find the dt element with "In-App Purchases"
            iap_dt = info_section.find("dt", string=re.compile(r"In-App Purchases"))
            if iap_dt and isinstance(iap_dt, Tag):
                # Find the corresponding dd element
                iap_dd = iap_dt.find_next_sibling("dd")
                if iap_dd and isinstance(iap_dd, Tag):
                    # Look for list items within the dd
                    items = iap_dd.find_all("li")
                    for item in items:
                        text = item.get_text(strip=True)
                        # The text might be concatenated like "Headspace$12.99"
                        # Look for price pattern at the end
                        price_match = re.search(r"(\$[\d.,]+)$", text)
                        if price_match:
                            price_str = price_match.group(1)
                            name = text[: price_match.start()].strip()

                            # Extract numeric price
                            price_value = None
                            try:
                                price_value = float(re.sub(r"[^\d.]", "", price_str))
                            except Exception:
                                pass

                            # Determine IAP type based on name
                            iap_type = "unknown"
                            name_lower = name.lower()
                            if any(
                                word in name_lower
                                for word in [
                                    "monthly",
                                    "month",
                                    "annual",
                                    "year",
                                    "weekly",
                                    "week",
                                    "subscription",
                                ]
                            ):
                                iap_type = "auto_renewable_subscription"
                            elif "lifetime" in name_lower:
                                iap_type = "non_consumable"

                            iap_list.append(
                                {
                                    "name": name,
                                    "price": price_str,
                                    "price_value": price_value,
                                    "currency": "USD",
                                    "type": iap_type,
                                }
                            )

        return iap_list

    def _extract_version(self, soup: BeautifulSoup) -> str:
        """Extract current version."""
        version_elem = soup.find("p", class_="whats-new__latest__version")
        if version_elem and version_elem.text:
            match = re.search(r"Version\s+([\d.]+)", version_elem.text)
            if match:
                return match.group(1)

        # Search entire page for version pattern
        version_texts = soup.find_all(string=re.compile(r"Version\s+[\d.]+"))
        for text in version_texts:
            # NavigableString objects have parent attribute
            if (
                hasattr(text, "parent")
                and text.parent
                and text.parent.name not in ["script", "style"]
            ):
                match = re.search(r"Version\s+([\d.]+)", str(text))
                if match:
                    return match.group(1)

        return "Unknown"

    def _extract_whats_new(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract what's new section."""
        whats_new_section = soup.find("section", class_="section--whats-new")
        if isinstance(whats_new_section, Tag):
            content = whats_new_section.find("div", class_="section__description")
            if content and hasattr(content, "text"):
                return str(content.text).strip()
        return None

    def _extract_description(
        self, soup: BeautifulSoup, json_ld: Dict[str, Any]
    ) -> Optional[str]:
        """Extract app description."""
        if json_ld and "description" in json_ld:
            return str(json_ld["description"])

        desc_section = soup.find("section", class_="section--description")
        if isinstance(desc_section, Tag):
            content = desc_section.find("div", class_="section__description")
            if content and hasattr(content, "text"):
                return str(content.text).strip()
        return None

    def _extract_age_rating(self, soup: BeautifulSoup, json_ld: Dict[str, Any]) -> str:
        """Extract age rating."""
        if json_ld and "contentRating" in json_ld:
            return str(json_ld["contentRating"])

        age_elem = soup.find("span", class_="badge--age-rating")
        if age_elem and age_elem.text:
            return str(age_elem.text).strip()
        return "4+"

    def _extract_rating(self, soup: BeautifulSoup, json_ld: Dict) -> Optional[float]:
        """Extract average rating."""
        if json_ld and "aggregateRating" in json_ld:
            try:
                return float(json_ld["aggregateRating"].get("ratingValue", 0))
            except Exception:
                pass

        rating_elem = soup.find("figcaption", class_="we-rating-count")
        if rating_elem:
            try:
                return float(rating_elem.text.split()[0])
            except Exception:
                pass
        return None

    def _extract_rating_count(self, soup: BeautifulSoup) -> Optional[int]:
        """Extract rating count."""
        rating_elem = soup.find("figcaption", class_="we-rating-count")
        if rating_elem:
            match = re.search(r"([\d,]+)\s+Ratings?", rating_elem.text)
            if match:
                try:
                    return int(match.group(1).replace(",", ""))
                except Exception:
                    pass
        return None

    def _extract_icon_url(
        self, soup: BeautifulSoup, json_ld: Dict[str, Any]
    ) -> HttpUrl:
        """Extract app icon URL."""
        if json_ld and "image" in json_ld:
            return HttpUrl(json_ld["image"])

        icon_elem = soup.find("picture", class_="product-hero__media")
        if isinstance(icon_elem, Tag):
            img = icon_elem.find("img")
            if img and hasattr(img, "get"):
                src = img.get("src")
                if src:
                    return HttpUrl(str(src))

        return HttpUrl("https://via.placeholder.com/512")

    def _extract_screenshots(self, soup: BeautifulSoup) -> List[HttpUrl]:
        """Extract screenshot URLs."""
        screenshots: List[HttpUrl] = []
        gallery = soup.find("section", class_="section--screenshots")
        if isinstance(gallery, Tag):
            images = gallery.find_all("img")
            for img in images:
                if hasattr(img, "get"):
                    src = img.get("src")
                    if src:
                        screenshots.append(HttpUrl(str(src)))
        return screenshots

    def _extract_languages(self, soup: BeautifulSoup) -> List[str]:
        """Extract supported languages."""
        languages: List[str] = []
        lang_section = soup.find("section", class_="section--languages")
        if isinstance(lang_section, Tag):
            lang_items = lang_section.find_all("li")
            for item in lang_items:
                if hasattr(item, "text"):
                    languages.append(item.text.strip())
        return languages

    def _extract_app_support_url(self, soup: BeautifulSoup) -> Optional[HttpUrl]:
        """Extract app support URL."""
        # Look for the Information section
        info_section = soup.find("section", class_="section section--information")
        if not info_section:
            info_section = soup.find("section", {"class": re.compile("information")})

        if info_section and isinstance(info_section, Tag):
            # Look for links in the section
            links = info_section.find_all("a")
            for link in links:
                if (
                    isinstance(link, Tag)
                    and link.get("href")
                    and "App Support" in link.get_text()
                ):
                    href = link.get("href")
                    if href:
                        return HttpUrl(str(href))

        # Alternative: Look for footer links
        footer_links = soup.find_all("a", {"class": re.compile("link.*footer")})
        for link in footer_links:
            if (
                isinstance(link, Tag)
                and link.get("href")
                and "support" in link.get_text().lower()
            ):
                href = link.get("href")
                if href:
                    return HttpUrl(str(href))

        return None

    def _extract_privacy_policy_url(self, soup: BeautifulSoup) -> Optional[HttpUrl]:
        """Extract privacy policy URL."""
        # Look for the Information section
        info_section = soup.find("section", class_="section section--information")
        if not info_section:
            info_section = soup.find("section", {"class": re.compile("information")})

        if info_section and isinstance(info_section, Tag):
            # Look for links in the section
            links = info_section.find_all("a")
            for link in links:
                if (
                    isinstance(link, Tag)
                    and link.get("href")
                    and "Privacy Policy" in link.get_text()
                ):
                    href = link.get("href")
                    if href:
                        return HttpUrl(str(href))

        # Alternative: Look for footer links
        footer_links = soup.find_all("a", {"class": re.compile("link.*footer")})
        for link in footer_links:
            if (
                isinstance(link, Tag)
                and link.get("href")
                and "privacy" in link.get_text().lower()
            ):
                href = link.get("href")
                if href:
                    return HttpUrl(str(href))

        return None

    def _extract_developer_website_url(self, soup: BeautifulSoup) -> Optional[HttpUrl]:
        """Extract developer website URL."""
        # Look for the Information section
        info_section = soup.find("section", class_="section section--information")
        if not info_section:
            info_section = soup.find("section", {"class": re.compile("information")})

        if info_section and isinstance(info_section, Tag):
            # Look for links in the section
            links = info_section.find_all("a")
            for link in links:
                if (
                    isinstance(link, Tag)
                    and link.get("href")
                    and "Developer Website" in link.get_text()
                ):
                    href = link.get("href")
                    if href:
                        return HttpUrl(str(href))

        return None


class CombinedExtractor(BaseExtractor):
    """Extractor combining iTunes API and web scraping for comprehensive data."""

    def __init__(self, wbs_config: WBSConfig, timeout: int = 30):
        super().__init__(wbs_config, timeout)
        self.itunes_extractor = ITunesAPIExtractor(wbs_config, timeout)
        self.web_extractor = WebScraperExtractor(wbs_config, timeout)

    async def extract(self, url: str) -> ExtractionResult:
        """Extract metadata using both sources and merge results."""
        app_id = self._extract_app_id(url)
        if not app_id:
            raise ValidationError("url", url, "valid App Store URL with app ID")

        # Try iTunes API first (faster and more reliable)
        try:
            itunes_result = await self.itunes_extractor.extract(url)

            # If we got all required fields from iTunes, we might be done
            if self._has_all_required_fields(itunes_result):
                itunes_result.extraction_method = ExtractionMode.SMART
                return itunes_result

        except Exception:
            itunes_result = None

        # Try web scraping for additional data
        try:
            web_result = await self.web_extractor.extract(url)
        except Exception:
            web_result = None

        # Merge results
        if (
            itunes_result
            and itunes_result.success
            and web_result
            and web_result.success
        ):
            merged_metadata = self._merge_metadata(
                itunes_result.metadata, web_result.metadata
            )

            result = ExtractionResult(
                app_id=app_id,
                metadata=merged_metadata,
                success=True,
                data_source=DataSource.COMBINED,
                extraction_method=ExtractionMode.COMPLETE,
                extraction_duration_seconds=(
                    itunes_result.extraction_duration_seconds
                    + web_result.extraction_duration_seconds
                ),
            )

            # Track present fields
            present_fields = self.validator._get_present_fields(merged_metadata)
            result.required_fields_present = (
                present_fields & self.wbs_config.boundaries.required_fields
            )
            result.optional_fields_present = (
                present_fields & self.wbs_config.boundaries.optional_fields
            )

            return result

        elif itunes_result and itunes_result.success:
            return itunes_result
        elif web_result and web_result.success:
            return web_result
        else:
            # Both failed
            result = ExtractionResult(
                app_id=app_id,
                success=False,
                data_source=DataSource.COMBINED,
                extraction_method=ExtractionMode.COMPLETE,
            )

            if itunes_result:
                result.errors.extend(itunes_result.errors)
            if web_result:
                result.errors.extend(web_result.errors)

            return result

    def _has_all_required_fields(self, result: ExtractionResult) -> bool:
        """Check if result has all required fields."""
        return len(result.required_fields_present) == len(
            self.wbs_config.boundaries.required_fields
        )

    def _merge_metadata(
        self, itunes_data: Optional[AppMetadata], web_data: Optional[AppMetadata]
    ) -> AppMetadata:
        """Merge metadata from both sources, preferring iTunes for most fields."""
        if not itunes_data and web_data:
            return web_data
        if not web_data and itunes_data:
            return itunes_data
        if not itunes_data and not web_data:
            raise ValueError("Both iTunes and web data are None")

        # Start with iTunes data and fill in missing fields from web
        # At this point, both itunes_data and web_data must be non-None
        assert itunes_data is not None and web_data is not None
        merged = itunes_data.model_copy()

        # Fields that are better from web scraping
        if web_data.subtitle:
            merged.subtitle = web_data.subtitle
        if web_data.in_app_purchases:
            merged.in_app_purchases = web_data.in_app_purchases
        if web_data.whats_new and not merged.whats_new:
            merged.whats_new = web_data.whats_new

        # Use web screenshots if more available
        if len(web_data.screenshots) > len(merged.screenshots):
            merged.screenshots = web_data.screenshots

        # Mark as combined source
        merged.data_source = DataSource.COMBINED

        return merged
