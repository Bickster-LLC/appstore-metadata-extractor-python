# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2025-07-29

### Fixed
- Fixed PyPI publishing workflow to use API token authentication
- Removed trusted publishing configuration that was causing authentication failures

## [0.1.1] - 2025-07-29

### Fixed
- Attempted fix for PyPI publishing (incomplete)

## [0.1.0] - 2025-07-29

### Added
- Initial release of appstore-metadata-extractor
- Core functionality extracted from the full-stack project
- iTunes API integration for basic metadata
- Web scraping for extended metadata
- Combined extraction mode for comprehensive data
- CLI with commands: extract, extract-batch, watch
- Async/concurrent processing support
- Rate limiting and caching
- Rich terminal output
- Comprehensive error handling and retries
- Type hints throughout the codebase
- Full test suite with >80% coverage

### Features
- Extract app metadata from Apple App Store
- Monitor apps for version changes
- Batch processing with concurrent requests
- Multiple output formats (JSON, pretty-print)
- Configurable extraction modes
- WBS (What-Boundaries-Success) framework compliance

[0.1.0]: https://github.com/yourusername/appstore-metadata-extractor-python/releases/tag/v0.1.0
