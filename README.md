# Apple App Store Metadata Extractor

[![PyPI version](https://badge.fury.io/py/apple-appstore-metadata-extractor.svg)](https://badge.fury.io/py/apple-appstore-metadata-extractor)
[![Python Support](https://img.shields.io/pypi/pyversions/apple-appstore-metadata-extractor.svg)](https://pypi.org/project/apple-appstore-metadata-extractor/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Extract and monitor metadata from Apple App Store applications with ease.

## Features

- 📱 **Extract comprehensive app metadata** - title, description, version, ratings, and more
- 🔎 **Keyword & genre search** (v0.2.0) - find apps via iTunes Search API
- 📝 **Review mining** (v0.2.0) - paginated reviews via Apple's RSS feed (~500 per app)
- 📊 **Chart rankings** (v0.2.0) - current top-free/top-paid/top-grossing snapshots
- 🌍 **Storefront support** (v0.2.0) - first-class `country` parameter on every extractor
- 💰 **In-App Purchase details** - extract names and prices of all IAP items
- 🔗 **Support links** - app support, privacy policy, and developer website URLs
- 🔄 **Track version changes** - monitor app updates and metadata changes over time
- 🚀 **Async support** - fast concurrent extraction for multiple apps
- 💪 **Robust error handling** - automatic retries and graceful error recovery
- 🛡️ **Rate limiting** - respect API limits and prevent blocking
- 🎨 **Rich CLI** - beautiful command-line interface with progress tracking
- 📊 **Multiple output formats** - JSON, pretty-printed, or custom formatting

## Installation

```bash
pip install apple-appstore-metadata-extractor
```

## What's New in v0.2.2

Scraper fix for Apple's migration of the App Store product page to a Svelte
frontend, which had silently broken several web-scraped fields:

- **In-app purchases** — `in_app_purchase_list` is populated again (item names
  and prices), parsed from the new Svelte markup.
- **Developer Website / Privacy Policy URLs** — `developer_website_url` and
  `privacy_policy_url` are extracted again.
- `app_support_url` is now typically `None` — Apple removed the explicit
  "App Support" link from the web product page.

> **Known issue:** web screenshot scraping no longer matches the Svelte markup
> and returns nothing; in combined mode screenshots are sourced from the iTunes
> API (which covers most apps). A dedicated fix is tracked for a future release.

## What's New in v0.2.0

v0.2.0 closes three gaps that previously required a third-party service:

- **Search** — `AppStoreSearcher` / `appstore-extractor search`
- **Reviews** — `AppStoreReviewExtractor` / `appstore-extractor reviews`
- **Rankings** — `AppStoreRankingFetcher` / `appstore-extractor chart` & `rank`
- **`CompositeAppStoreClient`** — one client bundling all four extractors with
  a shared rate limiter (default 20 req/min, the iTunes per-IP cap).
- **Country parameter** on every existing extractor (defaults to `"us"`).

Recommended entry point:

```python
import asyncio
from appstore_metadata_extractor import CompositeAppStoreClient

async def discover():
    async with CompositeAppStoreClient(country="us") as client:
        # 1. Find candidate apps.
        hits = await client.search.search("habit tracker", limit=20)

        for hit in hits.hits[:3]:
            # 2. Pull full metadata (existing CombinedExtractor).
            meta = client.metadata.fetch(hit.url)

            # 3. Mine reviews (up to 10 pages ≈ 500 reviews).
            reviews = await client.reviews.fetch_reviews(
                hit.app_id, max_pages=5
            )

            # 4. Look up current chart rank.
            rank = await client.rankings.find_app_rank(
                hit.app_id, chart="top-free"
            )

            print(f"{hit.name}: rank={rank}, reviews={reviews.total_reviews}")

asyncio.run(discover())
```

The four sub-extractors (`AppStoreSearcher`, `AppStoreReviewExtractor`,
`AppStoreRankingFetcher`, `CombinedExtractor`) are also importable
individually if you need finer control.

## Quick Start

### Command Line

Extract metadata for a single app:

```bash
appstore-extractor extract https://apps.apple.com/us/app/example/id123456789
```

Extract from multiple apps:

```bash
appstore-extractor extract-batch apps.json
```

Monitor apps for changes:

```bash
appstore-extractor watch apps.json --interval 3600
```

### Python Library

```python
from appstore_metadata_extractor import AppStoreScraper

# Initialize scraper
scraper = AppStoreScraper()

# Extract single app metadata
metadata = scraper.extract("https://apps.apple.com/us/app/example/id123456789")
print(f"App: {metadata.title}")
print(f"Version: {metadata.version}")
print(f"Rating: {metadata.rating}")

# Access In-App Purchases
if metadata.in_app_purchases:
    print(f"\nIn-App Purchases ({len(metadata.in_app_purchase_list)} items):")
    for iap in metadata.in_app_purchase_list:
        print(f"  - {iap['name']}: {iap['price']}")

# Access Support Links
print(f"\nSupport Links:")
print(f"  App Support: {metadata.app_support_url}")
print(f"  Privacy Policy: {metadata.privacy_policy_url}")
print(f"  Developer Website: {metadata.developer_website_url}")

# Access Screenshots (NEW in v0.1.10)
print(f"\nScreenshots:")
print(f"  iPhone: {len(metadata.screenshots)} screenshots")
print(f"  iPad: {len(metadata.ipad_screenshots)} screenshots")
if metadata.ipad_screenshots:
    print(f"  First iPad screenshot: {metadata.ipad_screenshots[0]}")

# Extract multiple apps
urls = [
    "https://apps.apple.com/us/app/app1/id111111111",
    "https://apps.apple.com/us/app/app2/id222222222"
]
results = scraper.extract_batch(urls)
```

### Async Usage

```python
import asyncio
from appstore_metadata_extractor import CombinedExtractor

async def main():
    extractor = CombinedExtractor()

    # Extract single app
    result = await extractor.extract("https://apps.apple.com/us/app/example/id123456789")

    # Extract multiple apps concurrently
    urls = ["url1", "url2", "url3"]
    results = await extractor.extract_batch(urls)

asyncio.run(main())
```

### Standalone Review Mining (v0.2.0)

```python
import asyncio
from appstore_metadata_extractor import AppStoreReviewExtractor

async def mine_reviews():
    extractor = AppStoreReviewExtractor()
    try:
        # Single app — up to 10 pages ≈ 500 reviews.
        batch = await extractor.fetch_reviews(
            app_id="310633997",       # WhatsApp Messenger
            country="us",
            sort="mostrecent",        # or "mosthelpful"
            max_pages=10,
        )
        print(f"Got {batch.total_reviews} reviews across {batch.pages_fetched} page(s)")
        for review in batch.reviews[:3]:
            print(f"  {review.rating}★ — {review.author}: {review.title}")

        # Batch — many apps at once, with a concurrency cap.
        batches = await extractor.fetch_reviews_batch(
            app_ids=["310633997", "284882215", "454638411"],
            country="us",
            max_pages=3,
            max_concurrent=3,
        )
        for app_id, b in batches.items():
            print(f"{app_id}: {b.total_reviews} reviews")
    finally:
        await extractor.close()

asyncio.run(mine_reviews())
```

### Standalone Chart Rankings (v0.2.0)

```python
import asyncio
from appstore_metadata_extractor import AppStoreRankingFetcher

async def check_rankings():
    fetcher = AppStoreRankingFetcher()
    try:
        # Fetch a full chart snapshot.
        snapshot = await fetcher.fetch_chart(
            chart="top-free",         # "top-free" | "top-paid" | "top-grossing"
            country="us",
            limit=100,
        )
        print(f"Top 3 free apps:")
        for entry in snapshot.entries[:3]:
            print(f"  #{entry.rank} — {entry.name} ({entry.developer_name})")

        # Or just look up one app's rank.
        rank = await fetcher.find_app_rank(
            app_id="310633997", chart="top-free", country="us", limit=100
        )
        print(f"WhatsApp rank: {rank if rank else 'not in top 100'}")
    finally:
        await fetcher.close()

asyncio.run(check_rankings())
```

### Standalone Search (v0.2.0)

```python
import asyncio
from appstore_metadata_extractor import AppStoreSearcher

async def search_competitors():
    searcher = AppStoreSearcher()
    try:
        # Keyword search.
        results = await searcher.search("habit tracker", country="us", limit=25)
        print(f"Found {results.total_count} matches; top {len(results.hits)} returned:")
        for hit in results.hits[:5]:
            print(f"  {hit.name} — {hit.developer_name} ({hit.formatted_price})")

        # Genre-only browse (6017 = Lifestyle).
        top_lifestyle = await searcher.search_by_genre(6017, country="us", limit=10)
        for hit in top_lifestyle.hits:
            print(f"  {hit.primary_category}: {hit.name}")
    finally:
        await searcher.close()

asyncio.run(search_competitors())
```

## CLI Commands

### `extract` - Extract single app metadata

```bash
appstore-extractor extract [OPTIONS] URL

Options:
  -o, --output PATH         Output file path
  -f, --format [json|pretty]  Output format (default: pretty)
  --no-cache               Disable caching
  --country TEXT           Country code (default: us)
```

### `extract-batch` - Extract multiple apps

```bash
appstore-extractor extract-batch [OPTIONS] INPUT_FILE

Options:
  -o, --output PATH         Output file path
  -f, --format [json|pretty]  Output format
  --concurrent INTEGER     Max concurrent requests (default: 5)
  --delay FLOAT           Delay between requests in seconds
```

### `watch` - Monitor apps for changes

```bash
appstore-extractor watch [OPTIONS] INPUT_FILE

Options:
  --interval INTEGER       Check interval in seconds (default: 3600)
  --output-dir PATH       Directory for history files
  --notify               Enable notifications for changes
```

### `search` - Find apps via the iTunes Search API (v0.2.0)

```bash
appstore-extractor search "habit tracker" --limit 25
appstore-extractor search --genre-id 6017 --limit 20  # Lifestyle category

Options:
  --country TEXT          Storefront code (default: us)
  --limit INTEGER         Max results (1–200, default: 50)
  --genre-id INTEGER      Optional category filter
  -o, --output PATH       Write JSON to file instead of stdout
```

### `reviews` / `reviews-batch` - Mine app reviews (v0.2.0)

```bash
appstore-extractor reviews 310633997 --max-pages 5
appstore-extractor reviews-batch ids.txt --max-pages 5 --concurrent 3

Options (reviews):
  --country TEXT                          Storefront code (default: us)
  --max-pages INTEGER                     1–10 (Apple's cap, default: 10)
  --sort [mostrecent|mosthelpful]        Sort order (default: mostrecent)
  -o, --output PATH                       Write JSON to file

reviews-batch reads one app ID per line from IDS_FILE.
```

### `chart` / `rank` - Chart snapshot and per-app rank (v0.2.0)

```bash
appstore-extractor chart top-free --limit 50
appstore-extractor chart top-paid --country us --genre-id 6017 --limit 25
appstore-extractor rank 310633997 --chart top-free --country us
```

## Input File Format

For batch operations, use a JSON file:

```json
{
  "apps": [
    {
      "name": "Example App 1",
      "url": "https://apps.apple.com/us/app/example-1/id123456789"
    },
    {
      "name": "Example App 2",
      "url": "https://apps.apple.com/us/app/example-2/id987654321"
    }
  ]
}
```

## Extracted Fields

The extractor provides comprehensive app metadata including:

### Basic Information
- **app_id** - Apple App Store ID
- **bundle_id** - App bundle identifier
- **url** - App Store URL
- **name** - App name
- **subtitle** - App subtitle/tagline (web scraping required)
- **developer_name** - Developer name
- **developer_id** - Developer ID
- **developer_url** - Developer page URL

### Categories
- **category** / **primary_category** - Primary category name
- **category_id** / **primary_category_id** - Primary category ID
- **categories** - List of all categories
- **category_ids** - List of all category IDs

### Pricing & Purchases
- **price** - App price (numeric value)
- **formatted_price** - Formatted price string (e.g., "$4.99" or "Free")
- **currency** - Currency code (e.g., "USD")
- **in_app_purchases** - Boolean indicating if app has IAPs
- **in_app_purchase_list** - Detailed list of IAPs (web scraping required):
  - name - IAP item name
  - price - Formatted price
  - price_value - Numeric price
  - type - IAP type (auto_renewable_subscription, non_consumable, etc.)
  - currency - Currency code

### Version Information
- **current_version** - Current version number
- **version_date** / **current_version_release_date** - Release date
- **whats_new** / **release_notes** - What's new in this version
- **version_history** - List of previous versions (web scraping required)
- **initial_release_date** - First release date
- **last_updated** - Last update to any field

### Content & Description
- **description** - Full app description
- **content_rating** - Age rating (e.g., "4+", "12+")
- **content_advisories** - List of content warnings

### Languages (web scraping required)
- **languages** - Human-readable language names (e.g., "English", "Spanish")
- **language_codes** - ISO language codes (e.g., "EN", "ES")

### Ratings & Reviews
- **average_rating** - Average user rating (0-5)
- **rating_count** - Total number of ratings
- **average_rating_current_version** - Rating for current version
- **rating_count_current_version** - Ratings for current version
- **rating_distribution** - Star breakdown (web scraping required)
- **reviews** - User reviews list (web scraping required)

### Media Assets
- **icon_url** - App icon URL (512x512)
- **icon_urls** - Dictionary of multiple icon sizes
- **screenshots** - List of iPhone screenshot URLs
- **ipad_screenshots** - List of iPad screenshot URLs (NEW in v0.1.10 - from iTunes API and web scraping)

### Support Links (web scraping required)
- **app_support_url** - Direct link to app support page
- **privacy_policy_url** - Link to privacy policy
- **developer_website_url** - Main developer website
- **support_url** - Support website (alias)
- **marketing_url** - Marketing website

### Technical Details
- **file_size_bytes** - Size in bytes
- **file_size_formatted** - Human-readable size (e.g., "245.8 MB")
- **minimum_os_version** - Minimum iOS version required
- **supported_devices** - List of compatible devices

### Features & Capabilities
- **features** - List of app features/capabilities
- **is_game_center_enabled** - Game Center support
- **is_vpp_device_based_licensing_enabled** - VPP device licensing

### Privacy Information (web scraping required)
- **privacy** - Detailed privacy information including:
  - data_used_to_track
  - data_linked_to_you
  - data_not_linked_to_you
  - privacy_details_url

### Related Content (web scraping required)
- **developer_apps** - Other apps by the same developer
- **similar_apps** - "You might also like" recommendations
- **rankings** - Chart positions (e.g., {"Games": 5, "Overall": 23})

### Metadata
- **data_source** - Source of the data (itunes_api, web_scrape, combined)
- **extracted_at** / **scraped_at** - When data was collected
- **raw_data** - Raw response data (optional, for debugging)

## v0.2.0 Models — Search, Reviews, Rankings

The new extractors return their own typed Pydantic models, separate from
`AppMetadata` / `ExtendedAppMetadata`.

### `SearchHit` (from `AppStoreSearcher.search` / `search_by_genre`)
Per-result fields populated from the iTunes Search API.
- **app_id** — Apple track ID (string)
- **bundle_id** — App bundle identifier (optional)
- **name** — App name (`trackName`)
- **developer_name** — Developer / artist name
- **developer_id** — Artist ID (optional)
- **url** — `apps.apple.com` URL (`trackViewUrl`)
- **icon_url** — Best available artwork URL (512 → 100 → 60 fallback)
- **average_rating** — `averageUserRating` (optional)
- **rating_count** — `userRatingCount` (optional)
- **price** — Numeric price in the storefront currency
- **formatted_price** — Price as a display string (e.g. `"Free"`, `"$4.99"`)
- **primary_category** — `primaryGenreName`
- **primary_category_id** — `primaryGenreId`
- **description** — Full description (iTunes Search returns this inline)
- **country** — Storefront the result came from

### `SearchResults` (wrapper for a single query)
- **query** — The original search term (or `"genre:<id>"` for genre-only searches)
- **country** — Storefront code
- **total_count** — `resultCount` from the API (may exceed `len(hits)` if the
  API truncated)
- **hits** — List of `SearchHit`
- **fetched_at** — UTC timestamp the query was issued

### `Review` (one user review, reused from `models_combined.Review`)
- **author** — Reviewer's screen name
- **rating** — Star rating, 1–5 (validated)
- **title** — Review title (optional)
- **content** — Review body
- **date** — `datetime` parsed from the RSS `updated` field
- **version** — App version the review was written against (optional)
- **helpful_count** — `im:voteSum` count (coerced to int; 0 if missing)

### `ReviewBatch` (from `AppStoreReviewExtractor.fetch_reviews`)
- **app_id** — The target app ID
- **country** — Storefront code
- **sort** — `"mostrecent"` or `"mosthelpful"`
- **pages_fetched** — How many pages were actually fetched (≤ requested `max_pages`)
- **total_reviews** — `len(reviews)` after dedup
- **reviews** — List of `Review`
- **fetched_at** — UTC timestamp
- **has_more** — `True` if we stopped at the requested cap rather than end-of-data
- **notes** — Diagnostic strings (e.g. `"page 5: 404 — end of data"`)

### `RankingEntry` (one entry in a chart, 1-indexed)
- **rank** — Position in the chart, starting at 1
- **app_id** — Apple track ID
- **name** — App name
- **developer_name** — Developer / artist name
- **genre_ids** — List of genre IDs (often empty for the overall chart)
- **artwork_url** — Icon URL (`artworkUrl100`, optional)
- **url** — `apps.apple.com` URL if Apple includes it

### `ChartSnapshot` (from `AppStoreRankingFetcher.fetch_chart`)
- **chart** — `"top-free"`, `"top-paid"`, or `"top-grossing"`
- **country** — Storefront code
- **genre_id** — `None` for the overall chart, otherwise the genre filter applied
- **fetched_at** — UTC timestamp — stitch these together to build history
- **entries** — Ordered list of `RankingEntry`

> Snapshots are point-in-time only. The package returns the chart as it is
> *right now*; storing daily snapshots for trend history is the consumer's
> responsibility.

## Migration Guide

### v0.1.10 - Screenshot Updates
The iTunes API extractor now returns `ExtendedAppMetadata` instead of basic `AppMetadata`, which includes:
- `ipad_screenshots` - Separate field for iPad screenshots
- `developer_url` - Developer page URL from iTunes
- `initial_release_date` - When the app was first released
- `average_rating_current_version` and `rating_count_current_version`

```python
# The screenshots field still contains iPhone screenshots
iphone_screenshots = metadata.screenshots  # iPhone only

# NEW: iPad screenshots are now separate
ipad_screenshots = metadata.ipad_screenshots  # iPad only (if available)
```

### v0.1.6 - CombinedExtractor Migration

If you were using `CombinedAppStoreScraper`, it has been consolidated into `CombinedExtractor`. The old class name still works via an alias, but we recommend updating your code:

```python
# Old way (still works via alias)
from appstore_metadata_extractor import CombinedAppStoreScraper
scraper = CombinedAppStoreScraper()
result = scraper.fetch(url)

# New way (recommended)
from appstore_metadata_extractor import CombinedExtractor
extractor = CombinedExtractor()
metadata = extractor.fetch(url)  # Synchronous method
# or
result = await extractor.extract(url)  # Async method
```

The new `CombinedExtractor` offers:
- Full backward compatibility
- Better type safety
- Support for extraction modes (iTunes-only vs combined)
- Both sync and async interfaces

## Advanced Usage

### Custom Extraction Modes

```python
from appstore_metadata_extractor import CombinedExtractor, ExtractionMode

extractor = CombinedExtractor()

# API-only mode (faster, less data)
result = await extractor.extract(url, mode=ExtractionMode.API_ONLY)

# Web scraping mode (slower, more complete)
result = await extractor.extract(url, mode=ExtractionMode.WEB_SCRAPE)

# Combined mode (default - best of both)
result = await extractor.extract(url, mode=ExtractionMode.COMBINED)
```

### Rate Limiting Configuration

```python
from appstore_metadata_extractor import RateLimiter

# Configure custom rate limits
rate_limiter = RateLimiter(
    calls_per_minute=20,  # iTunes API limit
    min_delay=1.0        # Minimum delay between calls
)

scraper = AppStoreScraper(rate_limiter=rate_limiter)
```

### Caching

```python
from appstore_metadata_extractor import CacheManager

# Configure cache
cache = CacheManager(
    ttl=300,  # Cache TTL in seconds
    max_size=1000  # Maximum cache entries
)

scraper = AppStoreScraper(cache_manager=cache)
```

## Error Handling

The library provides robust error handling with automatic retries:

```python
from appstore_metadata_extractor import AppNotFoundError, RateLimitError

try:
    metadata = scraper.extract(url)
except AppNotFoundError:
    print("App not found")
except RateLimitError:
    print("Rate limit exceeded, please wait")
except Exception as e:
    print(f"Extraction failed: {e}")
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed development setup and workflow instructions.

**Quick Start:**
```bash
# Clone and setup
git clone https://github.com/yourusername/appstore-metadata-extractor-python.git
cd appstore-metadata-extractor-python
./dev-setup.sh

# Activate environment and develop
source venv/bin/activate
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This tool is for educational and research purposes only. Make sure to comply with Apple's Terms of Service and robots.txt when using this tool. Be respectful of rate limits and implement appropriate delays between requests.

## Acknowledgments

- Built with [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) for web scraping
- Uses [Rich](https://github.com/Textualize/rich) for beautiful CLI output
- Powered by [Pydantic](https://pydantic-docs.helpmanual.io/) for data validation

## Related Projects

For a full-featured solution with web API, authentication, and UI, check out the [parent project](https://github.com/Bickster-LLC/appstore-metadata-extractor).
