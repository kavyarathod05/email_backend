"""iCIMS public career portal JSON endpoints when available.

board_token: portal host or company code.
Tries:
  https://careers-{token}.icims.com/jobs/search?ss=1&in_iframe=1&searchResultView=LIST&pr=0
  and JSON APIs used by some portals: /api/jobs or ?mode=json
"""

from __future__ import annotations

from datetime import datetime, timezone

from intel.adapters.http_client import get_json
from intel.core.models.company import AtsProvider
from intel.core.models.job import NormalizedJob
from intel.modules.ats.base import register


@register
class ICIMSProvider:
    name = AtsProvider.icims

    async def list_jobs(
        self,
        *,
        board_token: str,
        company_name: str,
        company_slug: str,
    ) -> list[NormalizedJob]:
        token = board_token.strip().replace("https://", "").replace("http://", "")
        if token.startswith("http"):
            urls = [board_token]
        else:
            base = token if "icims.com" in token else f"careers-{token}.icims.com"
            urls = [
                f"https://{base}/api/jobs",
                f"https://{base}/jobs/search?ss=1&searchResultView=LIST&mode=json",
                f"https://{base}/jobs/search.json",
            ]

        data = None
        for url in urls:
            try:
                data = await get_json(url)
                if data:
                    break
            except Exception:
                continue
        if not data:
            return []

        if isinstance(data, dict):
            jobs = data.get("jobs") or data.get("searchResults") or data.get("positions") or []
        elif isinstance(data, list):
            jobs = data
        else:
            return []

        out: list[NormalizedJob] = []
        for j in jobs:
            if not isinstance(j, dict):
                continue
            job_id = str(j.get("id") or j.get("jobId") or j.get("requisitionId") or "")
            title = (j.get("title") or j.get("jobTitle") or "").strip()
            apply_url = j.get("url") or j.get("jobUrl") or j.get("canonicalUrl") or ""
            if not title or not apply_url:
                continue
            if not job_id:
                job_id = apply_url
            loc = j.get("location") or j.get("primaryLocation") or ""
            if isinstance(loc, dict):
                location_text = loc.get("name") or loc.get("city")
            else:
                location_text = str(loc) if loc else None
            out.append(
                NormalizedJob(
                    external_job_id=str(job_id),
                    ats_provider=AtsProvider.icims,
                    company_slug=company_slug,
                    company_name=company_name,
                    title=title,
                    location_text=location_text,
                    locations=[location_text] if location_text else [],
                    is_remote=location_text and "remote" in location_text.lower() or None,
                    description_text=None,
                    apply_url=apply_url,
                    posted_at=datetime.now(timezone.utc),
                    raw={"id": job_id},
                )
            )
        return out
