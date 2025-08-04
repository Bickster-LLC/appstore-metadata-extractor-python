import asyncio
import json
import re
from datetime import UTC, datetime
from typing import Dict, Optional

import aiohttp
from bs4 import BeautifulSoup
from pydantic import HttpUrl
from tenacity import retry, stop_after_attempt, wait_exponential

from .models_combined import (
    AppMetadataCombined,
    AppPrivacy,
    CombinedScrapeResult,
    DataSource,
    PrivacyDetail,
    RatingDistribution,
    RelatedApp,
)


class CombinedAppStoreScraper:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.itunes_base_url = "https://itunes.apple.com/lookup"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    def _extract_app_id(self, url: str) -> Optional[str]:
        """Extract app ID from App Store URL"""
        match = re.search(r"/id(\d+)", str(url))
        return match.group(1) if match else None

    def _extract_country_code(self, url: str) -> str:
        """Extract country code from URL, default to 'us'"""
        match = re.search(r"apps\.apple\.com/([a-z]{2})/", str(url))
        return match.group(1) if match else "us"

    def _format_file_size(self, size_bytes: int) -> str:
        """Convert bytes to human-readable format"""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def _fetch_itunes_data(
        self, session: aiohttp.ClientSession, app_id: str, country: str = "us"
    ) -> Dict:
        """Fetch data from iTunes API"""
        params = {"id": app_id, "country": country, "entity": "software"}

        async with session.get(self.itunes_base_url, params=params) as response:
            response.raise_for_status()
            # Read as text first, then parse JSON manually to handle content-type issues
            text = await response.text()
            data = json.loads(text)

            if data.get("resultCount", 0) == 0:
                raise ValueError(f"No app found with ID {app_id}")

            return data["results"][0]

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def _fetch_web_page(self, session: aiohttp.ClientSession, url: str) -> str:
        """Fetch App Store web page"""
        async with session.get(
            url, headers=self.headers, timeout=self.timeout
        ) as response:
            response.raise_for_status()
            return await response.text()

    def _parse_web_specific_data(self, soup: BeautifulSoup) -> Dict:
        """Extract web-only data from App Store page"""
        web_data = {
            "subtitle": None,
            "in_app_purchases": False,
            "privacy": None,
            "rating_distribution": None,
            "reviews": [],
            "developer_apps": [],
            "similar_apps": [],
            "rankings": {},
        }

        # Extract subtitle
        subtitle_elem = soup.find("h2", class_="product-header__subtitle")
        if subtitle_elem:
            web_data["subtitle"] = subtitle_elem.text.strip()

        # Check for in-app purchases
        info_section = soup.find("section", class_="section--information")
        if not info_section:
            info_section = soup.find("section", {"class": re.compile("information")})

        if info_section:
            in_app_elem = info_section.find("dt", string=re.compile("In-App Purchases"))
            if in_app_elem:
                web_data["in_app_purchases"] = True

                # Extract detailed IAP information
                iap_list = []
                iap_dd = in_app_elem.find_next_sibling("dd")
                if iap_dd:
                    items = iap_dd.find_all("li")
                    for item in items:
                        text = item.get_text(strip=True)
                        # The text might be concatenated like "Headspace$12.99"
                        # Look for price pattern at the end
                        price_match = re.search(r"(\$[\d.,]+)$", text)
                        if price_match:
                            price_str = price_match.group(1)
                            name = text[: price_match.start()].strip()
                            iap_list.append({"name": name, "price": price_str})

                web_data["in_app_purchase_list"] = iap_list

        # Extract support links from Information section
        info_section = soup.find("section", class_="section section--information")
        if not info_section:
            info_section = soup.find("section", {"class": re.compile("information")})

        if info_section:
            links = info_section.find_all("a")
            for link in links:
                href = link.get("href")
                text = link.get_text()
                if href:
                    if "App Support" in text:
                        web_data["app_support_url"] = href
                    elif "Privacy Policy" in text:
                        web_data["privacy_policy_url"] = href
                    elif "Developer Website" in text:
                        web_data["developer_website_url"] = href

        # Extract privacy information
        privacy_section = soup.find("section", class_="section--app-privacy")
        if privacy_section:
            privacy = AppPrivacy()

            # Look for privacy practice sections
            for practice_div in privacy_section.find_all("div", class_="privacy-type"):
                category_name = practice_div.find("h3")
                if category_name:
                    category = category_name.text.strip()
                    data_types = []

                    for item in practice_div.find_all("li"):
                        data_types.append(item.text.strip())

                    detail = PrivacyDetail(category=category, data_types=data_types)

                    # Categorize based on section headers
                    if "track" in category.lower():
                        privacy.data_used_to_track.append(detail)
                    elif "linked" in category.lower() and "not" not in category.lower():
                        privacy.data_linked_to_you.append(detail)
                    else:
                        privacy.data_not_linked_to_you.append(detail)

            web_data["privacy"] = privacy

        # Extract rating distribution
        ratings_section = soup.find("section", class_="section--ratings-and-reviews")
        if ratings_section:
            distribution = RatingDistribution()

            # Look for rating bars
            rating_bars = ratings_section.find_all("div", class_="we-rating-bar")
            for bar in rating_bars:
                stars_text = bar.find("span", class_="we-rating-bar__stars")
                count_elem = bar.find("span", class_="we-rating-bar__count")

                if stars_text and count_elem:
                    stars = stars_text.text.strip()
                    count = int(count_elem.text.strip().replace(",", ""))

                    if "5" in stars:
                        distribution.five_stars = count
                    elif "4" in stars:
                        distribution.four_stars = count
                    elif "3" in stars:
                        distribution.three_stars = count
                    elif "2" in stars:
                        distribution.two_stars = count
                    elif "1" in stars:
                        distribution.one_star = count

            web_data["rating_distribution"] = distribution

        # Extract related apps (You Might Also Like)
        similar_section = soup.find(
            "section", attrs={"data-testid": "you-might-also-like"}
        )
        if similar_section:
            for app_elem in similar_section.find_all("a", class_="we-lockup"):
                app_data = self._extract_related_app(app_elem)
                if app_data:
                    web_data["similar_apps"].append(app_data)

        # Extract developer's other apps
        developer_section = soup.find(
            "section", attrs={"data-testid": "more-by-this-developer"}
        )
        if developer_section:
            for app_elem in developer_section.find_all("a", class_="we-lockup"):
                app_data = self._extract_related_app(app_elem)
                if app_data:
                    web_data["developer_apps"].append(app_data)

        return web_data

    def _extract_related_app(self, app_elem) -> Optional[RelatedApp]:
        """Extract related app information from a lockup element"""
        try:
            # Extract app ID from URL
            href = app_elem.get("href", "")
            app_id_match = re.search(r"/id(\d+)", href)
            if not app_id_match:
                return None

            app_id = app_id_match.group(1)

            # Extract name
            name_elem = app_elem.find("h3")
            name = name_elem.text.strip() if name_elem else "Unknown"

            # Extract developer
            dev_elem = app_elem.find("h4")
            developer = dev_elem.text.strip() if dev_elem else "Unknown"

            # Extract icon URL
            icon_elem = app_elem.find("picture")
            icon_url = None
            if icon_elem:
                source = icon_elem.find("source")
                if source and source.get("srcset"):
                    icon_url = source["srcset"].split()[0]

            if not icon_url:
                return None

            # Extract category
            category_elem = app_elem.find("span", class_="we-lockup__subtitle")
            category = category_elem.text.strip() if category_elem else "Unknown"

            # Extract rating
            rating = None
            rating_elem = app_elem.find("span", class_="we-star-rating-stars")
            if rating_elem:
                rating_match = re.search(r"([\d.]+)", rating_elem.get("aria-label", ""))
                if rating_match:
                    rating = float(rating_match.group(1))

            # Extract price
            price_elem = app_elem.find("span", class_="we-lockup__price")
            price = price_elem.text.strip() if price_elem else "Free"

            return RelatedApp(
                app_id=app_id,
                name=name,
                developer=developer,
                icon_url=HttpUrl(icon_url),
                rating=rating,
                price=price,
                category=category,
            )
        except Exception:
            return None

    def _create_combined_metadata(
        self, itunes_data: Dict, web_data: Dict, url: str
    ) -> AppMetadataCombined:
        """Combine iTunes API and web scraped data into unified model"""

        # Process language codes to human-readable
        language_map = {
            "AR": "Arabic",
            "BN": "Bengali",
            "CA": "Catalan",
            "HR": "Croatian",
            "CS": "Czech",
            "DA": "Danish",
            "NL": "Dutch",
            "EN": "English",
            "FI": "Finnish",
            "FR": "French",
            "DE": "German",
            "EL": "Greek",
            "HE": "Hebrew",
            "HI": "Hindi",
            "HU": "Hungarian",
            "ID": "Indonesian",
            "IT": "Italian",
            "JA": "Japanese",
            "KO": "Korean",
            "MS": "Malay",
            "NB": "Norwegian",
            "PL": "Polish",
            "PT": "Portuguese",
            "RO": "Romanian",
            "RU": "Russian",
            "ZH": "Chinese",
            "SK": "Slovak",
            "ES": "Spanish",
            "SV": "Swedish",
            "TH": "Thai",
            "TR": "Turkish",
            "UK": "Ukrainian",
            "VI": "Vietnamese",
        }

        language_codes = itunes_data.get("languageCodesISO2A", [])
        languages = [language_map.get(code, code) for code in language_codes]

        # Process file size
        file_size_bytes = int(itunes_data.get("fileSizeBytes", 0))
        file_size_formatted = (
            self._format_file_size(file_size_bytes) if file_size_bytes else None
        )

        # Build icon URLs dictionary
        icon_urls = {}
        for size in [60, 100, 512]:
            key = f"artworkUrl{size}"
            if key in itunes_data:
                icon_urls[f"{size}x{size}"] = itunes_data[key]

        # Determine data source
        data_source = (
            DataSource.COMBINED if web_data.get("subtitle") else DataSource.ITUNES_API
        )

        return AppMetadataCombined(
            # Core identifiers
            app_id=str(itunes_data["trackId"]),
            bundle_id=itunes_data.get("bundleId"),
            url=HttpUrl(url),
            # Basic info
            name=itunes_data["trackName"],
            subtitle=web_data.get("subtitle"),
            developer_name=itunes_data["artistName"],
            developer_id=str(itunes_data.get("artistId")),
            developer_url=(
                HttpUrl(itunes_data["artistViewUrl"])
                if "artistViewUrl" in itunes_data
                else None
            ),
            # Categories
            primary_category=itunes_data.get("primaryGenreName", "Unknown"),
            primary_category_id=itunes_data.get("primaryGenreId"),
            categories=itunes_data.get("genres", []),
            category_ids=itunes_data.get("genreIds", []),
            # Pricing
            price=itunes_data.get("price", 0.0),
            formatted_price=itunes_data.get("formattedPrice", "Free"),
            currency=itunes_data.get("currency", "USD"),
            in_app_purchases=web_data.get("in_app_purchases"),
            in_app_purchase_list=web_data.get("in_app_purchase_list", []),
            # Version info
            current_version=itunes_data.get("version", "Unknown"),
            current_version_release_date=(
                datetime.fromisoformat(
                    itunes_data["currentVersionReleaseDate"].replace("Z", "+00:00")
                )
                if "currentVersionReleaseDate" in itunes_data
                else None
            ),
            release_notes=itunes_data.get("releaseNotes"),
            version_history=web_data.get("version_history", []),
            # Content
            description=itunes_data.get("description", ""),
            # Technical details
            file_size_bytes=file_size_bytes if file_size_bytes else None,
            file_size_formatted=file_size_formatted,
            minimum_os_version=itunes_data.get("minimumOsVersion"),
            supported_devices=itunes_data.get("supportedDevices", []),
            # Languages
            language_codes=language_codes,
            languages=languages,
            # Ratings and reviews
            content_rating=itunes_data.get("trackContentRating", "Unknown"),
            content_advisories=itunes_data.get("advisories", []),
            average_rating=itunes_data.get("averageUserRating"),
            rating_count=itunes_data.get("userRatingCount"),
            average_rating_current_version=itunes_data.get(
                "averageUserRatingForCurrentVersion"
            ),
            rating_count_current_version=itunes_data.get(
                "userRatingCountForCurrentVersion"
            ),
            rating_distribution=web_data.get("rating_distribution"),
            reviews=web_data.get("reviews", []),
            # Media
            icon_url=HttpUrl(
                itunes_data.get("artworkUrl512", itunes_data.get("artworkUrl100", ""))
            ),
            icon_urls=icon_urls,
            screenshots=[HttpUrl(url) for url in itunes_data.get("screenshotUrls", [])],
            ipad_screenshots=[
                HttpUrl(url) for url in itunes_data.get("ipadScreenshotUrls", [])
            ],
            # Support links
            app_support_url=(
                HttpUrl(web_data["app_support_url"])
                if web_data.get("app_support_url")
                else None
            ),
            privacy_policy_url=(
                HttpUrl(web_data["privacy_policy_url"])
                if web_data.get("privacy_policy_url")
                else None
            ),
            developer_website_url=(
                HttpUrl(web_data["developer_website_url"])
                if web_data.get("developer_website_url")
                else None
            ),
            # Privacy
            privacy=web_data.get("privacy"),
            # Related content
            developer_apps=web_data.get("developer_apps", []),
            similar_apps=web_data.get("similar_apps", []),
            # Rankings
            rankings=web_data.get("rankings", {}),
            # Metadata
            initial_release_date=(
                datetime.fromisoformat(
                    itunes_data["releaseDate"].replace("Z", "+00:00")
                )
                if "releaseDate" in itunes_data
                else None
            ),
            last_updated=datetime.now(UTC),
            data_source=data_source,
            # Features and capabilities
            features=itunes_data.get("features", []),
            is_game_center_enabled=itunes_data.get("isGameCenterEnabled", False),
            is_vpp_device_based_licensing_enabled=itunes_data.get(
                "isVppDeviceBasedLicensingEnabled", False
            ),
            # Additional URLs
            support_url=(
                HttpUrl(itunes_data["sellerUrl"])
                if itunes_data.get("sellerUrl")
                else None
            ),
            marketing_url=(
                HttpUrl(itunes_data["trackViewUrl"])
                if "trackViewUrl" in itunes_data
                else None
            ),
            # Raw data
            raw_itunes_data=itunes_data,
            raw_web_data=web_data if web_data.get("subtitle") else None,
        )

    async def fetch_combined(
        self, url: str, skip_web_scraping: bool = False
    ) -> CombinedScrapeResult:
        """Fetch app data from both sources and combine"""
        app_id = self._extract_app_id(url)
        if not app_id:
            return CombinedScrapeResult(
                success=False,
                error="Could not extract app ID from URL",
                error_details={"url": url},
            )

        country = self._extract_country_code(url)
        data_sources_used = []
        warnings = []

        try:
            async with aiohttp.ClientSession() as session:
                # Always fetch iTunes data first (it's faster and more reliable)
                itunes_data = await self._fetch_itunes_data(session, app_id, country)
                data_sources_used.append(DataSource.ITUNES_API)

                # Optionally fetch web data for additional fields
                web_data = {}
                if not skip_web_scraping:
                    try:
                        html = await self._fetch_web_page(session, url)
                        soup = BeautifulSoup(html, "lxml")
                        web_data = self._parse_web_specific_data(soup)
                        data_sources_used.append(DataSource.WEB_SCRAPE)
                    except Exception as e:
                        warnings.append(f"Web scraping failed: {str(e)}")

                # Combine the data
                metadata = self._create_combined_metadata(itunes_data, web_data, url)

                return CombinedScrapeResult(
                    success=True,
                    app_metadata=metadata,
                    data_sources_used=data_sources_used,
                    warnings=warnings,
                )

        except Exception as e:
            return CombinedScrapeResult(
                success=False,
                error=str(e),
                error_details={"url": url, "app_id": app_id, "type": type(e).__name__},
                data_sources_used=data_sources_used,
            )

    def fetch(self, url: str, skip_web_scraping: bool = False) -> AppMetadataCombined:
        """Synchronous wrapper for fetch_combined"""
        result = asyncio.run(self.fetch_combined(url, skip_web_scraping))
        if not result.success:
            raise Exception(f"Failed to fetch metadata: {result.error}")
        return result.app_metadata
