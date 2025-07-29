"""Cache management for AppStore Metadata Extractor."""

import hashlib
import json
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional

from .exceptions import RateLimitError


class CacheManager:
    """Simple in-memory cache with TTL support."""

    def __init__(self, default_ttl: int = 300):
        """
        Initialize cache manager.

        Args:
            default_ttl: Default time-to-live in seconds (5 minutes)
        """
        self._storage: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl

        # Restore cache attribute for backward compatibility
        self.cache = self._storage

    def _generate_key(self, prefix: str, params: Dict[str, Any]) -> str:
        """Generate cache key from prefix and parameters."""
        # Sort params for consistent keys
        sorted_params = json.dumps(params, sort_keys=True)
        hash_digest = hashlib.md5(sorted_params.encode()).hexdigest()[:8]
        return f"{prefix}:{hash_digest}"

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if key not in self._storage:
            return None

        entry = self._storage[key]
        if time.time() > entry["expires_at"]:
            # Expired, remove it
            del self._storage[key]
            return None

        return entry["value"]

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with TTL."""
        ttl = ttl or self.default_ttl
        self._storage[key] = {
            "value": value,
            "expires_at": time.time() + ttl,
            "created_at": time.time(),
        }

    def delete(self, key: str) -> None:
        """Delete key from cache."""
        self._storage.pop(key, None)

    def remove(self, key: str) -> None:
        """Remove key from cache (alias for delete)."""
        self.delete(key)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._storage.clear()

    def get_age(self, key: str) -> Optional[float]:
        """Get age of cache entry in seconds."""
        if key not in self._storage:
            return None
        return float(time.time() - self._storage[key]["created_at"])

    def cleanup_expired(self) -> int:
        """Remove expired entries and return count removed."""
        current_time = time.time()
        expired_keys = [
            key
            for key, entry in self._storage.items()
            if current_time > entry["expires_at"]
        ]

        for key in expired_keys:
            del self._storage[key]

        return len(expired_keys)

    def size(self) -> int:
        """Return the number of items in cache."""
        return len(self._storage)

    def cached(self, prefix: str = "", ttl: Optional[int] = None) -> Callable:
        """
        Decorator method for caching function results using this cache instance.

        Args:
            prefix: Prefix for cache keys
            ttl: Time-to-live in seconds (uses default_ttl if not specified)
        """
        cache_ttl = ttl or self.default_ttl

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                # Generate cache key
                cache_key = self._generate_key(
                    prefix or func.__name__, {"args": args, "kwargs": kwargs}
                )

                # Check cache
                cached_value = self.get(cache_key)
                if cached_value is not None:
                    return cached_value

                # Call function
                result = func(*args, **kwargs)

                # Cache result
                self.set(cache_key, result, cache_ttl)

                return result

            return wrapper

        return decorator


def cache(ttl: int = 300, key_prefix: str = "") -> Callable:
    """
    Decorator for caching function results.

    Args:
        ttl: Time-to-live in seconds
        key_prefix: Prefix for cache keys
    """

    def decorator(func: Callable) -> Callable:
        cache_manager = CacheManager(default_ttl=ttl)

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Generate cache key
            cache_key = cache_manager._generate_key(
                key_prefix or func.__name__, {"args": args, "kwargs": kwargs}
            )

            # Check cache
            cached_value = cache_manager.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Call function
            result = await func(*args, **kwargs)

            # Cache result
            cache_manager.set(cache_key, result, ttl)

            return result

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Generate cache key
            cache_key = cache_manager._generate_key(
                key_prefix or func.__name__, {"args": args, "kwargs": kwargs}
            )

            # Check cache
            cached_value = cache_manager.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Call function
            result = func(*args, **kwargs)

            # Cache result
            cache_manager.set(cache_key, result, ttl)

            return result

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            # Store cache_manager as attribute of wrapper
            setattr(async_wrapper, "cache_manager", cache_manager)
            return async_wrapper
        else:
            # Store cache_manager as attribute of wrapper
            setattr(sync_wrapper, "cache_manager", cache_manager)
            return sync_wrapper

    return decorator


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self) -> None:
        self.buckets: Dict[str, Dict[str, Any]] = {}

    def configure(self, service: str, max_requests: int, time_window: int = 60) -> None:
        """
        Configure rate limit for a service.

        Args:
            service: Service identifier (e.g., "itunes_api")
            max_requests: Maximum requests allowed
            time_window: Time window in seconds (default: 60)
        """
        self.buckets[service] = {
            "max_requests": max_requests,
            "time_window": time_window,
            "requests": [],
            "tokens": max_requests,
        }

    def check(self, service: str) -> bool:
        """Check if request is allowed."""
        if service not in self.buckets:
            return True  # No limit configured

        bucket = self.buckets[service]
        current_time = time.time()

        # Remove old requests outside time window
        bucket["requests"] = [
            req_time
            for req_time in bucket["requests"]
            if current_time - req_time < bucket["time_window"]
        ]

        # Check if under limit
        return bool(len(bucket["requests"]) < bucket["max_requests"])

    def consume(self, service: str) -> None:
        """Consume a token for the service."""
        if service not in self.buckets:
            return  # No limit configured

        if not self.check(service):
            raise RateLimitError(
                service=service, retry_after=self.get_retry_after(service)
            )

        bucket = self.buckets[service]
        bucket["requests"].append(time.time())

    def get_retry_after(self, service: str) -> Optional[int]:
        """Get seconds until next request is allowed."""
        if service not in self.buckets:
            return None

        bucket = self.buckets[service]
        if len(bucket["requests"]) == 0:
            return None

        # Find oldest request
        oldest_request = min(bucket["requests"])
        retry_after = bucket["time_window"] - (time.time() - oldest_request)

        return max(0, int(retry_after))

    def get_remaining(self, service: str) -> int:
        """Get remaining requests allowed."""
        if service not in self.buckets:
            return -1  # Unlimited

        bucket = self.buckets[service]
        current_time = time.time()

        # Count requests in current window
        active_requests = sum(
            1
            for req_time in bucket["requests"]
            if current_time - req_time < bucket["time_window"]
        )

        return int(max(0, bucket["max_requests"] - active_requests))

    def reset(self, service: str) -> None:
        """Reset rate limit for service."""
        if service in self.buckets:
            self.buckets[service]["requests"] = []


# Global instances
_cache_manager = CacheManager()
_rate_limiter = RateLimiter()


def get_cache_manager() -> CacheManager:
    """Get global cache manager instance."""
    return _cache_manager


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance."""
    return _rate_limiter
