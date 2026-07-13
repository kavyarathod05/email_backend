"""Teamtailor public careers JSON (jobs.json / API career-site)."""

from __future__ import annotations

from datetime import datetime, timezone

from intel.adapters.http_client import get_json
from intel.core.models.company import AtsProvider
from intel.core.models.job import NormalizedJob
from intel.modules.ats.base import register


@register
class TeamtailorProvider:
    name = AtsProvider.teamtailor

    async def list_jobs(
        self,
        *,
        board_token: str,
        company_name: str,
        company_slug: str,
    ) -> list[NormalizedJob]:
        host = board_token.replace("https://", "").replace("http://", "").rstrip("/")
        if "." not in host:
            host = f"{host}.teamtailor.com"
        candidates = [
            f"https://{host}/jobs.json",
            f"https://{host}/api/career-site/jobs",
        ]
        data = None
        for url in candidates:
            data = await get_json(url)
            if data:
                break
        if not data:
            return []

        if isinstance(data, dict):
            jobs = data.get("jobs") or data.get("data") or []
        elif isinstance(data, list):
            jobs = data
        else:
            return []

        out: list[NormalizedJob] = []
        for j in jobs:
            if not isinstance(j, dict):
                continue
            attrs = j.get("attributes") if j.get("type") == "jobs" else j
            if not isinstance(attrs, dict):
                attrs = j
            job_id = str(attrs.get("id") or j.get("id") or "")
            title = (attrs.get("title") or attrs.get("name") or "").strip()
            apply_url = attrs.get("url") or attrs.get("apply_url") or ""
            links = attrs.get("links")
            if not apply_url and isinstance(links, dict):
                apply_url = links.get("careersite-job-url") or links.get("self") or ""
            if not apply_url:
                slug = attrs.get("slug") or job_id
                apply_url = f"https://{host}/jobs/{slug}" if slug else ""
            if not title or not apply_url:
                continue
            if not job_id:
                job_id = apply_url
            loc = attrs.get("location") or attrs.get("remote_status") or ""
            if isinstance(loc, dict):
                location_text = loc.get("name") or loc.get("city")
            else:
                location_text = str(loc) if loc else None
            remote_status = attrs.get("remote_status")
            is_remote = remote_status == "fully_remote" or (
                bool(location_text) and "remote" in str(location_text).lower()
            )
            desc = attrs.get("body") or attrs.get("pitch") or attrs.get("description") or ""
            out.append(
                NormalizedJob(
                    external_job_id=str(job_id),
                    ats_provider=AtsProvider.teamtailor,
                    company_slug=company_slug,
                    company_name=company_name,
                    title=title,
                    location_text=location_text,
                    locations=[location_text] if location_text else [],
                    is_remote=bool(is_remote),
                    description_text=str(desc)[:20000] if desc else None,
                    apply_url=apply_url,
                    posted_at=datetime.now(timezone.utc),
                    raw={"id": job_id, "host": host},
                )
            )
        return out
