"""Lever public postings API."""

from __future__ import annotations

from datetime import datetime, timezone

from intel.adapters.http_client import get_json
from intel.core.models.company import AtsProvider
from intel.core.models.job import NormalizedJob
from intel.modules.ats.base import register


@register
class LeverProvider:
    name = AtsProvider.lever

    async def list_jobs(
        self,
        *,
        board_token: str,
        company_name: str,
        company_slug: str,
    ) -> list[NormalizedJob]:
        url = f"https://api.lever.co/v0/postings/{board_token}"
        data = await get_json(url, params={"mode": "json"})
        if not data or not isinstance(data, list):
            return []
        out: list[NormalizedJob] = []
        for j in data:
            job_id = str(j.get("id") or j.get("leverId") or "")
            title = (j.get("text") or "").strip()
            apply_url = j.get("hostedUrl") or j.get("applyUrl") or ""
            if not job_id or not title or not apply_url:
                continue
            cats = j.get("categories") or {}
            location = cats.get("location") or j.get("location")
            locs = [location] if location else []
            location_text = location
            is_remote = None
            if location and "remote" in str(location).lower():
                is_remote = True
            desc_parts = []
            for key in ("descriptionPlain", "description", "additionalPlain"):
                if j.get(key):
                    desc_parts.append(str(j[key]))
            desc = "\n".join(desc_parts)[:20000] or None
            posted = None
            if j.get("createdAt"):
                try:
                    posted = datetime.fromtimestamp(
                        j["createdAt"] / 1000.0, tz=timezone.utc
                    )
                except Exception:
                    posted = None
            out.append(
                NormalizedJob(
                    external_job_id=job_id,
                    ats_provider=AtsProvider.lever,
                    company_slug=company_slug,
                    company_name=company_name,
                    title=title,
                    location_text=location_text,
                    locations=locs,
                    is_remote=is_remote,
                    description_text=desc,
                    apply_url=apply_url,
                    posted_at=posted or datetime.now(timezone.utc),
                    raw={"id": job_id, "site": board_token},
                )
            )
        return out
