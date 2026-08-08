"""SitemapCrawlerAdapter — discover job URLs via sitemap, prefer JSON-LD on each page."""

from __future__ import annotations

import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from intel.core.models.company import AtsProvider
from intel.core.models.job import NormalizedJob
from intel.modules.ats.base import register
from intel.modules.scraping.fetch import fetch_text
from intel.modules.scraping.jsonld import extract_json_ld_jobs, jobposting_to_normalized
from intel.modules.scraping.robots import origin_of

logger = logging.getLogger("email_automation.intel.ats.sitemap")

_JOB_PATH_RE = re.compile(
    r"(job|jobs|career|careers|position|opening|vacanc|internship|intern|"
    r"opportunity|opportunities|role|roles|hiring)",
    re.I,
)
_MAX_SITEMAP_URLS = 80
_MAX_NESTED_SITEMAPS = 8


def _strip_ns(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _parse_sitemap_locs(xml_text: str) -> tuple[list[str], list[str]]:
    """Return (page_urls, nested_sitemap_urls)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return [], []
    tag = _strip_ns(root.tag).lower()
    locs: list[str] = []
    for el in root.iter():
        if _strip_ns(el.tag).lower() != "loc" or not el.text:
            continue
        loc = el.text.strip()
        if loc.startswith("http"):
            locs.append(loc)
    locs = list(dict.fromkeys(locs))
    if tag == "sitemapindex":
        return [], locs
    pages: list[str] = []
    nested: list[str] = []
    for u in locs:
        low = u.lower()
        if low.endswith(".xml") and "sitemap" in low:
            nested.append(u)
        else:
            pages.append(u)
    return pages, nested


def _job_like(url: str) -> bool:
    path = urlparse(url).path or ""
    return bool(_JOB_PATH_RE.search(path))


def _heuristic_job(
    html: str,
    *,
    page_url: str,
    company_name: str,
    company_slug: str,
) -> NormalizedJob | None:
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(" ", strip=True) or title
    if not title or len(title) < 3:
        return None
    # Skip pure listing pages
    lower = title.lower()
    if lower in ("careers", "jobs", "job openings", "open positions"):
        return None
    loc_el = soup.find(attrs={"class": re.compile(r"location", re.I)})
    location = loc_el.get_text(" ", strip=True) if loc_el else None
    desc = ""
    main = soup.find("main") or soup.find("article") or soup.body
    if main:
        desc = main.get_text(" ", strip=True)[:5000]
    ext_id = hashlib.sha1(page_url.encode("utf-8")).hexdigest()[:16]
    return NormalizedJob(
        external_job_id=ext_id,
        ats_provider=AtsProvider.sitemap,
        company_slug=company_slug,
        company_name=company_name,
        title=title[:300],
        location_text=location,
        locations=[location] if location else [],
        is_remote="remote" in f"{title} {location or ''}".lower() or None,
        description_text=desc or None,
        apply_url=page_url,
        posted_at=datetime.now(timezone.utc),
        raw={"source": "sitemap_heuristic", "url": page_url},
    )


@register
class SitemapCrawlerAdapter:
    name = AtsProvider.sitemap

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
        origin = origin_of(careers_url)
        sitemap_url = urljoin(origin + "/", "sitemap.xml")

        page_urls: list[str] = []
        to_fetch = [sitemap_url]
        seen_sitemaps: set[str] = set()

        while to_fetch and len(seen_sitemaps) < _MAX_NESTED_SITEMAPS:
            sm = to_fetch.pop(0)
            if sm in seen_sitemaps:
                continue
            seen_sitemaps.add(sm)
            xml_text = await fetch_text(
                sm,
                accept="application/xml,text/xml,*/*;q=0.8",
            )
            if not xml_text:
                continue
            pages, nested = _parse_sitemap_locs(xml_text)
            page_urls.extend(pages)
            for n in nested:
                if n not in seen_sitemaps:
                    to_fetch.append(n)

        # Also try careers-relative sitemap hints
        for hint in ("sitemap_index.xml", "job-sitemap.xml", "sitemap-jobs.xml"):
            hint_url = urljoin(origin + "/", hint)
            if hint_url not in seen_sitemaps:
                xml_text = await fetch_text(
                    hint_url,
                    accept="application/xml,text/xml,*/*;q=0.8",
                )
                if xml_text:
                    pages, nested = _parse_sitemap_locs(xml_text)
                    page_urls.extend(pages)

        job_urls = [u for u in dict.fromkeys(page_urls) if _job_like(u)]
        job_urls = job_urls[:_MAX_SITEMAP_URLS]

        out: list[NormalizedJob] = []
        seen_ids: set[str] = set()
        for url in job_urls:
            html = await fetch_text(url)
            if not html:
                continue
            postings = extract_json_ld_jobs(html, base_url=url)
            if postings:
                for jp in postings:
                    nj = jobposting_to_normalized(
                        jp,
                        company_name=company_name,
                        company_slug=company_slug,
                        provider=AtsProvider.sitemap,
                    )
                    if nj and nj.external_job_id not in seen_ids:
                        seen_ids.add(nj.external_job_id)
                        out.append(nj)
            else:
                nj = _heuristic_job(
                    html,
                    page_url=url,
                    company_name=company_name,
                    company_slug=company_slug,
                )
                if nj and nj.external_job_id not in seen_ids:
                    seen_ids.add(nj.external_job_id)
                    out.append(nj)

        logger.info(
            "sitemap company=%s origin=%s urls=%s jobs=%s",
            company_slug,
            origin,
            len(job_urls),
            len(out),
        )
        return out
