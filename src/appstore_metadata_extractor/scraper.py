import asyncio
import json
import re
from datetime import UTC, datetime
from typing import List, Optional

import aiohttp
from bs4 import BeautifulSoup
from pydantic import HttpUrl
from tenacity import retry, stop_after_attempt, wait_exponential

from .models import AppInput, AppMetadata, BatchScrapeResult, ScrapeResult


class AppStoreScraper:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def _fetch_page(self, session: aiohttp.ClientSession, url: str) -> str:
        async with session.get(
            url, headers=self.headers, timeout=self.timeout
        ) as response:
            response.raise_for_status()
            return await response.text()

    def _extract_app_id(self, url: str) -> Optional[str]:
        match = re.search(r"/id(\d+)", str(url))
        return match.group(1) if match else None

    def _parse_metadata(self, html: str, url: str) -> AppMetadata:
        soup = BeautifulSoup(html, "lxml")

        app_id = self._extract_app_id(url)
        if not app_id:
            raise ValueError(f"Could not extract app ID from URL: {url}")

        # Try to extract data from JSON-LD structured data first
        json_ld_data = {}
        json_ld_elem = soup.find("script", type="application/ld+json")
        if json_ld_elem and json_ld_elem.string:  # type: ignore[union-attr]
            try:
                json_ld_data = json.loads(json_ld_elem.string)  # type: ignore[union-attr]
            except Exception:
                pass

        # Extract from JSON-LD or fall back to HTML parsing
        title = json_ld_data.get("name", "")
        if not title:
            title_elem = soup.find("h1", class_="product-header__title")
            if title_elem:
                # Clean up the title to remove age rating badge
                title_text = title_elem.get_text(strip=True)
                title = re.sub(r"\s*(4\+|9\+|12\+|17\+)\s*$", "", title_text)

        subtitle_elem = soup.find("h2", class_="product-header__subtitle")
        subtitle = subtitle_elem.text.strip() if subtitle_elem else None

        developer = "Unknown"
        if "author" in json_ld_data and isinstance(json_ld_data["author"], dict):
            developer = json_ld_data["author"].get("name", "Unknown")
        else:
            developer_elem = soup.find("h2", class_="product-header__identity")
            developer = "Unknown"
            if developer_elem:
                dev_link = developer_elem.find("a")
                if dev_link:
                    developer = dev_link.text.strip()

        # Extract price
        price = "Free"
        if "offers" in json_ld_data and isinstance(json_ld_data["offers"], dict):
            price_value = json_ld_data["offers"].get("price", 0)
            if price_value == 0:
                price = "Free"
            else:
                currency = json_ld_data["offers"].get("priceCurrency", "USD")
                price = (
                    f"${price_value}"
                    if currency == "USD"
                    else f"{price_value} {currency}"
                )

        # Check for in-app purchases
        in_app_purchases = False
        in_app_purchase_list = []

        # Look for the Information section
        info_section = soup.find("section", class_="section section--information")
        if not info_section:
            info_section = soup.find("section", {"class": re.compile("information")})

        if info_section:
            in_app_elem = info_section.find("dt", string=re.compile("In-App Purchases"))
            if in_app_elem:
                in_app_purchases = True

                # Extract detailed IAP information
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
                            in_app_purchase_list.append(
                                {"name": name, "price": price_str}
                            )

        # Extract version information
        version = "Unknown"
        version_date = None

        # Method 1: Look for version in whats-new section
        whats_new_section = soup.find("section", class_="section--whats-new")
        if whats_new_section:
            # Try multiple selectors for version info
            version_elem = whats_new_section.find(
                "p", class_="whats-new__latest__version"
            )
            if not version_elem:
                # Try to find any p tag with version text
                for p in whats_new_section.find_all("p"):
                    if p.text and "Version" in p.text:
                        version_elem = p
                        break

            if version_elem:
                version_text = version_elem.text.strip()
                version_match = re.search(r"Version\s+([\d.]+)", version_text)
                if version_match:
                    version = version_match.group(1)

                # Try to extract date
                date_match = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})", version_text)
                if date_match:
                    try:
                        version_date = datetime.strptime(
                            date_match.group(1), "%m/%d/%Y"
                        )
                    except Exception:
                        try:
                            version_date = datetime.strptime(
                                date_match.group(1), "%m/%d/%y"
                            )
                        except Exception:
                            pass

        # Method 2: Search entire page for version pattern
        if version == "Unknown":
            # Look for version anywhere in the page
            version_texts = soup.find_all(string=re.compile(r"Version\s+[\d.]+"))
            for text in version_texts:
                if text.parent and text.parent.name not in ["script", "style"]:
                    version_match = re.search(r"Version\s+([\d.]+)", text)
                    if version_match:
                        version = version_match.group(1)
                        break

        # Extract description
        description = json_ld_data.get("description", "")
        if not description:
            description_section = soup.find("section", class_="section--description")
            if description_section:
                desc_div = description_section.find(
                    "div", class_="section__description"
                )
                if desc_div:
                    description = desc_div.get_text(strip=True)

        # Extract ratings
        rating = None
        rating_count = None
        if "aggregateRating" in json_ld_data and isinstance(
            json_ld_data["aggregateRating"], dict
        ):
            rating = json_ld_data["aggregateRating"].get("ratingValue")
            rating_count = json_ld_data["aggregateRating"].get("reviewCount")
        else:
            rating_elem = soup.find("figcaption", class_="we-rating-count")
            if rating_elem:
                rating_text = rating_elem.text.strip()
                rating_match = re.search(r"([\d.]+)\s+out\s+of\s+5", rating_text)
                if rating_match:
                    rating = float(rating_match.group(1))

                count_match = re.search(r"([\d,K.M]+)\s+Ratings?", rating_text)
                if count_match:
                    count_str = count_match.group(1).replace(",", "")
                    if "K" in count_str:
                        rating_count = int(float(count_str.replace("K", "")) * 1000)
                    elif "M" in count_str:
                        rating_count = int(float(count_str.replace("M", "")) * 1000000)
                    else:
                        rating_count = int(count_str)

        # Extract category
        category = json_ld_data.get("applicationCategory", "Unknown")
        if category == "Unknown":
            info_section = soup.find("section", class_="section--information")
            if info_section:
                category_dt = info_section.find("dt", string="Category")
                if category_dt:
                    category_dd = category_dt.find_next_sibling("dd")
                    if category_dd:
                        category = category_dd.get_text(strip=True)

        # Extract app size
        size = None
        info_section = soup.find("section", class_="section--information")
        if info_section:
            size_dt = info_section.find("dt", string="Size")
            if size_dt:
                size_dd = size_dt.find_next_sibling("dd")
                if size_dd:
                    size = size_dd.get_text(strip=True)

        # Extract languages
        languages = []
        if info_section:
            lang_dt = info_section.find("dt", string="Languages")
            if lang_dt:
                lang_dd = lang_dt.find_next_sibling("dd")
                if lang_dd:
                    lang_text = lang_dd.get_text(strip=True)
                    languages = [lang.strip() for lang in lang_text.split(",")]

        # Extract age rating
        age_rating = None
        if info_section:
            age_dt = info_section.find("dt", string="Age Rating")
            if age_dt:
                age_dd = age_dt.find_next_sibling("dd")
                if age_dd:
                    age_rating = age_dd.get_text(strip=True)

        # Extract icon URL
        icon_url = json_ld_data.get("image")
        if not icon_url:
            # Try meta tags
            meta_icon = soup.find("meta", property="og:image")
            if meta_icon:
                icon_url = meta_icon.get("content")

        # Extract screenshots
        screenshots = json_ld_data.get("screenshot", [])
        if isinstance(screenshots, list):
            # Filter to get only the main screenshots (not iPad ones)
            screenshots = [url for url in screenshots if "643x0w" in url][:5]

        # Extract support links
        app_support_url = None
        privacy_policy_url = None
        developer_website_url = None

        # Look for links in Information section
        if info_section:
            links = info_section.find_all("a")
            for link in links:
                href = link.get("href")
                text = link.get_text()
                if href:
                    if "App Support" in text:
                        app_support_url = href
                    elif "Privacy Policy" in text:
                        privacy_policy_url = href
                    elif "Developer Website" in text:
                        developer_website_url = href

        # Extract what's new
        whats_new = None
        if whats_new_section:
            # Try multiple selectors for what's new content
            whats_new_div = whats_new_section.find("div", class_="section__description")
            if not whats_new_div:
                # Try alternative selector
                whats_new_div = whats_new_section.find("div", class_="we-truncate")

            if whats_new_div:
                # Get all text content, handling multiple paragraphs
                whats_new_parts = []
                for elem in whats_new_div.find_all(["p", "div", "span"]):
                    text = elem.get_text(strip=True)
                    if text and text not in whats_new_parts:
                        whats_new_parts.append(text)

                if whats_new_parts:
                    whats_new = "\n".join(whats_new_parts)
                else:
                    whats_new = whats_new_div.get_text(strip=True)

        return AppMetadata(
            app_id=app_id,
            url=HttpUrl(url),
            title=title,
            subtitle=subtitle,
            developer=developer,
            category=category,
            price=price,
            in_app_purchases=in_app_purchases,
            in_app_purchase_list=in_app_purchase_list,
            description=description,
            version=version,
            version_date=version_date,
            size=size,
            languages=languages,
            age_rating=age_rating,
            rating=rating,
            rating_count=rating_count,
            screenshots=screenshots,
            icon_url=HttpUrl(icon_url) if icon_url else None,
            app_support_url=HttpUrl(app_support_url) if app_support_url else None,
            privacy_policy_url=(
                HttpUrl(privacy_policy_url) if privacy_policy_url else None
            ),
            developer_website_url=(
                HttpUrl(developer_website_url) if developer_website_url else None
            ),
            whats_new=whats_new,
        )

    async def extract_async(self, url: str) -> ScrapeResult:
        try:
            async with aiohttp.ClientSession() as session:
                html = await self._fetch_page(session, url)
                metadata = self._parse_metadata(html, url)
                return ScrapeResult(success=True, app_metadata=metadata)
        except Exception as e:
            return ScrapeResult(
                success=False,
                error=str(e),
                error_details={"url": url, "type": type(e).__name__},
            )

    def extract(self, url: str) -> AppMetadata:
        result = asyncio.run(self.extract_async(url))
        if not result.success:
            raise Exception(f"Failed to extract metadata: {result.error}")
        return result.app_metadata

    async def extract_batch_async(self, urls: List[str]) -> BatchScrapeResult:
        start_time = datetime.now(UTC)
        tasks = [self.extract_async(url) for url in urls]
        results = await asyncio.gather(*tasks)

        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        duration = (datetime.now(UTC) - start_time).total_seconds()

        return BatchScrapeResult(
            total=len(results),
            successful=successful,
            failed=failed,
            results=results,
            duration_seconds=duration,
        )

    def extract_batch(self, urls: List[str]) -> BatchScrapeResult:
        return asyncio.run(self.extract_batch_async(urls))

    def extract_from_json(self, json_path: str) -> BatchScrapeResult:
        with open(json_path, "r") as f:
            data = json.load(f)

        apps = [AppInput(**app) for app in data.get("apps", [])]
        urls = [str(app.url) for app in apps]

        return self.extract_batch(urls)
