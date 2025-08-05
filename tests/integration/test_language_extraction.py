"""Integration tests for language extraction functionality."""

import asyncio

import pytest

from appstore_metadata_extractor.core import CombinedExtractor, WBSConfig


@pytest.mark.asyncio
async def test_chatgpt_language_extraction():
    """Test language extraction with ChatGPT app which has multiple languages."""
    # Create extractor with default WBS config
    wbs_config = WBSConfig()
    extractor = CombinedExtractor(wbs_config)

    # ChatGPT app URL - known to have multiple language support
    url = "https://apps.apple.com/cv/app/chatgpt/id6448311069"

    print("\nTesting Language Extraction with ChatGPT")
    print("=" * 50)

    # Test 1: iTunes API only (should have empty language lists)
    print("\n1. iTunes API only mode:")
    print("-" * 30)
    result = await extractor.fetch_combined(url, skip_web_scraping=True)

    if result.success:
        metadata = result.app_metadata
        print(f"✓ App: {metadata.name}")
        print(f"✓ Bundle ID: {metadata.bundle_id}")
        print(f"✗ Languages from iTunes API: {len(metadata.languages)} (expected: 0)")
        print(
            f"✗ Language codes from iTunes API: {len(metadata.language_codes)} (expected: 0)"
        )

        # iTunes API should not provide language data
        assert (
            len(metadata.languages) == 0
        ), "iTunes API should not provide language data"
        assert (
            len(metadata.language_codes) == 0
        ), "iTunes API should not provide language codes"
    else:
        pytest.fail(f"iTunes API extraction failed: {result.error}")

    # Test 2: Combined mode with web scraping (should have language data)
    print("\n\n2. Combined mode (with web scraping):")
    print("-" * 30)
    result = await extractor.fetch_combined(url, skip_web_scraping=False)

    if result.success:
        metadata = result.app_metadata
        print(f"✓ App: {metadata.name}")
        print(f"✓ Languages found: {len(metadata.languages)}")
        print(f"✓ Language codes found: {len(metadata.language_codes)}")

        # ChatGPT should support multiple languages
        assert len(metadata.languages) > 1, "ChatGPT should support multiple languages"
        assert (
            len(metadata.language_codes) > 1
        ), "ChatGPT should have multiple language codes"

        # Show first 10 languages
        print("\nFirst 10 supported languages:")
        for i, lang in enumerate(metadata.languages[:10]):
            code = (
                metadata.language_codes[i]
                if i < len(metadata.language_codes)
                else "N/A"
            )
            print(f"  {i+1}. {lang} ({code})")

        if len(metadata.languages) > 10:
            print(f"  ... and {len(metadata.languages) - 10} more languages")

        # Verify common languages are present
        common_languages = [
            "English",
            "Spanish",
            "French",
            "German",
            "Japanese",
            "Chinese",
        ]
        found_languages = set(metadata.languages)

        print("\nChecking for common languages:")
        for lang in common_languages:
            if lang in found_languages:
                print(f"  ✓ {lang}")
            else:
                # Some language names might vary, so we'll be flexible
                print(f"  ? {lang} (might have different naming)")

        # At minimum, English should be supported
        assert any(
            "English" in lang or "EN" in lang for lang in metadata.languages
        ), "English should be in supported languages"

        print("\n✓ Language extraction successful!")
        print(f"  Total languages: {len(metadata.languages)}")
        print(f"  Total language codes: {len(metadata.language_codes)}")

    else:
        pytest.fail(f"Combined extraction failed: {result.error}")


def test_synchronous_language_extraction():
    """Test synchronous wrapper for language extraction."""
    wbs_config = WBSConfig()
    extractor = CombinedExtractor(wbs_config)

    url = "https://apps.apple.com/cv/app/chatgpt/id6448311069"

    print("\n\n3. Testing synchronous language extraction:")
    print("-" * 50)

    # Test with web scraping enabled (default)
    metadata = extractor.fetch(url, skip_web_scraping=False)

    print(f"✓ App: {metadata.name}")
    print(f"✓ Bundle ID: {metadata.bundle_id}")
    print(f"✓ Languages: {len(metadata.languages)}")

    # Verify we got language data
    assert len(metadata.languages) > 1, "Should extract multiple languages"
    assert len(metadata.language_codes) > 1, "Should extract multiple language codes"

    # Language codes should match languages count (or be close)
    assert (
        abs(len(metadata.languages) - len(metadata.language_codes)) <= 1
    ), "Language codes and languages count should match"

    print("✓ Synchronous language extraction successful!")


@pytest.mark.asyncio
async def test_language_extraction_consistency():
    """Test that language extraction is consistent between calls."""
    wbs_config = WBSConfig()
    extractor = CombinedExtractor(wbs_config)

    url = "https://apps.apple.com/cv/app/chatgpt/id6448311069"

    print("\n\n4. Testing language extraction consistency:")
    print("-" * 50)

    # Extract twice to check consistency
    result1 = await extractor.fetch_combined(url, skip_web_scraping=False)
    result2 = await extractor.fetch_combined(url, skip_web_scraping=False)

    if result1.success and result2.success:
        languages1 = set(result1.app_metadata.languages)
        languages2 = set(result2.app_metadata.languages)

        # Languages should be consistent between calls
        assert languages1 == languages2, "Languages should be consistent between calls"

        print("✓ Language extraction is consistent")
        print(f"  Languages count: {len(languages1)}")
        print("  Both extractions returned the same language list")
    else:
        pytest.fail("One or both extractions failed")


@pytest.mark.asyncio
async def test_chatgpt_iap_extraction():
    """Test IAP extraction with ChatGPT app which has known IAPs."""
    wbs_config = WBSConfig()
    extractor = CombinedExtractor(wbs_config)

    # Clear any cached data to force fresh extraction
    extractor.cache.clear()

    url = "https://apps.apple.com/us/app/chatgpt/id6448311069"

    print("\n\n5. Testing IAP extraction with ChatGPT:")
    print("-" * 50)

    result = await extractor.fetch_combined(url, skip_web_scraping=False)

    if result.success:
        metadata = result.app_metadata
        print(f"✓ App: {metadata.name}")
        print(f"✓ Has IAPs: {metadata.in_app_purchases}")

        if metadata.in_app_purchase_list and len(metadata.in_app_purchase_list) > 0:
            print(f"✓ Found {len(metadata.in_app_purchase_list)} IAP items:")
            for iap in metadata.in_app_purchase_list[:5]:  # Show first 5
                print(f"  - {iap['name']}: {iap['price']}")
                if "type" in iap:
                    print(f"    Type: {iap['type']}")

            # Verify we got actual IAP data
            assert len(metadata.in_app_purchase_list) > 0, "Should find IAP items"
            assert metadata.in_app_purchases is True, "Should have IAPs flag set"

            # Check that IAP items have required fields
            first_iap = metadata.in_app_purchase_list[0]
            assert "name" in first_iap and first_iap["name"], "IAP should have name"
            assert "price" in first_iap and first_iap["price"], "IAP should have price"

            print("\n✓ IAP extraction successful!")
        else:
            pytest.fail("Expected to find IAP items for ChatGPT")
    else:
        pytest.fail(f"Extraction failed: {result.error}")


if __name__ == "__main__":
    # Run the async tests
    asyncio.run(test_chatgpt_language_extraction())
    asyncio.run(test_language_extraction_consistency())
    asyncio.run(test_chatgpt_iap_extraction())

    # Run the sync test
    test_synchronous_language_extraction()
