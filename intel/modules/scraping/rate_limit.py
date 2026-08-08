"""Per-domain async rate limiting."""

from __future__ import annotations

import asyncio
import time
from urllib.parse import urlparse

_DOMAIN_LOCKS: dict[str, asyncio.Lock] = {}
_DOMAIN_LAST: dict[str, float] = {}
_MIN_INTERVAL_SEC = 2.5


def domain_of(url: str) -> str:
    return urlparse(url).netloc.lower()


async def wait_rate_limit(url: str, *, min_interval: float = _MIN_INTERVAL_SEC) -> None:
    domain = domain_of(url)
    lock = _DOMAIN_LOCKS.setdefault(domain, asyncio.Lock())
    async with lock:
        last = _DOMAIN_LAST.get(domain, 0.0)
        wait = min_interval - (time.monotonic() - last)
        if wait > 0:
            await asyncio.sleep(wait)
        _DOMAIN_LAST[domain] = time.monotonic()
