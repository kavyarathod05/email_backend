"""Parse schema.org JobPosting from HTML / JSON-LD blobs."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from intel.core.models.company import AtsProvider
from intel.core.models.job import NormalizedJob


def _as_list(val: Any) -> list[Any]:
    if val is None:
        return []
    if isinstance(val, list):
        return val
    return [val]


def _text(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, dict):
        return (val.get("name") or val.get("@value") or "").strip()
    return str(val).strip()


def _location_from_job(job: dict[str, Any]) -> str | None:
    parts: list[str] = []
    for loc in _as_list(job.get("jobLocation")):
        if isinstance(loc, str):
            parts.append(loc)
            continue
        if not isinstance(loc, dict):
            continue
        addr = loc.get("address") or loc
        if isinstance(addr, str):
            parts.append(addr)
            continue
        if isinstance(addr, dict):
            bits = [
                addr.get("addressLocality"),
                addr.get("addressRegion"),
                addr.get("addressCountry"),
            ]
            parts.append(", ".join(str(b) for b in bits if b))
        name = loc.get("name")
        if name:
            parts.append(str(name))
    cleaned = [p.strip() for p in parts if p and str(p).strip()]
    return ", ".join(dict.fromkeys(cleaned)) if cleaned else None


def _job_id(url: str, title: str) -> str:
    raw = f"{url}|{title}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]


def _parse_date(val: Any) -> datetime | None:
    if not val or not isinstance(val, str):
        return None
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except Exception:
        return None


def _loads_json_blobs(raw: str) -> list[Any]:
    """Parse one or more JSON values from a script body (tolerant)."""
    text = raw.strip()
    if not text:
        return []
    # Strip HTML comments / CDATA wrappers some CMS inject
    text = re.sub(r"^\s*<!--", "", text)
    text = re.sub(r"-->\s*$", "", text)
    text = re.sub(r"/\*\s*<!\[CDATA\[\s*\*/", "", text)
    text = re.sub(r"/\*\s*\]\]>\s*\*/", "", text)
    text = text.strip()
    out: list[Any] = []
    try:
        out.append(json.loads(text))
        return out
    except json.JSONDecodeError:
        pass
    # Concatenated objects: }{
    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(text):
        while idx < len(text) and text[idx].isspace():
            idx += 1
        if idx >= len(text):
            break
        try:
            val, end = decoder.raw_decode(text, idx)
            out.append(val)
            idx = end
        except json.JSONDecodeError:
            break
    return out


def iter_jobpostings(node: Any, *, _seen: set[int] | None = None) -> list[dict[str, Any]]:
    """Recursively collect JobPosting dicts from JSON-LD trees."""
    if _seen is None:
        _seen = set()
    out: list[dict[str, Any]] = []
    if isinstance(node, list):
        for item in node:
            out.extend(iter_jobpostings(item, _seen=_seen))
        return out
    if not isinstance(node, dict):
        return out
    node_id = id(node)
    if node_id in _seen:
        return out
    _seen.add(node_id)
    types = node.get("@type")
    type_list = [types] if isinstance(types, str) else list(types or [])
    if any(
        str(t).lower()
        in (
            "jobposting",
            "http://schema.org/jobposting",
            "https://schema.org/jobposting",
        )
        for t in type_list
    ):
        out.append(node)
    if "@graph" in node:
        out.extend(iter_jobpostings(node["@graph"], _seen=_seen))
    for k, v in node.items():
        if k in ("@graph", "@type"):
            continue
        if isinstance(v, (dict, list)):
            out.extend(iter_jobpostings(v, _seen=_seen))
    return out


def extract_json_ld_jobs(html: str, *, base_url: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    jobs: list[dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        raw = script.string or script.get_text() or ""
        for data in _loads_json_blobs(raw):
            for jp in iter_jobpostings(data):
                jobs.append(jp)
    # Dedup by title+url
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for j in jobs:
        title = _text(j.get("title"))
        url = _text(j.get("url") or j.get("sameAs") or "")
        if url and not url.startswith("http"):
            url = urljoin(base_url, url)
        key = f"{title}|{url}"
        if not title or key in seen:
            continue
        seen.add(key)
        j["_resolved_url"] = url or base_url
        unique.append(j)
    return unique


def jobposting_to_normalized(
    jp: dict[str, Any],
    *,
    company_name: str,
    company_slug: str,
    provider: AtsProvider = AtsProvider.json_ld,
) -> NormalizedJob | None:
    title = _text(jp.get("title"))
    url = _text(jp.get("_resolved_url") or jp.get("url") or jp.get("sameAs") or "")
    if not title or not url:
        return None
    desc = _text(jp.get("description"))
    if "<" in desc:
        desc = BeautifulSoup(desc, "html.parser").get_text(" ", strip=True)
    location_text = _location_from_job(jp)
    is_remote = None
    blob = f"{location_text or ''} {title} {desc[:500]}".lower()
    if "remote" in blob:
        is_remote = True
    posted = _parse_date(jp.get("datePosted")) or datetime.now(timezone.utc)
    return NormalizedJob(
        external_job_id=_job_id(url, title),
        ats_provider=provider,
        company_slug=company_slug,
        company_name=company_name,
        title=title,
        location_text=location_text,
        locations=[location_text] if location_text else [],
        is_remote=is_remote,
        description_text=desc[:20000] if desc else None,
        apply_url=url,
        posted_at=posted,
        raw={"source": provider.value, "title": title},
    )


def heuristic_listing_job(
    *,
    title: str,
    url: str,
    company_name: str,
    company_slug: str,
    provider: AtsProvider,
    location: str | None = None,
) -> NormalizedJob | None:
    title = (title or "").strip()
    if not title or not url:
        return None
    return NormalizedJob(
        external_job_id=_job_id(url, title),
        ats_provider=provider,
        company_slug=company_slug,
        company_name=company_name,
        title=title[:300],
        location_text=location,
        locations=[location] if location else [],
        is_remote=("remote" in f"{title} {location or ''}".lower()) or None,
        description_text=None,
        apply_url=url,
        posted_at=datetime.now(timezone.utc),
        raw={"source": f"{provider.value}_link", "url": url},
    )
