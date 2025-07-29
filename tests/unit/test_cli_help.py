#!/usr/bin/env python3
"""Test the refactored CLI with core modules."""

import subprocess
import sys


def test_cli_help():
    """Test CLI help command."""
    print("Testing CLI help...")
    result = subprocess.run(
        [sys.executable, "-m", "appstore_metadata_extractor.cli", "--help"],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    print(f"Return code: {result.returncode}")
    assert result.returncode == 0


def test_cli_extract_help():
    """Test extract command help."""
    print("\nTesting extract command help...")
    result = subprocess.run(
        [sys.executable, "-m", "appstore_metadata_extractor.cli", "extract", "--help"],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    print(f"Return code: {result.returncode}")
    assert result.returncode == 0


def test_cli_validate_help():
    """Test validate command help."""
    print("\nTesting validate command help...")
    result = subprocess.run(
        [sys.executable, "-m", "appstore_metadata_extractor.cli", "validate", "--help"],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    print(f"Return code: {result.returncode}")
    assert result.returncode == 0


def main():
    """Run all tests."""
    tests = [
        test_cli_help,
        test_cli_extract_help,
        test_cli_validate_help,
    ]

    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
                print(f"✓ {test.__name__} passed")
            else:
                print(f"✗ {test.__name__} failed")
        except Exception as e:
            print(f"✗ {test.__name__} error: {e}")

    print(f"\nPassed {passed}/{len(tests)} tests")
    return passed == len(tests)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
