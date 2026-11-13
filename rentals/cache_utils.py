"""
Small helpers for the Redis cache of the property list.

How the cache works (simple version):
  * The property list is saved in Redis for 5 minutes.
  * The cache key contains a "version number".
  * When a property changes we raise the version number, so the old cached
    lists are never used again (they simply expire later).
"""
from django.core.cache import cache

VERSION_KEY = "properties:version"


def get_cache_version():
    """Current version number of the property list cache (starts at 1)."""
    return cache.get(VERSION_KEY, 1)


def bump_cache_version():
    """Call this whenever a property is created, changed or deleted."""
    try:
        cache.incr(VERSION_KEY)
    except ValueError:  # the key does not exist yet
        cache.set(VERSION_KEY, 2, timeout=None)
