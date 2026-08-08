"""JsonLdScraperAdapter — JobPosting JSON-LD on careers pages (+ linked job pages)."""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from intel.core.models.company import AtsProvider
from intel.core.models.job import NormalizedJob
from intel.modules.ats.base import register
from intel.modules.scraping.fetch import fetch_text
from intel.modules.scraping.jsonld import (
    extract_json_ld_jobs,
    heuristic_listing_job,
    jobposting_to_normalized,
)
from intel.modules.scraping.links import extract_job_links

logger = logging.getLogger("email_automation.intel.ats.json_ld")

_MAX_DETAIL_PAGES = 30


@register
class JsonLdScraperAdapter:
    name = AtsProvider.json_ld

    async def list_jobs(
        self,
        *,
        board_token: str,
        company_name: str,
        company_slug: str,
    ) -> list[NormalizedJob]:
        """board_token is the careers_url for custom scrapers."""
        careers_url = board_token.strip()
        if not careers_url.startswith("http"):
            return []

        html = await fetch_text(careers_url)
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
                    provider=AtsProvider.json_ld,
                )
                if nj and nj.external_job_id not in seen:
                    seen.add(nj.external_job_id)
                    out.append(nj)

        _add_from_html(html, careers_url)

        # Listing pages rarely embed JobPosting — follow job-like links
        if len(out) < 3:
            links = extract_job_links(html, base_url=careers_url, limit=_MAX_DETAIL_PAGES)
            for link in links:
                detail = await fetch_text(link)
                if not detail:
                    # Still keep the listing link if the anchor looks like a job title
                    continue
                before = len(out)
                _add_from_html(detail, link)
                if len(out) == before:
                    # Fallback: page title / h1 as a candidate job
                    soup = BeautifulSoup(detail, "html.parser")
                    title = ""
                    h1 = soup.find("h1")
                    if h1:
                        title = h1.get_text(" ", strip=True)
                    if not title and soup.title and soup.title.string:
                        title = soup.title.string.strip()
                    nj = heuristic_listing_job(
                        title=title,
                        url=link,
                        company_name=company_name,
                        company_slug=company_slug,
                        provider=AtsProvider.json_ld,
                    )
                    if nj and nj.external_job_id not in seen:
                        seen.add(nj.external_job_id)
                        out.append(nj)

            # Last resort: anchors on the listing themselves (title = link text)
            if not out:
                soup = BeautifulSoup(html, "html.parser")
                from urllib.parse import urljoin

                for a in soup.find_all("a", href=True):
                    text = a.get_text(" ", strip=True)
                    href = a["href"].strip()
                    if len(text) < 8:
                        continue
                    low = text.lower()
                    if not any(
                        k in low
                        for k in (
                            "intern",
                            "engineer",
                            "developer",
                            "software",
                            "sde",
                            "swe",
                            "job",
                            "career",
                        )
                    ):
                        continue
                    full = urljoin(careers_url, href)
                    if not full.startswith("http"):
                        continue
                    nj = heuristic_listing_job(
                        title=text,
                        url=full,
                        company_name=company_name,
                        company_slug=company_slug,
                        provider=AtsProvider.json_ld,
                    )
                    if nj and nj.external_job_id not in seen:
                        seen.add(nj.external_job_id)
                        out.append(nj)
                    if len(out) >= _MAX_DETAIL_PAGES:
                        break

        logger.info(
            "json_ld company=%s url=%s jobs=%s",
            company_slug,
            careers_url,
            len(out),
        )
        return out
