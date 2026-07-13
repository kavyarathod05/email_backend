"""Crawl companies → detect → filter → upsert jobs (with per-company logs)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from intel.core.models.job import CrawlRunResult
from intel.modules.ats import get_provider
from intel.modules.ats import providers as _ats_providers  # noqa: F401 — register
from intel.modules.detection.engine import detect_internship
from intel.modules.filtering.engine import apply_filters
from intel.modules.jobs.repository import JobRepository, crawler_runs_col
from intel.modules.companies.repository import CompanyRepository

logger = logging.getLogger("email_automation.intel.crawl")


class CrawlService:
    def __init__(
        self,
        companies: CompanyRepository | None = None,
        jobs: JobRepository | None = None,
    ):
        self.companies = companies or CompanyRepository()
        self.jobs = jobs or JobRepository()

    async def crawl_all(self, *, only_with_boards: bool = True, limit: int | None = None) -> CrawlRunResult:
        items, _ = self.companies.list(active=True, limit=limit or 1000, offset=0)
        if only_with_boards:
            items = [
                c
                for c in items
                if c.get("board_token") and c.get("ats_provider") not in (None, "unknown")
            ]

        attempted = ok = failed = 0
        fetched = new = updated = passed = 0
        errors: list[str] = []
        company_logs: list[dict[str, Any]] = []

        run_doc: dict[str, Any] = {
            "started_at": datetime.now(timezone.utc),
            "status": "running",
            "companies": len(items),
            "company_logs": [],
        }
        run_id = crawler_runs_col().insert_one(run_doc).inserted_id

        for company in items:
            attempted += 1
            provider_name = company["ats_provider"]
            token = company.get("board_token") or company.get("board_url")
            provider = get_provider(provider_name)
            entry: dict[str, Any] = {
                "company": company["name"],
                "slug": company["slug"],
                "ats": provider_name,
                "board": token,
                "status": "pending",
                "jobs_total": 0,
                "intern_found": 0,
                "passed_filter": 0,
                "samples": [],
                "error": None,
            }

            if not provider or not token:
                failed += 1
                entry["status"] = "skipped"
                entry["error"] = "no provider/token"
                errors.append(f"{company['name']}: no provider/token")
                company_logs.append(entry)
                crawler_runs_col().update_one(
                    {"_id": run_id},
                    {"$set": {"company_logs": company_logs[-200:]}},
                )
                continue

            try:
                board_token = company.get("board_token") or ""
                if company.get("board_url") and str(company["board_url"]).startswith("http"):
                    if provider_name in (
                        "workday",
                        "oracle",
                        "successfactors",
                        "rippling",
                    ):
                        board_token = company["board_url"]
                if not board_token:
                    board_token = token

                raw_jobs = await provider.list_jobs(
                    board_token=board_token,
                    company_name=company["name"],
                    company_slug=company["slug"],
                )
                ok += 1
                entry["jobs_total"] = len(raw_jobs)
                live_ids: set[str] = set()
                samples: list[dict[str, str]] = []

                for nj in raw_jobs:
                    fetched += 1
                    live_ids.add(nj.external_job_id)
                    det = detect_internship(nj.title, nj.description_text)
                    if not det.is_internship:
                        continue
                    entry["intern_found"] += 1
                    filt = apply_filters(
                        title=nj.title,
                        location_text=nj.location_text,
                        description=nj.description_text,
                        is_remote_hint=nj.is_remote,
                    )
                    doc = {
                        "company_id": company["id"],
                        "company_name": company["name"],
                        "company_slug": company["slug"],
                        "ats_provider": nj.ats_provider.value,
                        "external_job_id": nj.external_job_id,
                        "title": nj.title,
                        "apply_url": nj.apply_url,
                        "location_text": nj.location_text,
                        "is_remote": filt.is_remote
                        if filt.is_remote is not None
                        else nj.is_remote,
                        "is_india": filt.is_india,
                        "is_internship": True,
                        "grad_year_eligibility": filt.grad_year.value,
                        "season_tag": filt.season.value,
                        "filter_pass": filt.passed,
                        "filter_reasons": filt.reasons + [det.reason],
                        "role_family": det.role_family,
                        "description_text": nj.description_text,
                        "link_ok": False,
                        "source": provider_name,
                        "detection_confidence": det.confidence,
                    }
                    if filt.passed:
                        passed += 1
                        entry["passed_filter"] += 1
                        if len(samples) < 5:
                            samples.append(
                                {
                                    "title": nj.title,
                                    "url": nj.apply_url,
                                    "location": nj.location_text or "",
                                }
                            )
                    status = self.jobs.upsert_observed(doc)
                    if status == "inserted":
                        new += 1
                    else:
                        updated += 1

                entry["samples"] = samples
                entry["status"] = "ok"
                self.jobs.mark_company_jobs_closed_except(company["slug"], live_ids)

            except Exception as e:
                failed += 1
                msg = f"{company['name']} ({provider_name}/{token}): {e}"
                errors.append(msg)
                entry["status"] = "error"
                entry["error"] = str(e)[:300]
                logger.warning("Crawl failed: %s", msg)

            company_logs.append(entry)
            # Live progress for dashboard polling
            crawler_runs_col().update_one(
                {"_id": run_id},
                {
                    "$set": {
                        "company_logs": company_logs[-300:],
                        "progress": {
                            "attempted": attempted,
                            "ok": ok,
                            "failed": failed,
                            "passed": passed,
                        },
                    }
                },
            )

        result = CrawlRunResult(
            companies_attempted=attempted,
            companies_ok=ok,
            companies_failed=failed,
            jobs_fetched=fetched,
            jobs_new=new,
            jobs_updated=updated,
            jobs_passed_filter=passed,
            errors=errors[:50],
            company_logs=company_logs,
        )
        crawler_runs_col().update_one(
            {"_id": run_id},
            {
                "$set": {
                    "finished_at": datetime.now(timezone.utc),
                    "status": "done",
                    "result": result.model_dump(),
                    "company_logs": company_logs,
                }
            },
        )
        logger.info(
            "Crawl done attempted=%s ok=%s new=%s passed=%s",
            attempted,
            ok,
            new,
            passed,
        )
        return result

    def latest_runs(self, limit: int = 5) -> list[dict[str, Any]]:
        cursor = crawler_runs_col().find().sort("started_at", -1).limit(limit)
        out = []
        for doc in cursor:
            out.append(
                {
                    "id": str(doc["_id"]),
                    "status": doc.get("status"),
                    "started_at": doc.get("started_at"),
                    "finished_at": doc.get("finished_at"),
                    "companies": doc.get("companies"),
                    "progress": doc.get("progress"),
                    "result": doc.get("result"),
                    "company_logs": doc.get("company_logs") or [],
                }
            )
        return out
