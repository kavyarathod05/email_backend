"""Workable public widget/accounts JSON API."""

from __future__ import annotations

from datetime import datetime, timezone

from intel.adapters.http_client import get_json
from intel.core.models.company import AtsProvider
from intel.core.models.job import NormalizedJob
from intel.modules.ats.base import register


@register
class WorkableProvider:
    name = AtsProvider.workable

    async def list_jobs(
        self,
        *,
        board_token: str,
        company_name: str,
        company_slug: str,
    ) -> list[NormalizedJob]:
        # Prefer apply.workable widget; fall back to www.workable.com
        urls = [
            f"https://apply.workable.com/api/v1/widget/accounts/{board_token}?details=true",
            f"https://www.workable.com/api/accounts/{board_token}?details=true",
        ]
        data = None
        for url in urls:
            data = await get_json(url)
            if data:
                break
        if not data or not isinstance(data, dict):
            return []
        jobs = data.get("jobs") or []
        out: list[NormalizedJob] = []
        for j in jobs:
            job_id = str(j.get("id") or j.get("shortcode") or "")
            title = (j.get("title") or "").strip()
            apply_url = j.get("url") or j.get("shortlink") or j.get("application_url") or ""
            if not job_id or not title or not apply_url:
                continue
            loc = j.get("location") or {}
            if isinstance(loc, dict):
                location_text = loc.get("location_str") or ", ".join(
                    p for p in [loc.get("city"), loc.get("region"), loc.get("country")] if p
                )
            else:
                location_text = str(loc) if loc else None
            locs_list = []
            for L in j.get("locations") or []:
                if isinstance(L, dict):
                    locs_list.append(L.get("location_str") or L.get("city") or "")
            is_remote = None
            blob = f"{location_text or ''} {' '.join(locs_list)}".lower()
            if "remote" in blob:
                is_remote = True
            desc = j.get("description") or j.get("full_description") or ""
            posted = None
            for key in ("published_on", "created_at"):
                if j.get(key):
                    try:
                        posted = datetime.fromisoformat(
                            str(j[key]).replace("Z", "+00:00")
                        )
                        break
                    except Exception:
                        pass
            out.append(
                NormalizedJob(
                    external_job_id=job_id,
                    ats_provider=AtsProvider.workable,
                    company_slug=company_slug,
                    company_name=company_name,
                    title=title,
                    location_text=location_text or (locs_list[0] if locs_list else None),
                    locations=locs_list,
                    is_remote=is_remote,
                    description_text=desc[:20000] if desc else None,
                    apply_url=apply_url,
                    posted_at=posted or datetime.now(timezone.utc),
                    raw={"id": job_id, "account": board_token},
                )
            )
        return out
