"""BambooHR public careers list JSON."""

from __future__ import annotations

from datetime import datetime, timezone

from intel.adapters.http_client import get_json
from intel.core.models.company import AtsProvider
from intel.core.models.job import NormalizedJob
from intel.modules.ats.base import register


@register
class BambooHRProvider:
    name = AtsProvider.bamboohr

    async def list_jobs(
        self,
        *,
        board_token: str,
        company_name: str,
        company_slug: str,
    ) -> list[NormalizedJob]:
        # board_token = subdomain (company)
        sub = board_token.replace(".bamboohr.com", "").strip("/")
        url = f"https://{sub}.bamboohr.com/careers/list"
        data = await get_json(url)
        if not data:
            return []
        result = data.get("result") if isinstance(data, dict) else data
        if not isinstance(result, list):
            result = (data or {}).get("meta", {}).get("jobs") if isinstance(data, dict) else []
        # BambooHR varies: sometimes {result: [...]} with id/jobOpeningName
        jobs = result if isinstance(result, list) else []
        if not jobs and isinstance(data, dict):
            jobs = data.get("jobs") or []

        out: list[NormalizedJob] = []
        for j in jobs:
            if not isinstance(j, dict):
                continue
            job_id = str(j.get("id") or j.get("jobOpeningId") or "")
            title = (j.get("jobOpeningName") or j.get("jobTitle") or j.get("title") or "").strip()
            apply_url = (
                j.get("jobOpeningShareUrl")
                or j.get("url")
                or (f"https://{sub}.bamboohr.com/careers/{job_id}" if job_id else "")
            )
            if not title or not apply_url:
                continue
            if not job_id:
                job_id = apply_url
            loc = j.get("location") or j.get("departmentLabel") or ""
            if isinstance(loc, dict):
                location_text = loc.get("city") or loc.get("name")
            else:
                location_text = str(loc) if loc else None
            is_remote = location_text and "remote" in location_text.lower()
            out.append(
                NormalizedJob(
                    external_job_id=str(job_id),
                    ats_provider=AtsProvider.bamboohr,
                    company_slug=company_slug,
                    company_name=company_name,
                    title=title,
                    location_text=location_text,
                    locations=[location_text] if location_text else [],
                    is_remote=bool(is_remote) if is_remote else None,
                    description_text=None,
                    apply_url=apply_url,
                    posted_at=datetime.now(timezone.utc),
                    raw={"id": job_id, "sub": sub},
                )
            )
        return out
