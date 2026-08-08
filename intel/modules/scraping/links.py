"""Helpers to discover job detail URLs from a careers listing HTML page."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

_JOB_HREF_RE = re.compile(
    r"(job|jobs|career|careers|position|opening|vacanc|internship|intern|"
    r"opportunity|opportunities|/gh_jid=|/lever\.|/ashby|/boards\.)",
    re.I,
)
_SKIP_RE = re.compile(
    r"(login|signin|sign-up|signup|cookie|privacy|terms|mailto:|javascript:|"
    r"#$|\.pdf$|\.jpg$|\.png$)",
    re.I,
)


def extract_job_links(html: str, *, base_url: str, limit: int = 40) -> list[str]:
    """Return absolute job-like hrefs from a careers listing page."""
    soup = BeautifulSoup(html, "html.parser")
    base_host = urlparse(base_url).netloc.lower()
    out: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or _SKIP_RE.search(href):
            continue
        full = urljoin(base_url, href)
        if not full.startswith("http"):
            continue
        host = urlparse(full).netloc.lower()
        # Prefer same site; allow known ATS hosts
        if host != base_host and not _JOB_HREF_RE.search(full):
            continue
        text = a.get_text(" ", strip=True)
        if not (_JOB_HREF_RE.search(full) or _JOB_HREF_RE.search(text)):
            continue
        # Drop the careers landing itself
        if full.rstrip("/") == base_url.rstrip("/"):
            continue
        if full in seen:
            continue
        seen.add(full)
        out.append(full)
        if len(out) >= limit:
            break
    return out
