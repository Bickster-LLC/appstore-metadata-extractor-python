"""Unit tests for the cache module."""

import time

import pytest

from appstore_metadata_extractor.core.cache import CacheManager, RateLimiter
from appstore_metadata_extractor.core.exceptions import RateLimitError


class TestCacheManager:
    """Test CacheManager class."""

    @pytest.fixture
    def cache(self):
        """Create a CacheManager instance."""
        return CacheManager(default_ttl=300)

    def test_init(self, cache):
        """Test cache initialization."""
        assert cache.default_ttl == 300
        assert cache.cache == {}

    def test_generate_key(self, cache):
        """Test cache key generation."""
        key1 = cache._generate_key("test", {"param1": "value1", "param2": "value2"})
        key2 = cache._generate_key("test", {"param2": "value2", "param1": "value1"})
        key3 = cache._generate_key("test", {"param1": "value1", "param2": "value3"})

        # Same params in different order should generate same key
        assert key1 == key2
        # Different params should generate different key
        assert key1 != key3
        # Key should have prefix
        assert key1.startswith("test:")

    def test_set_and_get(self, cache):
        """Test setting and getting values from cache."""
        cache.set("test_key", {"data": "test_value"})

        result = cache.get("test_key")
        assert result == {"data": "test_value"}

    def test_get_nonexistent(self, cache):
        """Test getting non-existent key."""
        result = cache.get("nonexistent_key")
        assert result is None

    def test_ttl_expiration(self, cache):
        """Test TTL expiration."""
        # Set with 1 second TTL
        cache.set("expire_key", "test_value", ttl=1)

        # Should be available immediately
        assert cache.get("expire_key") == "test_value"

        # Wait for expiration
        time.sleep(1.1)

        # Should be expired
        assert cache.get("expire_key") is None

    def test_clear(self, cache):
        """Test clearing cache."""
        # Add multiple items
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # Verify items exist
        assert len(cache.cache) == 3

        # Clear cache
        cache.clear()

        # Verify cache is empty
        assert cache.cache == {}

    def test_remove(self, cache):
        """Test removing specific key."""
        # Add items
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        # Remove one
        cache.remove("key1")

        # Verify removal
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

    def test_size(self, cache):
        """Test getting cache size."""
        assert cache.size() == 0

        cache.set("key1", "value1")
        cache.set("key2", "value2")

        assert cache.size() == 2

    def test_cache_decorator(self, cache):
        """Test cache decorator functionality."""
        call_count = 0

        @cache.cached(prefix="test_func")
        def expensive_function(param1, param2):
            nonlocal call_count
            call_count += 1
            return f"{param1}-{param2}-result"

        # First call should execute function
        result1 = expensive_function("a", "b")
        assert result1 == "a-b-result"
        assert call_count == 1

        # Second call with same params should use cache
        result2 = expensive_function("a", "b")
        assert result2 == "a-b-result"
        assert call_count == 1  # Function not called again

        # Different params should execute function
        result3 = expensive_function("c", "d")
        assert result3 == "c-d-result"
        assert call_count == 2

    def test_cache_decorator_with_ttl(self, cache):
        """Test cache decorator with custom TTL."""

        @cache.cached(prefix="short_ttl", ttl=1)
        def short_lived_function():
            return time.time()

        # First call
        time1 = short_lived_function()

        # Immediate second call should return cached value
        time2 = short_lived_function()
        assert time1 == time2

        # Wait for expiration
        time.sleep(1.1)

        # Should get new value
        time3 = short_lived_function()
        assert time3 > time1

    def test_cleanup_expired(self, cache):
        """Test cleanup of expired entries."""
        # Add items with different TTLs
        cache.set("expire1", "value1", ttl=1)
        cache.set("expire2", "value2", ttl=1)
        cache.set("keep", "value3", ttl=300)

        # Wait for some to expire
        time.sleep(1.1)

        # Access one expired key (should trigger cleanup)
        assert cache.get("expire1") is None

        # The expired entry should be removed from cache
        assert "expire1" not in cache.cache
        # Other expired entry still in cache until accessed
        assert "expire2" in cache.cache
        # Non-expired entry should remain
        assert "keep" in cache.cache


class TestRateLimiter:
    """Test RateLimiter class."""

    @pytest.fixture
    def rate_limiter(self):
        """Create a RateLimiter instance."""
        limiter = RateLimiter()
        limiter.configure("test_service", max_requests=60, time_window=60)
        limiter.configure("test_hour", max_requests=1000, time_window=3600)
        return limiter

    def test_init(self, rate_limiter):
        """Test rate limiter initialization."""
        assert "test_service" in rate_limiter.buckets
        assert rate_limiter.buckets["test_service"]["max_requests"] == 60
        assert rate_limiter.buckets["test_service"]["time_window"] == 60

    def test_consume(self, rate_limiter):
        """Test consuming tokens."""
        initial_count = len(rate_limiter.buckets["test_service"]["requests"])

        rate_limiter.consume("test_service")

        assert (
            len(rate_limiter.buckets["test_service"]["requests"]) == initial_count + 1
        )

    def test_cleanup_old_requests(self, rate_limiter):
        """Test cleanup of old requests."""
        # Add some old requests
        old_time = time.time() - 70  # Over a minute ago
        rate_limiter.buckets["test_service"]["requests"] = [
            old_time,
            old_time,
            time.time(),
        ]

        # Check will clean up old requests
        is_allowed = rate_limiter.check("test_service")

        # Should be allowed and only recent request should remain
        assert is_allowed
        assert (
            len(
                [
                    r
                    for r in rate_limiter.buckets["test_service"]["requests"]
                    if time.time() - r < 60
                ]
            )
            == 1
        )

    def test_check_within_limits(self, rate_limiter):
        """Test checking within rate limits."""
        # Should pass initially
        assert rate_limiter.check("test_service")

        # Add many requests but within limits
        for _ in range(50):
            rate_limiter.consume("test_service")

        # Should still pass (under 60/min limit)
        assert rate_limiter.check("test_service")

    def test_check_minute_limit_exceeded(self, rate_limiter):
        """Test minute rate limit exceeded."""
        # Add requests up to the minute limit
        current_time = time.time()
        rate_limiter.buckets["test_service"]["requests"] = [current_time] * 60

        # Next request should fail
        assert not rate_limiter.check("test_service")

        # Consuming should raise error
        with pytest.raises(RateLimitError):
            rate_limiter.consume("test_service")

    def test_check_hour_limit_exceeded(self, rate_limiter):
        """Test hour rate limit exceeded."""
        # Add requests up to the hour limit
        current_time = time.time()
        rate_limiter.buckets["test_hour"]["requests"] = [current_time] * 1000

        # Next request should fail
        assert not rate_limiter.check("test_hour")

        # Consuming should raise error
        with pytest.raises(RateLimitError):
            rate_limiter.consume("test_hour")

    def test_get_retry_after_no_wait(self, rate_limiter):
        """Test get_retry_after when no wait is needed."""
        # No requests, so no wait needed
        retry_after = rate_limiter.get_retry_after("test_service")
        assert retry_after is None

    def test_get_retry_after_with_wait(self, rate_limiter):
        """Test get_retry_after when wait is required."""
        # Add 60 requests in the last 30 seconds
        current_time = time.time()
        rate_limiter.buckets["test_service"]["requests"] = [current_time - 30] * 60

        # Should need to wait approximately 30 seconds
        retry_after = rate_limiter.get_retry_after("test_service")
        assert 28 <= retry_after <= 32

    def test_get_remaining(self, rate_limiter):
        """Test getting remaining requests."""
        # Should have full quota initially
        assert rate_limiter.get_remaining("test_service") == 60

        # Use some requests
        for _ in range(10):
            rate_limiter.consume("test_service")

        assert rate_limiter.get_remaining("test_service") == 50

        # Fill up the limit
        for _ in range(50):
            rate_limiter.consume("test_service")

        assert rate_limiter.get_remaining("test_service") == 0

    def test_unconfigured_service(self, rate_limiter):
        """Test unconfigured service behavior."""
        # Should allow requests for unconfigured services
        assert rate_limiter.check("unknown_service")
        rate_limiter.consume("unknown_service")  # Should not raise
        assert rate_limiter.get_remaining("unknown_service") == -1

    def test_reset(self, rate_limiter):
        """Test resetting rate limits."""
        # Add some requests
        for _ in range(25):
            rate_limiter.consume("test_service")

        assert len(rate_limiter.buckets["test_service"]["requests"]) == 25

        # Reset the service
        rate_limiter.reset("test_service")

        assert len(rate_limiter.buckets["test_service"]["requests"]) == 0
        assert rate_limiter.get_remaining("test_service") == 60

    def test_concurrent_requests(self, rate_limiter):
        """Test concurrent request handling."""
        import threading

        errors = []
        success_count = 0

        def make_request():
            nonlocal success_count
            try:
                rate_limiter.consume("test_service")
                success_count += 1
            except RateLimitError as e:
                errors.append(e)

        # Pre-fill with some requests
        for _ in range(55):
            rate_limiter.consume("test_service")

        # Try to make 10 concurrent requests
        threads = []
        for _ in range(10):
            t = threading.Thread(target=make_request)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Should have succeeded for some, failed for others
        assert success_count <= 5  # At most 5 should succeed (60 limit - 55 existing)
        assert len(errors) >= 5  # At least 5 should fail
