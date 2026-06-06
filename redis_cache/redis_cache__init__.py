"""
redis_cache/
────────────
Redis-backed caching layer for research results.
"""
from redis_cache.cache import get_cached_result, cache_result, invalidate, cache_health

__all__ = ["get_cached_result", "cache_result", "invalidate", "cache_health"]
