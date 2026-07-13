"""SmartRecruiters public postings API."""

from __future__ import annotations

from datetime import datetime, timezone

from intel.adapters.http_client import get_json
from intel.core.models.company import AtsProvider
from intel.core.models.job import NormalizedJob
from intel.modules.ats.base import register


@register
class SmartRecruitersProvider:
    name = AtsProvider.smartrecruiters

    async def list_jobs(
        self,
        *,
        board_token: str,
        company_name: str,
        company_slug: str,
    ) -> list[NormalizedJob]:
        out: list[NormalizedJob] = []
        offset = 0
        limit = 100
        while True:
            url = f"https://api.smartrecruiters.com/v1/companies/{board_token}/postings"
            data = await get_json(url, params={"limit": limit, "offset": offset})
            if not data or not isinstance(data, dict):
                break
            content = data.get("content") or []
            if not content:
                break
            for j in content:
                job_id = str(j.get("id") or j.get("uuid") or "")
                title = (j.get("name") or j.get("title") or "").strip()
                ref = (j.get("ref") or "") if isinstance(j.get("ref"), str) else ""
                apply_url = ref or (
                    f"https://jobs.smartrecruiters.com/{board_token}/{job_id}"
                    if job_id
                    else ""
                )
                if not job_id or not title or not apply_url:
                    continue
                loc = j.get("location") or {}
                parts = [
                    loc.get("city"),
                    loc.get("region"),
                    loc.get("country"),
                ]
                location_text = ", ".join(p for p in parts if p) or None
                is_remote = loc.get("remote") if isinstance(loc, dict) else None
                posted = None
                if j.get("releasedDate"):
                    try:
                        posted = datetime.fromisoformat(
                            str(j["releasedDate"]).replace("Z", "+00:00")
                        )
                    except Exception:
                        posted = None
                out.append(
                    NormalizedJob(
                        external_job_id=job_id,
                        ats_provider=AtsProvider.smartrecruiters,
                        company_slug=company_slug,
                        company_name=company_name,
                        title=title,
                        location_text=location_text,
                        locations=[location_text] if location_text else [],
                        is_remote=is_remote,
                        description_text=None,
                        apply_url=apply_url,
                        posted_at=posted or datetime.now(timezone.utc),
                        raw={"id": job_id, "company": board_token},
                    )
                )
            total = data.get("totalFound") or data.get("total") or 0
            offset += limit
            if offset >= total or len(content) < limit:
                break
        return out
