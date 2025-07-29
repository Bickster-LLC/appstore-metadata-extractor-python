# Apple App Store Metadata Extractor

[![PyPI version](https://badge.fury.io/py/apple-appstore-metadata-extractor.svg)](https://badge.fury.io/py/apple-appstore-metadata-extractor)
[![Python Support](https://img.shields.io/pypi/pyversions/apple-appstore-metadata-extractor.svg)](https://pypi.org/project/apple-appstore-metadata-extractor/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Extract and monitor metadata from Apple App Store applications with ease.

## Features

- 📱 **Extract comprehensive app metadata** - title, description, version, ratings, and more
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

```bash
# Clone the repository
git clone https://github.com/yourusername/appstore-metadata-extractor-python.git
cd appstore-metadata-extractor-python

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
black src tests
isort src tests
flake8 src tests
mypy src
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
