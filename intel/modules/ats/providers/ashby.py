"""Ashby public job board API."""

from __future__ import annotations

from datetime import datetime, timezone

from intel.adapters.http_client import get_json
from intel.core.models.company import AtsProvider
from intel.core.models.job import NormalizedJob
from intel.modules.ats.base import register


@register
class AshbyProvider:
    name = AtsProvider.ashby

    async def list_jobs(
        self,
        *,
        board_token: str,
        company_name: str,
        company_slug: str,
    ) -> list[NormalizedJob]:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{board_token}"
        data = await get_json(url)
        if not data or not isinstance(data, dict):
            return []
        jobs = data.get("jobs") or []
        out: list[NormalizedJob] = []
        for j in jobs:
            job_id = str(j.get("id") or j.get("jobId") or "")
            title = (j.get("title") or "").strip()
            apply_url = j.get("jobUrl") or j.get("applyUrl") or ""
            if not job_id or not title or not apply_url:
                continue
            loc = j.get("location") or ""
            locs = [loc] if loc else []
            is_remote = j.get("isRemote")
            if is_remote is None and loc and "remote" in str(loc).lower():
                is_remote = True
            desc = j.get("descriptionPlain") or j.get("descriptionHtml") or ""
            posted = None
            if j.get("publishedAt"):
                try:
                    posted = datetime.fromisoformat(
                        str(j["publishedAt"]).replace("Z", "+00:00")
                    )
                except Exception:
                    posted = None
            out.append(
                NormalizedJob(
                    external_job_id=job_id,
                    ats_provider=AtsProvider.ashby,
                    company_slug=company_slug,
                    company_name=company_name,
                    title=title,
                    location_text=loc or None,
                    locations=locs,
                    is_remote=is_remote,
                    description_text=desc[:20000] if desc else None,
                    apply_url=apply_url,
                    posted_at=posted or datetime.now(timezone.utc),
                    raw={"id": job_id, "board": board_token},
                )
            )
        return out
