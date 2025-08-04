# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
