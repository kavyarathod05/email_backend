"""Greenhouse public boards API."""

from __future__ import annotations

from datetime import datetime, timezone

from intel.adapters.http_client import get_json
from intel.core.models.company import AtsProvider
from intel.core.models.job import NormalizedJob
from intel.modules.ats.base import register


@register
class GreenhouseProvider:
    name = AtsProvider.greenhouse

    async def list_jobs(
        self,
        *,
        board_token: str,
        company_name: str,
        company_slug: str,
    ) -> list[NormalizedJob]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"
        data = await get_json(url, params={"content": "true"})
        if not data or not isinstance(data, dict):
            return []
        jobs = data.get("jobs") or []
        out: list[NormalizedJob] = []
        for j in jobs:
            job_id = str(j.get("id", ""))
            title = (j.get("title") or "").strip()
            abs_url = j.get("absolute_url") or ""
            if not job_id or not title or not abs_url:
                continue
            locs = []
            loc_obj = j.get("location") or {}
            if isinstance(loc_obj, dict) and loc_obj.get("name"):
                locs.append(loc_obj["name"])
            for loc in j.get("offices") or []:
                if isinstance(loc, dict) and loc.get("name"):
                    locs.append(loc["name"])
            location_text = ", ".join(dict.fromkeys(locs)) if locs else None
            posted = None
            if j.get("updated_at"):
                try:
                    posted = datetime.fromisoformat(
                        j["updated_at"].replace("Z", "+00:00")
                    )
                except Exception:
                    posted = None
            desc = j.get("content") or ""
            is_remote = None
            blob = f"{location_text or ''} {title}".lower()
            if "remote" in blob:
                is_remote = True
            out.append(
                NormalizedJob(
                    external_job_id=job_id,
                    ats_provider=AtsProvider.greenhouse,
                    company_slug=company_slug,
                    company_name=company_name,
                    title=title,
                    location_text=location_text,
                    locations=locs,
                    is_remote=is_remote,
                    description_text=desc[:20000] if desc else None,
                    apply_url=abs_url,
                    posted_at=posted or datetime.now(timezone.utc),
                    raw={"id": job_id, "board": board_token},
                )
            )
        return out
