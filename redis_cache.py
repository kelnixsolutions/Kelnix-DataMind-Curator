"""
Optional Redis caching layer for query results and connector state.
Falls back to in-memory dict if Redis is not available.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any

_redis_client = None
_memory_cache: dict[str, str] = {}
_use_redis = False


def _get_redis():
    global _redis_client, _use_redis
    if _redis_client is not None:
        return _redis_client

    redis_url = os.environ.get("REDIS_URL", "")
    if not redis_url:
        _use_redis = False
        return None

    try:
        import redis
        _redis_client = redis.from_url(redis_url, decode_responses=True)
        _redis_client.ping()
        _use_redis = True
        return _redis_client
    except Exception:
        _use_redis = False
        return None


def cache_key(prefix: str, *parts: str) -> str:
    raw = "|".join(parts)
    hashed = hashlib.md5(raw.encode()).hexdigest()[:12]
    return f"dm:{prefix}:{hashed}"


def get(key: str) -> Any | None:
    r = _get_redis()
    if r and _use_redis:
        val = r.get(key)
        if val:
            return json.loads(val)
    else:
        val = _memory_cache.get(key)
        if val:
            return json.loads(val)
    return None


def set(key: str, value: Any, ttl: int = 300) -> None:
    serialized = json.dumps(value, default=str)
    r = _get_redis()
    if r and _use_redis:
        r.setex(key, ttl, serialized)
    else:
        _memory_cache[key] = serialized


def delete(key: str) -> None:
    r = _get_redis()
    if r and _use_redis:
        r.delete(key)
    else:
        _memory_cache.pop(key, None)


def flush_prefix(prefix: str) -> int:
    """Delete all keys matching a prefix."""
    r = _get_redis()
    if r and _use_redis:
        keys = r.keys(f"dm:{prefix}:*")
        if keys:
            r.delete(*keys)
            return len(keys)
    else:
        to_delete = [k for k in _memory_cache if k.startswith(f"dm:{prefix}:")]
        for k in to_delete:
            del _memory_cache[k]
        return len(to_delete)
    return 0
