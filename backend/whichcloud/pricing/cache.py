"""Redis in front of the price catalog.

The container has been running since the project started and nothing has
ever talked to it. infra/docker-compose.yml says why it exists -- "Redis
caches price lookups so the engine never re-queries a provider
mid-request" -- and the lookup path went straight to Postgres every time.

WHAT THIS IS AND IS NOT.
It is a read-through cache over `store.get_price` and the cheapest-match
queries. It is NOT a second source of truth: every value in it came from
Postgres, every key carries the ingest generation, and a cold cache
produces byte-identical answers to a warm one. That last property is
asserted rather than assumed, because a cache that changes an answer is
not a cache, it is a bug with a latency improvement.

WHY A TTL AT ALL, given prices barely move.
Not for freshness -- `prune_stale` and the ingest generation handle that.
For BOUNDED WRONGNESS. If an ingest ever fails to bump the generation,
the TTL puts a ceiling on how long a stale rate can be served, and a
ceiling measured in hours is a very different failure from one measured
in "until someone restarts it".

FAILING OPEN IS DELIBERATE.
Every operation here swallows connection errors and falls through to
Postgres. A pricing engine that cannot answer because its cache is down
is worse in every way than one that answers a little slower -- and Redis
being optional is what lets the whole thing run with no container at all.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from decimal import Decimal

#: Hours a cached rate may survive. See the module docstring: this bounds
#: how wrong a missed generation bump can make us, it is not a freshness
#: mechanism.
TTL_SECONDS = int(os.getenv("WHICHCLOUD_CACHE_TTL", str(6 * 3600)))

#: Bumped when the SHAPE of a cached value changes. A row written under
#: an older shape must not be read as a current one -- the same rule the
#: extraction cache follows, for the same reason.
CACHE_SCHEMA = "price-v1"

_URL = os.getenv("WHICHCLOUD_REDIS_URL", "redis://localhost:6379/0")

#: An escape hatch, not a default. The cache is ON wherever Redis is
#: reachable, including in tests -- which is deliberate, because the
#: property worth asserting is that a warm cache changes nothing, and a
#: test suite that always ran cold would never exercise it.
_DISABLED = bool(os.getenv("WHICHCLOUD_DISABLE_CACHE"))


@dataclass
class Stats:
    """Hit rate, so the cache can be shown to be doing something.

    A cache nobody measures is a cache nobody can tell is broken: a 0%
    hit rate and a working cache look identical from the outside.
    """

    hits: int = 0
    misses: int = 0
    errors: int = 0

    @property
    def lookups(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        return self.hits / self.lookups if self.lookups else 0.0

    def as_dict(self) -> dict:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "errors": self.errors,
            "lookups": self.lookups,
            "hit_rate": round(self.hit_rate, 4),
            "enabled": enabled(),
            "ttl_seconds": TTL_SECONDS,
        }


STATS = Stats()

_client = None
_client_tried = False


def enabled() -> bool:
    return not _DISABLED


def _connect():
    """One client, created lazily. A failure is remembered, so a missing
    Redis costs one connection attempt per process rather than one per
    price lookup."""
    global _client, _client_tried
    if _DISABLED:
        return None
    if _client_tried:
        return _client
    _client_tried = True
    try:
        import redis

        client = redis.Redis.from_url(
            _URL, socket_connect_timeout=0.25, socket_timeout=0.25,
        )
        client.ping()
        _client = client
    except Exception:  # noqa: BLE001 -- no cache is a valid state
        _client = None
    return _client


def reset() -> None:
    """Drop the client and the counters. For tests that need a cold start."""
    global _client, _client_tried, STATS
    _client, _client_tried = None, False
    STATS = Stats()


def key(*parts: object) -> str:
    return ":".join(["wc", CACHE_SCHEMA, *(str(p) for p in parts)])


def get(cache_key: str):
    """A cached value, or None. Never raises."""
    client = _connect()
    if client is None:
        return None
    try:
        raw = client.get(cache_key)
    except Exception:  # noqa: BLE001
        STATS.errors += 1
        return None
    if raw is None:
        STATS.misses += 1
        return None
    try:
        STATS.hits += 1
        return json.loads(raw)
    except Exception:  # noqa: BLE001 -- a corrupt row is a miss, not a crash
        STATS.errors += 1
        return None


def put(cache_key: str, value) -> None:
    """Store a value. Never raises, and a failure to cache is not a
    failure to price."""
    client = _connect()
    if client is None:
        return
    try:
        # `set(..., ex=)` rather than `setex`: the latter is deprecated
        # in redis-py 2.6.12+ and warns on every write.
        client.set(cache_key, json.dumps(value, default=_encode), ex=TTL_SECONDS)
    except Exception:  # noqa: BLE001
        STATS.errors += 1


def _encode(value):
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"{type(value).__name__} is not cacheable")


def invalidate_all() -> int:
    """Drop every cached rate. Called after an ingest, so a fresh catalog
    is never shadowed by rates from the previous one."""
    client = _connect()
    if client is None:
        return 0
    try:
        keys = list(client.scan_iter(match=key("*"), count=1000))
        if keys:
            client.delete(*keys)
        return len(keys)
    except Exception:  # noqa: BLE001
        STATS.errors += 1
        return 0
