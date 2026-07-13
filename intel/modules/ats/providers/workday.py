"""Workday CXS public jobs search API.

board_token formats:
  - full CXS jobs URL: https://company.wd5.myworkdayjobs.com/wday/cxs/company/site/jobs
  - host|tenant|site  e.g. company.wd5.myworkdayjobs.com|company|External
"""

from __future__ import annotations

from datetime import datetime, timezone

from intel.adapters.http_client import post_json
from intel.core.models.company import AtsProvider
from intel.core.models.job import NormalizedJob
from intel.modules.ats.base import register


def _jobs_endpoint(board_token: str) -> tuple[str, str]:
    """Return (jobs_url, apply_base)."""
    token = board_token.strip()
    if token.startswith("http"):
        jobs_url = token if token.endswith("/jobs") else token.rstrip("/") + "/jobs"
        # apply links are relative to career site root
        # https://x.wdN.myworkdayjobs.com/wday/cxs/tenant/site/jobs
        parts = jobs_url.split("/wday/cxs/")
        if len(parts) == 2:
            host = parts[0]
            rest = parts[1].rsplit("/jobs", 1)[0]  # tenant/site
            site = rest.split("/")[-1]
            apply_base = f"{host}/{site}"
        else:
            apply_base = jobs_url.rsplit("/wday/", 1)[0]
        return jobs_url, apply_base

    if "|" in token:
        host, tenant, site = [p.strip() for p in token.split("|", 2)]
        host = host.replace("https://", "").replace("http://", "")
        jobs_url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
        apply_base = f"https://{host}/{site}"
        return jobs_url, apply_base

    raise ValueError(
        "Workday board_token must be CXS jobs URL or host|tenant|site"
    )


@register
class WorkdayProvider:
    name = AtsProvider.workday

    async def list_jobs(
        self,
        *,
        board_token: str,
        company_name: str,
        company_slug: str,
    ) -> list[NormalizedJob]:
        jobs_url, apply_base = _jobs_endpoint(board_token)
        out: list[NormalizedJob] = []
        offset = 0
        limit = 50
        while True:
            data = await post_json(
                jobs_url,
                json_body={
                    "appliedFacets": {},
                    "limit": limit,
                    "offset": offset,
                    "searchText": "",
                },
            )
            if not data or not isinstance(data, dict):
                break
            postings = data.get("jobPostings") or []
            if not postings:
                break
            for j in postings:
                title = (j.get("title") or "").strip()
                external_path = j.get("externalPath") or j.get("bulletFields") or ""
                job_id = str(
                    j.get("bulletFields", [None])[0]
                    if isinstance(j.get("bulletFields"), list) and j.get("bulletFields")
                    else j.get("id") or external_path or title
                )
                if external_path and isinstance(external_path, str):
                    apply_url = (
                        external_path
                        if external_path.startswith("http")
                        else f"{apply_base}{external_path}"
                    )
                    job_id = external_path
                else:
                    apply_url = apply_base
                if not title or not apply_url:
                    continue
                loc = j.get("locationsText") or j.get("location") or ""
                is_remote = "remote" in str(loc).lower() if loc else None
                out.append(
                    NormalizedJob(
                        external_job_id=str(job_id),
                        ats_provider=AtsProvider.workday,
                        company_slug=company_slug,
                        company_name=company_name,
                        title=title,
                        location_text=str(loc) if loc else None,
                        locations=[str(loc)] if loc else [],
                        is_remote=is_remote,
                        description_text=None,
                        apply_url=apply_url,
                        posted_at=datetime.now(timezone.utc),
                        raw={"path": external_path},
                    )
                )
            total = data.get("total") or 0
            offset += limit
            if offset >= total or len(postings) < limit:
                break
            if offset > 500:  # safety
                break
        return out
