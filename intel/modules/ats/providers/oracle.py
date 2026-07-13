"""Oracle Cloud HCM / Taleo-style public requisition JSON when board_url is set.

board_token: full JSON feed URL (preferred) OR site path fragment.
Oracle/Taleo public boards vary by customer — require explicit board_url/token URL.
"""

from __future__ import annotations

from datetime import datetime, timezone

from intel.adapters.http_client import get_json
from intel.core.models.company import AtsProvider
from intel.core.models.job import NormalizedJob
from intel.modules.ats.base import register


@register
class OracleProvider:
    name = AtsProvider.oracle

    async def list_jobs(
        self,
        *,
        board_token: str,
        company_name: str,
        company_slug: str,
    ) -> list[NormalizedJob]:
        if not board_token.startswith("http"):
            # Common CX pattern placeholder — caller should set full URL
            url = board_token
            return []
        data = await get_json(board_token)
        if not data:
            return []
        if isinstance(data, dict):
            jobs = (
                data.get("items")
                or data.get("requisitions")
                or data.get("jobs")
                or data.get("jobSearchResponse", {}).get("jobSearchResult")
                or []
            )
        elif isinstance(data, list):
            jobs = data
        else:
            return []

        out: list[NormalizedJob] = []
        for j in jobs:
            if not isinstance(j, dict):
                continue
            job_id = str(
                j.get("Id")
                or j.get("id")
                or j.get("requisitionId")
                or j.get("JobId")
                or ""
            )
            title = (
                j.get("Title")
                or j.get("title")
                or j.get("PostingTitle")
                or j.get("jobTitle")
                or ""
            ).strip()
            apply_url = (
                j.get("URL")
                or j.get("url")
                or j.get("AppliedJobUrl")
                or j.get("jobUrl")
                or ""
            )
            if not title or not apply_url:
                continue
            if not job_id:
                job_id = apply_url
            loc = j.get("PrimaryLocation") or j.get("location") or j.get("City") or ""
            location_text = str(loc) if loc else None
            out.append(
                NormalizedJob(
                    external_job_id=str(job_id),
                    ats_provider=AtsProvider.oracle,
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
