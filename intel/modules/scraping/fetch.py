"""Polite HTTP fetch for career-page scrapers."""

from __future__ import annotations

import asyncio
import logging

import httpx

from intel.modules.scraping.constants import DEFAULT_TIMEOUT, USER_AGENT
from intel.modules.scraping.rate_limit import wait_rate_limit
from intel.modules.scraping.robots import robots_allowed

logger = logging.getLogger("email_automation.intel.scraping.fetch")


async def fetch_text(
    url: str,
    *,
    accept: str = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    max_retries: int = 3,
    check_robots: bool = True,
) -> str | None:
    """Polite GET with robots check, rate limit, and retries. Returns body text or None."""
    if check_robots and not await robots_allowed(url):
        logger.info("robots.txt disallows url=%s", url)
        return None

    last_err: Exception | None = None
    for attempt in range(max_retries):
        await wait_rate_limit(url)
        try:
            async with httpx.AsyncClient(
                timeout=DEFAULT_TIMEOUT,
                headers={"User-Agent": USER_AGENT, "Accept": accept},
                follow_redirects=True,
            ) as client:
                resp = await client.get(url)
                if resp.status_code == 404:
                    return None
                if resp.status_code == 429:
                    await asyncio.sleep(2 ** attempt * 2)
                    continue
                resp.raise_for_status()
                return resp.text
        except Exception as e:
            last_err = e
            await asyncio.sleep(2 ** attempt * 0.5)
    if last_err:
        logger.warning("fetch_text failed url=%s err=%s", url, last_err)
    return None
