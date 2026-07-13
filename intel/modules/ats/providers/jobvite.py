"""Jobvite public careers JSON (company.jobvite.com)."""

from __future__ import annotations

from datetime import datetime, timezone

from intel.adapters.http_client import get_json
from intel.core.models.company import AtsProvider
from intel.core.models.job import NormalizedJob
from intel.modules.ats.base import register


@register
class JobviteProvider:
    name = AtsProvider.jobvite

    async def list_jobs(
        self,
        *,
        board_token: str,
        company_name: str,
        company_slug: str,
    ) -> list[NormalizedJob]:
        # board_token: company code used in jobs.jobvite.com / company.jobvite.com
        code = board_token.strip()
        candidates = [
            f"https://jobs.jobvite.com/{code}/job",
            f"https://jobs.jobvite.com/api/v1/job?company={code}",
            f"https://{code}.jobvite.com/api/jobs",
        ]
        data = None
        for url in candidates:
            try:
                data = await get_json(url)
                if data:
                    break
            except Exception:
                continue
        if not data:
            return []

        if isinstance(data, dict):
            jobs = data.get("positions") or data.get("jobs") or data.get("requisitions") or []
            if not jobs and "job" in data:
                jobs = data["job"] if isinstance(data["job"], list) else [data["job"]]
        elif isinstance(data, list):
            jobs = data
        else:
            return []

        out: list[NormalizedJob] = []
        for j in jobs:
            if not isinstance(j, dict):
                continue
            job_id = str(j.get("id") or j.get("eId") or j.get("jobId") or "")
            title = (j.get("title") or j.get("jobTitle") or "").strip()
            apply_url = (
                j.get("applyUrl")
                or j.get("url")
                or j.get("detailUrl")
                or (
                    f"https://jobs.jobvite.com/{code}/job/{j.get('eId') or job_id}"
                    if job_id
                    else ""
                )
            )
            if not title or not apply_url:
                continue
            if not job_id:
                job_id = apply_url
            loc = j.get("location") or j.get("city") or ""
            location_text = str(loc) if loc else None
            is_remote = location_text and "remote" in location_text.lower()
            desc = j.get("description") or j.get("jobDescription") or ""
            out.append(
                NormalizedJob(
                    external_job_id=str(job_id),
                    ats_provider=AtsProvider.jobvite,
                    company_slug=company_slug,
                    company_name=company_name,
                    title=title,
                    location_text=location_text,
                    locations=[location_text] if location_text else [],
                    is_remote=bool(is_remote) if is_remote else None,
                    description_text=str(desc)[:20000] if desc else None,
                    apply_url=apply_url,
                    posted_at=datetime.now(timezone.utc),
                    raw={"id": job_id, "code": code},
                )
            )
        return out
