"""robots.txt helpers for polite scraping."""

from __future__ import annotations

import logging
import time
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from intel.modules.scraping.constants import USER_AGENT

logger = logging.getLogger("email_automation.intel.scraping.robots")

_ROBOTS_CACHE: dict[str, tuple[float, RobotFileParser | None]] = {}
_ROBOTS_TTL = 3600.0


def origin_of(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


async def robots_allowed(url: str, *, user_agent: str = USER_AGENT) -> bool:
    """Return True if robots.txt allows fetching url for our UA."""
    origin = origin_of(url)
    now = time.monotonic()
    cached = _ROBOTS_CACHE.get(origin)
    if cached and now - cached[0] < _ROBOTS_TTL:
        rp = cached[1]
        if rp is None:
            return True
        return rp.can_fetch(user_agent, url)

    robots_url = urljoin(origin + "/", "robots.txt")
    rp = RobotFileParser()
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            headers={"User-Agent": user_agent},
            follow_redirects=True,
        ) as client:
            resp = await client.get(robots_url)
            if resp.status_code >= 400:
                _ROBOTS_CACHE[origin] = (now, None)
                return True
            rp.parse(resp.text.splitlines())
            _ROBOTS_CACHE[origin] = (now, rp)
            return rp.can_fetch(user_agent, url)
    except Exception as e:
        logger.debug("robots.txt fetch failed origin=%s err=%s", origin, e)
        _ROBOTS_CACHE[origin] = (now, None)
        return True
