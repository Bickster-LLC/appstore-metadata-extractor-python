# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.4] - 2026-05-28

### Documentation
- Correct the README API examples, which are also the PyPI project
  description. The quick-start and async examples now use the modern
  `CombinedExtractor(WBSConfig())` API with accurate field names and methods
  (`fetch`, `fetch_batch`, `fetch_batch_async`); the previous snippets used
  legacy `AppStoreScraper` attributes, called `CombinedExtractor()` with no
  args, and referenced a non-existent `extract_batch()`.
- Fix the migration, extraction-mode, rate-limiting, caching, and
  error-handling snippets to match the real API (`skip_web_scraping` flag,
  `RateLimiter.configure()`, `CacheManager(default_ttl=…)`,
  `CompositeAppStoreClient` injection, and the actual exceptions in
  `core.exceptions`; `AppNotFoundError` never existed).
- Mark model fields that exist but are not populated by the extractors
  (`features`, `rating_distribution`, `version_history`, `categories`,
  `content_advisories`, `privacy`, `similar_apps`, `developer_apps`,
  `rankings`, `support_url`, `marketing_url`, `icon_urls`,
  `supported_devices`) as "reserved — not yet populated".

No code changes.

## [0.2.3] - 2026-05-28

### Documentation
- Update the README "What's New" section to cover the v0.2.1/v0.2.2 App Store
  Svelte scraper fixes. The README is the package long description shown on
  PyPI, so this release exists to surface those notes on the PyPI project page
  (distribution metadata is immutable per version). No code changes.

## [0.2.2] - 2026-05-28

Re-release of 0.2.1 with corrected, structured release notes. No functional
code changes — the App Store Svelte scraper fixes below are identical to 0.2.1.

### Fixed
- **In-app purchase extraction for the Svelte App Store page**: Apple migrated
  the product page to a Svelte frontend, removing the `section--information`
  and `list-with-numbers__item` markup the scraper relied on, which silently
  returned an empty IAP list. `_extract_in_app_purchases` now reads the
  current `<dt>In-App Purchases</dt><dd>…<div class="text-pair">` structure
  (matching the stable `text-pair` token rather than volatile `svelte-*`
  hashes) and skips non-purchase rows such as the trailing "Learn More" link.
  Legacy markup is still handled as a fallback.
- **Developer Website / Privacy Policy URL extraction**: these links moved out
  of the information section into standalone anchors. They are now matched by
  exact anchor text globally, so `developer_website_url` and
  `privacy_policy_url` populate again.

### Changed
- `app_support_url` is now typically `None`: Apple removed the explicit
  "App Support" link from the web product page, and it was never available
  from the iTunes API. The lookup is retained for forward compatibility.

### Known Issues
- Web screenshot scraping (`_extract_screenshots` /
  `_extract_ipad_screenshots`) no longer matches the Svelte markup and returns
  nothing. In combined mode screenshots are sourced from the iTunes API, which
  covers most apps; a dedicated fix is tracked for a future release.

## [0.2.1] - 2026-05-28

### Fixed
- **In-app purchase extraction for the Svelte App Store page**: Apple migrated
  the product page to a Svelte frontend, removing the `section--information`
  and `list-with-numbers__item` markup the scraper relied on, which silently
  returned an empty IAP list. `_extract_in_app_purchases` now reads the
  current `<dt>In-App Purchases</dt><dd>…<div class="text-pair">` structure
  (matching the stable `text-pair` token rather than volatile `svelte-*`
  hashes) and skips non-purchase rows such as the trailing "Learn More" link.
  Legacy markup is still handled as a fallback.
- **Developer Website / Privacy Policy URL extraction**: these links moved out
  of the information section into standalone anchors. They are now matched by
  exact anchor text globally, so `developer_website_url` and
  `privacy_policy_url` populate again.

### Changed
- `app_support_url` is now typically `None`: Apple removed the explicit
  "App Support" link from the web product page, and it was never available
  from the iTunes API. The lookup is retained for forward compatibility.

### Known Issues
- Web screenshot scraping (`_extract_screenshots` /
  `_extract_ipad_screenshots`) no longer matches the Svelte markup and returns
  nothing. In combined mode screenshots are sourced from the iTunes API, which
  covers most apps; a dedicated fix is tracked for a future release.

## [0.2.0] - 2026-05-25

### Added
- **Search / Discovery** (`AppStoreSearcher`, CLI `search`): Find apps by
  keyword or genre via the iTunes Search API. Returns `SearchResults` with
  typed `SearchHit` entries. Supports country/storefront, limit (≤200), and
  optional `genre_id` filtering. Cache TTL: 1 hour.
- **Review Extraction** (`AppStoreReviewExtractor`, CLI `reviews` /
  `reviews-batch`): Paginated reviews via the Apple RSS customer-reviews feed,
  up to Apple's 10-page (~500 review) cap. Returns `ReviewBatch` (timestamped,
  with diagnostic notes) containing the existing `Review` model populated for
  the first time. Dedup by review id; stops cleanly on 404 or empty pages.
  Batch mode uses `asyncio.Semaphore` to cap concurrency. Cache TTL: 24 hours.
- **Rankings Snapshot** (`AppStoreRankingFetcher`, CLI `chart` / `rank`):
  Current chart positions via Apple Marketing Tools RSS
  (`rss.marketingtools.apple.com`). Returns `ChartSnapshot` with rank-ordered
  `RankingEntry` items. Includes `find_app_rank()` convenience to look up one
  app's position. Snapshot only — historical tracking is the consumer's job.
  Cache TTL: 1 hour.
- **Country parameter on existing extractors**:
  `ITunesAPIExtractor.extract`, `WebScraperExtractor.extract`, and
  `CombinedExtractor.extract` (plus `extract_with_mode`, `fetch`,
  `fetch_batch`, `fetch_combined`) now accept a `country` argument (default
  `"us"`). The web scraper rewrites the `/<cc>/app/` URL segment to match.
- **`CompositeAppStoreClient`**: Convenience wrapper bundling search,
  metadata, reviews, and rankings, sharing a single `RateLimiter` (default
  20 req/min, the iTunes per-IP cap) and `CacheManager` across all four
  extractors. Supports `async with` for automatic cleanup.

### Notes
- Backward compatible — no existing public APIs changed; all new arguments
  have defaults.
- The previously-defined `reviews`, `rankings`, and `similar_apps` fields on
  `AppMetadataCombined` remain unpopulated by the existing extractors — use
  the new dedicated extractors instead.
- `similar_apps` extraction is intentionally out of scope for 0.2.0.
- Test infrastructure: `pytest` now defaults to skipping `@pytest.mark.integration`
  tests; opt in with `pytest -m integration` to hit real Apple endpoints. All
  existing files under `tests/integration/` were retroactively marked
  `pytestmark = pytest.mark.integration` so CI stays green when Apple's HTML
  drifts (the legacy tests still run on demand).

## [0.1.12] - 2025-08-06

### Added
- **Platform-specific screenshot extraction**: Web scraper now fetches screenshots using `?platform=iphone` and `?platform=ipad` URL parameters
  - Ensures both iPhone and iPad screenshots are captured for apps that support both devices
  - Automatically makes additional requests to platform-specific URLs
  - Works with apps like XIVI that have both device types in a generic "Screenshots" section

### Fixed
- iPad screenshots not being extracted for apps with generic "Screenshots" sections
- CombinedExtractor now properly merges iPad screenshots from web scraping results
- Screenshot extraction logic simplified to work with platform-specific pages

### Changed
- Renamed test file from `test_generic_screenshots_section.py` to `test_platform_specific_screenshots.py` to better reflect functionality

## [0.1.11] - 2025-08-06

### Fixed
- **Screenshot Extraction**: Fixed extraction for apps with generic "Screenshots" sections
  - Apps like XIVI (id6503696206) that only have "Screenshots" heading now properly extract images
  - Previously only worked with explicit "iPhone Screenshots" sections
  - Added detection for generic screenshot sections while avoiding iPad screenshot mixing
  - Added comprehensive test coverage for this scenario

## [0.1.10] - 2025-08-05

### Added
- **Screenshot Validation Tests**:
  - Comprehensive test suite for iPhone and iPad screenshot validation
  - ScreenshotValidator class to check image dimensions
  - Downloads and verifies actual image resolutions match device types
  - Tests for apps with both device types, iPhone-only apps, and batch validation
  - Pillow dependency added to dev requirements for image processing

### Improved
- **Screenshot Extraction**:
  - iTunes API now extracts both iPhone and iPad screenshots separately (`ipad_screenshots` field)
  - Web scraper can differentiate between "iPhone Screenshots" and "iPad Screenshots" sections
  - Device categorization based on image dimensions and aspect ratios

### Fixed
- ExtendedAppMetadata initialization now includes all required fields from iTunes API
- Added missing fields: developer_url, initial_release_date, rating counts for current version

## [0.1.9] - 2025-08-05

### Added
- **Developer Experience Improvements**:
  - `dev-setup.sh` - One-command development environment setup
  - `DEVELOPMENT.md` - Comprehensive development guide explaining Python packaging best practices
  - `Makefile` - Common development tasks (test, lint, format, clean, etc.)
  - `examples/basic_usage.py` - Working example demonstrating package usage
- **Documentation**:
  - Detailed explanation of why we install our own package during development
  - Troubleshooting guide for common issues
  - Clear workflow instructions for contributors

### Improved
- **Field Documentation**: README now documents all 50+ available fields with descriptions
- **Development Setup**: Clear instructions for virtual environments and editable installs

## [0.1.8] - 2025-08-05

### Fixed
- Added proper type guards in IAP extraction to fix mypy errors
- **Critical**: Publish workflow now requires all tests to pass before releasing to PyPI
  - Prevents broken releases from being published
  - Tests run on Python 3.11, 3.12, and 3.13
- **Screenshot extraction** now works for apps without iTunes API screenshots
  - Updated web scraper to handle new HTML structure with `<picture>` elements
  - Extracts highest quality PNG URLs from srcset attributes
  - Falls back to WebP if PNG not available

### Added
- Added `types-beautifulsoup4` to development dependencies for consistent type checking

### Security
- Releases are now gated by comprehensive test suite including:
  - Black formatting checks
  - isort import ordering
  - flake8 linting
  - mypy type checking
  - pytest unit and integration tests

## [0.1.7] - 2025-08-05

### Changed
- **BREAKING**: Removed `CombinedAppStoreScraper` class - use `CombinedExtractor` instead
  - Added backward compatibility alias: `CombinedAppStoreScraper = CombinedExtractor`
  - All functionality has been preserved and enhanced
- Consolidated all combined extraction logic into the WBS-compliant `CombinedExtractor`
- **Web scraping is now truly performed by default** - removed "smart" logic that could skip web scraping

### Improved
- **Language extraction** now supports new App Store HTML structure (dt/dd tags)
- **IAP extraction** improved to handle both old and new HTML formats
- IAP extraction now works regardless of the boolean flag value
- Added automatic language code generation from language names (60+ languages supported)

### Fixed
- Fixed issue where web scraping could be skipped even when `skip_web_scraping=False`
- Language extraction now correctly handles new HTML structure with dt/dd tags
- IAP extraction now supports both concatenated format and separate span elements

## [0.1.6] - 2025-08-05

### Changed
- Aligned pre-commit hooks with CI/CD pipeline configuration for consistency

### Added
- Synchronous wrapper methods for easier migration:
  - `fetch()` - Single app extraction with synchronous interface
  - `fetch_batch()` - Multiple app extraction with synchronous interface
- Support for extraction modes:
  - iTunes-only mode (fast) via `skip_web_scraping=True`
  - Combined mode (complete) via `skip_web_scraping=False`
- Comprehensive unit tests for `CombinedExtractor`
- Integration tests that verify real App Store API calls

### Fixed
- Fixed all mypy type errors in support link extraction
- Added proper type guards for BeautifulSoup Tag objects
- Fixed import errors for `DataSource` and `InAppPurchase` models
- Corrected asyncio event loop handling in tests

### Improved
- Enhanced type safety with full mypy compliance
- Increased test coverage to 71%
- Better error messages for extraction failures

## [0.1.5] - 2025-08-04

### Fixed
- Fixed version string in package (`__version__`) to match PyPI version

## [0.1.4] - 2025-08-04

### Added
- **In-App Purchase Details Extraction** - Extract complete list of IAP items with names and prices
  - Automatically detects IAP types (subscriptions, consumables, etc.)
  - Handles concatenated text format from App Store HTML
  - Available via `in_app_purchase_list` field (list of dictionaries)

- **Support Links Extraction** - Extract all support-related URLs from the Information section
  - App Support URL (`app_support_url`)
  - Privacy Policy URL (`privacy_policy_url`)
  - Developer Website URL (`developer_website_url`)
  - All three fields require web scraping (marked as "WEB ONLY")

### Changed
- Enhanced IAP detection logic to handle various HTML structures
- Improved web scraping selectors for better reliability

### Fixed
- In-app purchases detection now correctly identifies apps with IAPs
- Fixed regex patterns to handle concatenated IAP text (e.g., "Monthly$12.99")

## [0.1.3] - 2025-07-29

### Changed
- Removed `settings.py` as it contained mostly web API configurations not needed for standalone package
- Removed `pydantic-settings` dependency to reduce package dependencies
- Simplified test configuration

### Fixed
- Fixed test configuration to work without settings module

## [0.1.2] - 2025-07-29

### Fixed
- Fixed PyPI publishing workflow authentication

## [0.1.1] - 2025-07-29

### Fixed
- Updated GitHub Actions workflows to v4 to fix deprecation warnings
- Fixed PyPI trusted publishing configuration

## [0.1.0] - 2025-07-29

### Added
- Initial release of the standalone package
- Core App Store metadata extraction functionality
- iTunes API integration for fast metadata retrieval
- Web scraping for comprehensive data extraction
- WBS (What-Boundaries-Success) framework for validation
- Command-line interface with multiple commands
- Async support for concurrent operations
- Rate limiting and caching mechanisms
- Support for multiple extraction modes (fast, complete, smart)
