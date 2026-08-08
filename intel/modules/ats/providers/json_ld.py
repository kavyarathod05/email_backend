"""JsonLdScraperAdapter — JobPosting JSON-LD on careers pages."""

from __future__ import annotations

import logging

from intel.core.models.company import AtsProvider
from intel.core.models.job import NormalizedJob
from intel.modules.ats.base import register
from intel.modules.scraping.fetch import fetch_text
from intel.modules.scraping.jsonld import extract_json_ld_jobs, jobposting_to_normalized

logger = logging.getLogger("email_automation.intel.ats.json_ld")


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
        postings = extract_json_ld_jobs(html, base_url=careers_url)
        out: list[NormalizedJob] = []
        for jp in postings:
            nj = jobposting_to_normalized(
                jp,
                company_name=company_name,
                company_slug=company_slug,
                provider=AtsProvider.json_ld,
            )
            if nj:
                out.append(nj)
        logger.info(
            "json_ld company=%s url=%s jobs=%s",
            company_slug,
            careers_url,
            len(out),
        )
        return out
