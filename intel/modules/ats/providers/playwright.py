"""HeadlessBrowserAdapter — Playwright for SPA career pages (opt-in)."""

from __future__ import annotations

import logging
import os
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from intel.core.models.company import AtsProvider
from intel.core.models.job import NormalizedJob
from intel.modules.ats.base import register
from intel.modules.scraping.jsonld import extract_json_ld_jobs, jobposting_to_normalized
from intel.modules.scraping.robots import robots_allowed

logger = logging.getLogger("email_automation.intel.ats.playwright")

_JOB_HREF_RE = re.compile(
    r"(job|jobs|career|careers|position|opening|intern)",
    re.I,
)
_MAX_LINKS = 40


def playwright_enabled() -> bool:
    return os.getenv("PLAYWRIGHT_SCRAPE_ENABLED", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


async def _render_html(url: str) -> str | None:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.warning("playwright package not installed; skip SPA scrape")
        return None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=45000)
                await page.wait_for_timeout(1500)
                return await page.content()
            finally:
                await browser.close()
    except Exception as e:
        logger.warning("playwright render failed url=%s err=%s", url, e)
        return None


def _job_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue
        full = urljoin(base_url, href)
        if not full.startswith("http"):
            continue
        text = a.get_text(" ", strip=True)
        if _JOB_HREF_RE.search(href) or _JOB_HREF_RE.search(text):
            out.append(full)
    return list(dict.fromkeys(out))[:_MAX_LINKS]


@register
class HeadlessBrowserAdapter:
    name = AtsProvider.playwright

    async def list_jobs(
        self,
        *,
        board_token: str,
        company_name: str,
        company_slug: str,
    ) -> list[NormalizedJob]:
        careers_url = board_token.strip()
        if not careers_url.startswith("http"):
            return []
        if not playwright_enabled():
            logger.info(
                "playwright disabled (set PLAYWRIGHT_SCRAPE_ENABLED=1); skip %s",
                company_slug,
            )
            return []
        if not await robots_allowed(careers_url):
            logger.info("robots.txt disallows playwright url=%s", careers_url)
            return []

        html = await _render_html(careers_url)
        if not html:
            return []

        out: list[NormalizedJob] = []
        seen: set[str] = set()

        def _add_from_html(page_html: str, base: str) -> None:
            for jp in extract_json_ld_jobs(page_html, base_url=base):
                nj = jobposting_to_normalized(
                    jp,
                    company_name=company_name,
                    company_slug=company_slug,
                    provider=AtsProvider.playwright,
                )
                if nj and nj.external_job_id not in seen:
                    seen.add(nj.external_job_id)
                    out.append(nj)

        _add_from_html(html, careers_url)

        # Follow job-like links once if landing page had no JobPosting
        if not out:
            for link in _job_links(html, careers_url):
                if not await robots_allowed(link):
                    continue
                page_html = await _render_html(link)
                if page_html:
                    _add_from_html(page_html, link)

        logger.info(
            "playwright company=%s url=%s jobs=%s",
            company_slug,
            careers_url,
            len(out),
        )
        return out
