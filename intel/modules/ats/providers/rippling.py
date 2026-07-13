"""Rippling careers board — uses board_url JSON when configured.

board_token: Rippling careers board slug OR full jobs JSON URL in board_url.
Many Rippling-hosted boards expose:
  https://ats.rippling.com/api/v1/board/{board_id}/jobs
or company careers proxy — we try common patterns.
"""

from __future__ import annotations

from datetime import datetime, timezone

from intel.adapters.http_client import get_json
from intel.core.models.company import AtsProvider
from intel.core.models.job import NormalizedJob
from intel.modules.ats.base import register


@register
class RipplingProvider:
    name = AtsProvider.rippling

    async def list_jobs(
        self,
        *,
        board_token: str,
        company_name: str,
        company_slug: str,
    ) -> list[NormalizedJob]:
        token = board_token.strip()
        if token.startswith("http"):
            urls = [token]
        else:
            urls = [
                f"https://ats.rippling.com/api/v1/board/{token}/jobs",
                f"https://api.rippling.com/platform/api/ats/v1/board/{token}/jobs",
                f"https://ats.rippling.com/{token}/api/jobs",
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
            jobs = data.get("jobs") or data.get("items") or data.get("results") or []
        elif isinstance(data, list):
            jobs = data
        else:
            return []

        out: list[NormalizedJob] = []
        for j in jobs:
            if not isinstance(j, dict):
                continue
            job_id = str(j.get("id") or j.get("uuid") or j.get("jobId") or "")
            title = (j.get("name") or j.get("title") or "").strip()
            apply_url = (
                j.get("url")
                or j.get("applyUrl")
                or j.get("absolute_url")
                or j.get("jobUrl")
                or ""
            )
            if not title or not apply_url:
                continue
            if not job_id:
                job_id = apply_url
            loc = j.get("location") or j.get("locations") or ""
            if isinstance(loc, list):
                location_text = ", ".join(
                    (x.get("name") if isinstance(x, dict) else str(x)) for x in loc
                )
            elif isinstance(loc, dict):
                location_text = loc.get("name") or loc.get("city")
            else:
                location_text = str(loc) if loc else None
            is_remote = location_text and "remote" in location_text.lower()
            desc = j.get("description") or ""
            out.append(
                NormalizedJob(
                    external_job_id=str(job_id),
                    ats_provider=AtsProvider.rippling,
                    company_slug=company_slug,
                    company_name=company_name,
                    title=title,
                    location_text=location_text,
                    locations=[location_text] if location_text else [],
                    is_remote=bool(is_remote) if is_remote else None,
                    description_text=str(desc)[:20000] if desc else None,
                    apply_url=apply_url,
                    posted_at=datetime.now(timezone.utc),
                    raw={"id": job_id},
                )
            )
        return out
