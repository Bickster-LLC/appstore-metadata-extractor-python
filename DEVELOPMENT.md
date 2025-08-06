# Development Guide

This guide will help you set up your development environment and understand the development workflow for the appstore-metadata-extractor project.

## Quick Start

We provide a one-command setup script:

```bash
./dev-setup.sh
```

This script will:
- Create a virtual environment
- Install the package in editable mode
- Install all development dependencies
- Set up pre-commit hooks
- Clear any caches

## Manual Setup

If you prefer to set up manually:

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/appstore-metadata-extractor-python.git
cd appstore-metadata-extractor-python
```

### 2. Create a Virtual Environment

**Always use a virtual environment** to isolate dependencies:

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install in Development Mode

Install the package in "editable" mode with development dependencies:

```bash
pip install -e ".[dev]"
```

**What does `-e` mean?**
- `-e` stands for "editable" or "development mode"
- It creates a link to your source code instead of copying files
- Changes to the source code are immediately reflected without reinstalling
- This is how you can develop and test at the same time

### 4. Install Pre-commit Hooks

```bash
pre-commit install
```

This ensures code quality checks run before each commit.

## Understanding the Setup

### Why Install Your Own Package?

This is a common question! Here's why we do it:

1. **Test Real Usage**: You test the same import paths your users will use
   ```python
   # This is what users will write:
   from appstore_metadata_extractor import CombinedExtractor
   ```

2. **Dependency Management**: Installing ensures all dependencies from `pyproject.toml` are available

3. **CLI Tools**: The command-line tool `appstore-extractor` only works after installation

4. **Package Validation**: Helps catch packaging issues early

### Common Issues and Solutions

#### "My changes aren't reflected!"

If you modify code but changes don't appear:

1. **Check you're in the virtual environment**:
   ```bash
   which python  # Should show: /path/to/project/venv/bin/python
   ```

2. **Reinstall in editable mode**:
   ```bash
   pip install -e .
   ```

3. **Clear Python cache**:
   ```bash
   find . -type d -name "__pycache__" -exec rm -rf {} +
   ```

#### "Import errors when running scripts"

Make sure you're either:
- In the virtual environment with the package installed
- Or running from the project root with `python -m`:
  ```bash
  python -m appstore_metadata_extractor.cli extract URL
  ```

## Development Workflow

### 1. Before Starting Work

```bash
# Activate virtual environment
source venv/bin/activate

# Pull latest changes
git pull

# Update dependencies
pip install -e ".[dev]"
```

### 2. Making Changes

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes

3. Test your changes:
   ```bash
   # Run specific test
   pytest tests/test_specific.py

   # Run all tests
   pytest

   # Run with coverage
   pytest --cov=appstore_metadata_extractor
   ```

### 3. Code Quality

Before committing, ensure code quality:

```bash
# Format code
black src tests

# Sort imports
isort src tests

# Check linting
flake8 src tests

# Type checking
mypy src
```

Or let pre-commit do it automatically:
```bash
pre-commit run --all-files
```

### 4. Testing Changes

Test the actual package usage:

```python
# test_script.py
from appstore_metadata_extractor import CombinedExtractor, WBSConfig

config = WBSConfig()
extractor = CombinedExtractor(config)

url = "https://apps.apple.com/us/app/example/id123456"
result = extractor.fetch(url)
print(f"App: {result.name}")
```

Run it:
```bash
python test_script.py
```

### 5. CLI Testing

Test the command-line interface:

```bash
# Should work after pip install -e .
appstore-extractor extract https://apps.apple.com/us/app/example/id123456
```

## Project Structure

```
appstore-metadata-extractor-python/
├── src/
│   └── appstore_metadata_extractor/
│       ├── __init__.py          # Package initialization
│       ├── core/                # Core functionality
│       │   ├── extractors.py    # Main extractor classes
│       │   ├── models.py        # Pydantic models
│       │   └── cache.py         # Caching logic
│       └── cli/                 # Command-line interface
├── tests/                       # Test files
├── pyproject.toml              # Package configuration
├── requirements.txt            # Production dependencies
├── requirements-dev.txt        # Development dependencies
└── dev-setup.sh               # Development setup script
```

## Tips for Effective Development

1. **Use the REPL for Testing**:
   ```bash
   python
   >>> from appstore_metadata_extractor import CombinedExtractor
   >>> # Test your changes interactively
   ```

2. **Enable Debug Logging**:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

3. **Test with Different Apps**:
   - Apps with/without IAPs
   - Apps with/without screenshots in iTunes API
   - Apps in different categories
   - Non-English apps

4. **Monitor API Rate Limits**:
   - iTunes API: 20 requests/minute
   - Web scraping: Respect delays

## Troubleshooting

### Virtual Environment Issues

If `source venv/bin/activate` doesn't work:
- On Windows: `venv\Scripts\activate`
- On fish shell: `source venv/bin/activate.fish`
- Using conda: `conda activate ./venv`

### Import Issues

If imports fail after setup:
```bash
# Check package is installed
pip list | grep appstore-metadata-extractor

# Check you're in the right environment
which python

# Reinstall
pip install -e .
```

### Cache Issues

If you're getting stale data:
```python
from appstore_metadata_extractor.core import CombinedExtractor, WBSConfig

extractor = CombinedExtractor(WBSConfig())
extractor.cache.clear()  # Clear cache
```

## Contributing

1. Fork the repository
2. Create your feature branch
3. Make changes following the code style
4. Ensure all tests pass
5. Submit a pull request

## Questions?

If you have questions about development:
1. Check this guide first
2. Look at existing code for examples
3. Open an issue for discussion
