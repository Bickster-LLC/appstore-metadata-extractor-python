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

## What's New in v0.3.x

See [CHANGELOG.md](https://github.com/Bickster-LLC/appstore-metadata-extractor-python/blob/main/CHANGELOG.md)
for the full history.

- **Genre-filtered chart rankings actually work (v0.3.1)** — passing
  `genre_id` to `AppStoreRankingFetcher.fetch_chart()` / `find_app_rank()`
  used to fail with a `NetworkError` because Apple's Marketing Tools feed
  404s on genre queries. Charts now use the legacy iTunes RSS endpoint,
  which supports both overall and per-genre charts. The public API is
  unchanged.
- **More iTunes Lookup fields mapped (v0.3.0)** — `ExtendedAppMetadata`
  (and `AppMetadataCombined`) now populate `categories`, `category_ids`,
  `features`, `supported_devices`, `language_codes`,
  `content_advisories`, `icon_urls` (60/100/512px variants),
  `is_game_center_enabled`, and `is_vpp_device_based_licensing_enabled`
  straight from the iTunes API — including in iTunes-only mode
  (`skip_web_scraping=True`).

## What's New in v0.2.x

- **Web screenshot scraping restored (v0.2.5)** — Apple's Svelte page
  migration had broken screenshot scraping; a signal-based fallback now
  recovers iPhone and iPad screenshots from the new markup, so combined
  mode fills gaps the iTunes API leaves (e.g. ChatGPT went 0 → 6 iPhone /
  0 → 5 iPad screenshots).
- **Svelte scraper fixes (v0.2.2)** — `in_app_purchase_list`,
  `developer_website_url`, and `privacy_policy_url` are extracted again
  from the new Svelte markup. `app_support_url` is now typically `None` —
  Apple removed the explicit "App Support" link from the product page.
- **Search, Reviews, and Rankings (v0.2.0)** — closed three gaps that
  previously required a third-party service: `AppStoreSearcher`
  (`appstore-extractor search`), `AppStoreReviewExtractor`
  (`appstore-extractor reviews`), `AppStoreRankingFetcher`
  (`appstore-extractor chart` & `rank`), plus `CompositeAppStoreClient`
  bundling all four extractors behind one shared rate limiter (default
  20 req/min, the iTunes per-IP cap) and a `country` parameter on every
  extractor (defaults to `"us"`).

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
from appstore_metadata_extractor import CombinedExtractor, WBSConfig

# Initialize the combined extractor (iTunes API + web scraping)
extractor = CombinedExtractor(WBSConfig())

# Extract single app metadata
metadata = extractor.fetch("https://apps.apple.com/us/app/example/id123456789")
print(f"App: {metadata.name}")
print(f"Version: {metadata.current_version}")
print(f"Rating: {metadata.average_rating} ({metadata.rating_count} ratings)")

# Access In-App Purchases (items are InAppPurchase objects on this model)
if metadata.in_app_purchases:
    print(f"\nIn-App Purchases ({len(metadata.in_app_purchase_list)} items):")
    for iap in metadata.in_app_purchase_list:
        print(f"  - {iap.name}: {iap.price}")

# Access Support Links (from web scraping). Note: app_support_url is usually
# None — Apple removed the "App Support" link from the web product page.
print(f"\nSupport Links:")
print(f"  Privacy Policy: {metadata.privacy_policy_url}")
print(f"  Developer Website: {metadata.developer_website_url}")

# Access Screenshots
print(f"\nScreenshots:")
print(f"  iPhone: {len(metadata.screenshots)} screenshots")
print(f"  iPad: {len(metadata.ipad_screenshots)} screenshots")
if metadata.ipad_screenshots:
    print(f"  First iPad screenshot: {metadata.ipad_screenshots[0]}")

# Extract multiple apps (synchronous) -> dict keyed by URL (successful only)
urls = [
    "https://apps.apple.com/us/app/app1/id111111111",
    "https://apps.apple.com/us/app/app2/id222222222"
]
results = extractor.fetch_batch(urls)
```

> **Note on IAP access:** `CombinedExtractor.fetch()` returns an
> `ExtendedAppMetadata` whose `in_app_purchase_list` holds `InAppPurchase`
> objects (`iap.name`). The backward-compatible `fetch_combined()` returns an
> `AppMetadataCombined` whose `in_app_purchase_list` holds plain dicts
> (`iap["name"]`). Use the access style that matches the method you call.

### Async Usage

```python
import asyncio
from appstore_metadata_extractor import CombinedExtractor, WBSConfig

async def main():
    extractor = CombinedExtractor(WBSConfig())

    # Extract single app -> ExtractionResult (.success, .metadata)
    result = await extractor.extract("https://apps.apple.com/us/app/example/id123456789")
    if result.success:
        print(result.metadata.name, result.metadata.current_version)

    # Extract multiple apps concurrently -> list of ExtractionResult
    urls = [
        "https://apps.apple.com/us/app/app1/id111111111",
        "https://apps.apple.com/us/app/app2/id222222222",
    ]
    results = await extractor.fetch_batch_async(urls)
    for r in results:
        if r.success:
            print(r.metadata.name)

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

> **Note:** Some fields below are defined on the model but **not yet populated**
> by the current extractors — they return their default (`None`, `[]`, or
> `False`) and are marked _(reserved — not yet populated)_. Reserved fields:
> `version_history`, `rating_distribution`, `reviews`, `privacy`,
> `developer_apps`, `similar_apps`, `rankings`, `support_url`,
> `marketing_url`. For reviews and chart rankings, use the dedicated
> `AppStoreReviewExtractor` and `AppStoreRankingFetcher` instead.

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
- **categories** - List of all categories (from iTunes `genres`)
- **category_ids** - List of all category IDs (from iTunes `genreIds`)

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
- **version_history** - List of previous versions _(reserved — not yet populated)_
- **initial_release_date** - First release date
- **last_updated** - Last update to any field

### Content & Description
- **description** - Full app description
- **content_rating** - Age rating (e.g., "4+", "12+")
- **content_advisories** - List of content warnings (from iTunes `advisories`)

### Languages
- **languages** - Human-readable language names (e.g., "English", "Spanish") _(web scraping required)_
- **language_codes** - ISO language codes (e.g., "EN", "ES") (from iTunes `languageCodesISO2A`; web scraping provides them too in combined mode)

### Ratings & Reviews
- **average_rating** - Average user rating (0-5)
- **rating_count** - Total number of ratings
- **average_rating_current_version** - Rating for current version
- **rating_count_current_version** - Ratings for current version
- **rating_distribution** - Star breakdown _(reserved — not yet populated)_
- **reviews** - User reviews list _(reserved on this model — use `AppStoreReviewExtractor`)_

### Media Assets
- **icon_url** - App icon URL (512x512)
- **icon_urls** - Dict of icon size (`"60"`, `"100"`, `"512"`) to URL (from iTunes `artworkUrl60/100/512`)
- **screenshots** - List of iPhone screenshot URLs
- **ipad_screenshots** - List of iPad screenshot URLs (NEW in v0.1.10 - from iTunes API and web scraping)

### Support Links (web scraping required)
- **app_support_url** - Direct link to app support page _(usually `None` — Apple removed this link from the web product page)_
- **privacy_policy_url** - Link to privacy policy
- **developer_website_url** - Main developer website
- **support_url** - Support website (alias) _(reserved — not yet populated)_
- **marketing_url** - Marketing website _(reserved — not yet populated)_

### Technical Details
- **file_size_bytes** - Size in bytes
- **file_size_formatted** - Human-readable size (e.g., "245.8 MB")
- **minimum_os_version** - Minimum iOS version required
- **supported_devices** - List of compatible device identifiers (from iTunes `supportedDevices`)

### Features & Capabilities
- **features** - List of app features/capabilities (from iTunes `features`)
- **is_game_center_enabled** - Game Center support (from iTunes `isGameCenterEnabled`)
- **is_vpp_device_based_licensing_enabled** - VPP device licensing (from iTunes `isVppDeviceBasedLicensingEnabled`)

### Privacy Information _(reserved — not yet populated)_
- **privacy** - Detailed privacy information including:
  - data_used_to_track
  - data_linked_to_you
  - data_not_linked_to_you
  - privacy_details_url

### Related Content _(reserved — not yet populated)_
- **developer_apps** - Other apps by the same developer
- **similar_apps** - "You might also like" recommendations
- **rankings** - Chart positions (e.g., {"Games": 5, "Overall": 23}) — for chart data use `AppStoreRankingFetcher`

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
from appstore_metadata_extractor import CombinedAppStoreScraper, WBSConfig
scraper = CombinedAppStoreScraper(WBSConfig())
metadata = scraper.fetch(url)

# New way (recommended)
from appstore_metadata_extractor import CombinedExtractor, WBSConfig
extractor = CombinedExtractor(WBSConfig())
metadata = extractor.fetch(url)              # Synchronous method
# or
result = await extractor.extract(url)        # Async method -> ExtractionResult
```

The new `CombinedExtractor` offers:
- Full backward compatibility
- Better type safety
- Support for extraction modes (iTunes-only vs combined)
- Both sync and async interfaces

## Advanced Usage

### Custom Extraction Modes

Mode selection is controlled by the `skip_web_scraping` flag, not an
`ExtractionMode` argument:

```python
from appstore_metadata_extractor import CombinedExtractor, WBSConfig

extractor = CombinedExtractor(WBSConfig())

# iTunes API only (faster; no IAPs, languages, or support URLs)
metadata = extractor.fetch(url, skip_web_scraping=True)

# Combined: iTunes API + web scraping (default — most complete)
metadata = extractor.fetch(url, skip_web_scraping=False)

# Async equivalents:
#   result = await extractor.extract_with_mode(url, skip_web_scraping=True)
#   result = await extractor.extract(url)  # always combined
```

### Rate Limiting Configuration

`RateLimiter` is configured per service via `configure()` and shared across the
extractors bundled in a `CompositeAppStoreClient`:

```python
from appstore_metadata_extractor import CompositeAppStoreClient, RateLimiter

rate_limiter = RateLimiter()
rate_limiter.configure("itunes_api", max_requests=20, time_window=60)

async with CompositeAppStoreClient(rate_limiter=rate_limiter) as client:
    hits = await client.search.search("habit tracker", limit=10)
```

### Caching

```python
from appstore_metadata_extractor import CompositeAppStoreClient, CacheManager

cache = CacheManager(default_ttl=300)  # Cache TTL in seconds

async with CompositeAppStoreClient(cache_manager=cache) as client:
    hits = await client.search.search("notes", limit=10)
```

## Error Handling

The library retries transient failures automatically and raises typed
exceptions (import from `appstore_metadata_extractor.core.exceptions`):

```python
from appstore_metadata_extractor import CombinedExtractor, WBSConfig
from appstore_metadata_extractor.core.exceptions import (
    ExtractionError,   # e.g. no app found for the given ID
    NetworkError,      # HTTP / connection failure
    RateLimitError,    # rate limit exceeded
    ValidationError,   # invalid App Store URL
)

extractor = CombinedExtractor(WBSConfig())
try:
    metadata = extractor.fetch(url)
except ValidationError:
    print("Invalid App Store URL")
except RateLimitError:
    print("Rate limit exceeded, please wait")
except NetworkError:
    print("Network error")
except ExtractionError:
    print("Extraction failed (e.g. app not found)")
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
