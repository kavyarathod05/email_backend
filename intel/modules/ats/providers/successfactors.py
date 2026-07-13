"""SAP SuccessFactors public career site OData/JSON when board URL is configured.

board_token must be a full jobs JSON/OData URL for the customer career site.
"""

from __future__ import annotations

from datetime import datetime, timezone

from intel.adapters.http_client import get_json
from intel.core.models.company import AtsProvider
from intel.core.models.job import NormalizedJob
from intel.modules.ats.base import register


@register
class SuccessFactorsProvider:
    name = AtsProvider.successfactors

    async def list_jobs(
        self,
        *,
        board_token: str,
        company_name: str,
        company_slug: str,
    ) -> list[NormalizedJob]:
        if not board_token.startswith("http"):
            return []
        data = await get_json(board_token)
        if not data:
            return []
        if isinstance(data, dict):
            jobs = data.get("d", {}).get("results") if isinstance(data.get("d"), dict) else None
            jobs = jobs or data.get("jobRequisition") or data.get("jobs") or data.get("value") or []
        elif isinstance(data, list):
            jobs = data
        else:
            return []

        out: list[NormalizedJob] = []
        for j in jobs:
            if not isinstance(j, dict):
                continue
            job_id = str(j.get("jobReqId") or j.get("id") or j.get("externalId") or "")
            title = (j.get("title") or j.get("jobTitle") or j.get("defaultJobTitle") or "").strip()
            apply_url = j.get("jobUrl") or j.get("url") or j.get("externalUrl") or ""
            if not title:
                continue
            if not apply_url:
                apply_url = board_token  # at least keep feed reference
            if not job_id:
                job_id = f"{title}:{apply_url}"
            loc = j.get("location") or j.get("city") or j.get("country") or ""
            location_text = str(loc) if loc else None
            out.append(
                NormalizedJob(
                    external_job_id=str(job_id),
                    ats_provider=AtsProvider.successfactors,
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
