# Publishing to PyPI

This guide covers how to publish the `appstore-metadata-extractor` package to PyPI.

## Prerequisites

1. PyPI account: https://pypi.org/account/register/
2. Test PyPI account (optional): https://test.pypi.org/account/register/
3. Install tools:
   ```bash
   pip install build twine
   ```

## First-Time Setup

### 1. Configure PyPI Token

1. Go to https://pypi.org/manage/account/token/
2. Create a new API token with scope "Entire account"
3. Save the token securely

### 2. Configure GitHub Repository

1. Go to your repository settings on GitHub
2. Navigate to Settings > Secrets and variables > Actions
3. Add a new secret named `PYPI_API_TOKEN` with your token

### 3. Enable Trusted Publishing (Recommended)

Instead of using tokens, you can use PyPI's trusted publishing:

1. Go to https://pypi.org/manage/projects/
2. Create the project name `appstore-metadata-extractor`
3. Go to Publishing settings
4. Add GitHub as a trusted publisher:
   - Owner: yourusername
   - Repository: appstore-metadata-extractor-python
   - Workflow: publish.yml
   - Environment: release

## Manual Publishing

### 1. Build the Package

```bash
# Clean previous builds
rm -rf dist/ build/ *.egg-info

# Build source and wheel distributions
python -m build
```

### 2. Test with TestPyPI (Optional)

```bash
# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Test installation
pip install --index-url https://test.pypi.org/simple/ appstore-metadata-extractor
```

### 3. Upload to PyPI

```bash
# Check distributions
twine check dist/*

# Upload to PyPI
twine upload dist/*
```

## Automated Publishing with GitHub Actions

The repository includes a GitHub Actions workflow that automatically publishes to PyPI when you create a release.

### Steps:

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Commit and push changes
4. Create a new release on GitHub:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```
5. Go to GitHub > Releases > Create new release
6. Select the tag and publish the release
7. GitHub Actions will automatically build and publish to PyPI

## Version Management

Follow semantic versioning:
- MAJOR.MINOR.PATCH (e.g., 1.2.3)
- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes

## Post-Publishing Checklist

- [ ] Verify package on PyPI: https://pypi.org/project/appstore-metadata-extractor/
- [ ] Test installation: `pip install appstore-metadata-extractor`
- [ ] Update documentation links
- [ ] Announce release (if applicable)

## Troubleshooting

### "Package already exists" Error
- The package name is already taken on PyPI
- Choose a different name or request ownership transfer

### Authentication Failed
- Verify your API token is correct
- Check token permissions
- Ensure you're using the correct repository URL

### Build Errors
- Ensure all dependencies are listed in pyproject.toml
- Check for syntax errors in Python files
- Run tests before building