"""Crawl companies → detect → filter → upsert jobs (batched + concurrent)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

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

    def _board_companies(self, *, offset: int = 0, limit: int | None = None) -> tuple[list[dict], int]:
        # Prefer crawlable (ATS boards + custom scrapers); fall back to boards-only
        return self.companies.list(
            active=True,
            crawlable=True,
            limit=limit or 5000,
            offset=offset,
        )

    async def _crawl_one_company(
        self,
        company: dict[str, Any],
        *,
        require_india: bool = True,
        allow_remote: bool = False,
    ) -> tuple[dict[str, Any], dict[str, int]]:
        """Returns (log_entry, counters dict)."""
        counters = {
            "ok": 0,
            "failed": 0,
            "fetched": 0,
            "new": 0,
            "updated": 0,
            "passed": 0,
            "intern_found": 0,
        }
        provider_name = company["ats_provider"]
        custom = provider_name in ("json_ld", "sitemap", "playwright")
        token = (
            (company.get("careers_url") or company.get("board_url") or company.get("board_token"))
            if custom
            else (company.get("board_token") or company.get("board_url"))
        )
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
            counters["failed"] = 1
            entry["status"] = "skipped"
            entry["error"] = "no provider/token" if not custom else "no careers_url"
            return entry, counters

        try:
            board_token = company.get("board_token") or ""
            if custom:
                board_token = (
                    company.get("careers_url")
                    or company.get("board_url")
                    or board_token
                )
            elif company.get("board_url") and str(company["board_url"]).startswith("http"):
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
            counters["ok"] = 1
            entry["jobs_total"] = len(raw_jobs)
            live_ids: set[str] = set()
            samples: list[dict[str, str]] = []

            for nj in raw_jobs:
                counters["fetched"] += 1
                live_ids.add(nj.external_job_id)
                det = detect_internship(nj.title, nj.description_text)
                if not det.is_internship:
                    continue
                counters["intern_found"] += 1
                entry["intern_found"] += 1
                filt = apply_filters(
                    title=nj.title,
                    location_text=nj.location_text,
                    description=nj.description_text,
                    is_remote_hint=nj.is_remote,
                    require_india=require_india,
                    allow_remote=allow_remote,
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
                    "posted_at": nj.posted_at,
                }
                if filt.passed:
                    counters["passed"] += 1
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
                    counters["new"] += 1
                else:
                    counters["updated"] += 1

            entry["samples"] = samples
            entry["status"] = "ok"
            self.jobs.mark_company_jobs_closed_except(company["slug"], live_ids)

        except Exception as e:
            counters["failed"] = 1
            entry["status"] = "error"
            entry["error"] = str(e)[:300]
            logger.warning("Crawl failed: %s (%s): %s", company["name"], provider_name, e)

        return entry, counters

    async def crawl_all(
        self,
        *,
        only_with_boards: bool = True,
        limit: int | None = None,
        offset: int = 0,
        concurrency: int = 6,
        require_india: bool = True,
        allow_remote: bool = False,
        run_id: ObjectId | None = None,
        finalize: bool = True,
    ) -> CrawlRunResult:
        if only_with_boards:
            items, total_boards = self._board_companies(offset=offset, limit=limit)
        else:
            items, total_boards = self.companies.list(
                active=True, limit=limit or 1000, offset=offset
            )

        attempted = ok = failed = 0
        fetched = new = updated = passed = 0
        errors: list[str] = []
        company_logs: list[dict[str, Any]] = []

        if run_id is None:
            run_doc: dict[str, Any] = {
                "started_at": datetime.now(timezone.utc),
                "status": "running",
                "companies": total_boards if limit is None else len(items),
                "offset": offset,
                "limit": limit,
                "company_logs": [],
            }
            run_id = crawler_runs_col().insert_one(run_doc).inserted_id
        else:
            crawler_runs_col().update_one(
                {"_id": run_id},
                {
                    "$set": {
                        "status": "running",
                        "companies": total_boards,
                        "offset": offset,
                    }
                },
            )

        sem = asyncio.Semaphore(max(1, min(concurrency, 12)))
        lock = asyncio.Lock()

        async def worker(company: dict[str, Any]) -> None:
            nonlocal attempted, ok, failed, fetched, new, updated, passed
            async with sem:
                entry, counters = await self._crawl_one_company(
                    company,
                    require_india=require_india,
                    allow_remote=allow_remote,
                )
            async with lock:
                attempted += 1
                ok += counters["ok"]
                failed += counters["failed"]
                fetched += counters["fetched"]
                new += counters["new"]
                updated += counters["updated"]
                passed += counters["passed"]
                if entry.get("error") and entry["status"] == "error":
                    errors.append(f"{company['name']}: {entry['error']}")
                company_logs.append(entry)
                crawler_runs_col().update_one(
                    {"_id": run_id},
                    {
                        "$set": {
                            "company_logs": company_logs[-400:],
                            "progress": {
                                "attempted": attempted,
                                "ok": ok,
                                "failed": failed,
                                "passed": passed,
                                "total": len(items),
                                "offset": offset,
                            },
                        }
                    },
                )

        await asyncio.gather(*(worker(c) for c in items))

        # Keep logs roughly name-ordered for readability
        company_logs.sort(key=lambda e: (e.get("company") or "").lower())

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
        update: dict[str, Any] = {
            "company_logs": company_logs,
            "progress": {
                "attempted": attempted,
                "ok": ok,
                "failed": failed,
                "passed": passed,
                "total": len(items),
                "offset": offset,
            },
            "last_batch_result": result.model_dump(),
        }
        if finalize:
            update["finished_at"] = datetime.now(timezone.utc)
            update["status"] = "done"
            update["result"] = result.model_dump()
        else:
            update["status"] = "running"
        crawler_runs_col().update_one({"_id": run_id}, {"$set": update})
        logger.info(
            "Crawl done attempted=%s ok=%s new=%s passed=%s offset=%s finalize=%s",
            attempted,
            ok,
            new,
            passed,
            offset,
            finalize,
        )
        return result

    async def crawl_all_batches(
        self,
        *,
        batch_size: int = 30,
        concurrency: int = 6,
        require_india: bool = True,
        allow_remote: bool = False,
        run_id: ObjectId | None = None,
    ) -> CrawlRunResult:
        """Walk every company with a board, in batches, until finished."""
        _, total = self._board_companies(offset=0, limit=1)
        if run_id is None:
            run_id = ObjectId(self.start_run(total=total))
        else:
            crawler_runs_col().update_one(
                {"_id": run_id},
                {"$set": {"status": "running", "companies": total}},
            )

        all_logs: list[dict[str, Any]] = []
        tot_ok = tot_failed = tot_fetched = tot_new = tot_updated = tot_passed = tot_attempted = 0
        all_errors: list[str] = []
        offset = 0

        while offset < total:
            items, _ = self._board_companies(offset=offset, limit=batch_size)
            if not items:
                break

            batch = await self.crawl_all(
                limit=batch_size,
                offset=offset,
                concurrency=concurrency,
                require_india=require_india,
                allow_remote=allow_remote,
                run_id=run_id,
                finalize=False,
            )
            all_logs.extend(batch.company_logs or [])
            tot_attempted += batch.companies_attempted
            tot_ok += batch.companies_ok
            tot_failed += batch.companies_failed
            tot_fetched += batch.jobs_fetched
            tot_new += batch.jobs_new
            tot_updated += batch.jobs_updated
            tot_passed += batch.jobs_passed_filter
            all_errors.extend(batch.errors or [])

            crawler_runs_col().update_one(
                {"_id": run_id},
                {
                    "$set": {
                        "status": "running",
                        "company_logs": all_logs[-500:],
                        "progress": {
                            "attempted": tot_attempted,
                            "ok": tot_ok,
                            "failed": tot_failed,
                            "passed": tot_passed,
                            "total": total,
                            "offset": offset,
                        },
                    }
                },
            )
            offset += batch_size

        result = CrawlRunResult(
            companies_attempted=tot_attempted,
            companies_ok=tot_ok,
            companies_failed=tot_failed,
            jobs_fetched=tot_fetched,
            jobs_new=tot_new,
            jobs_updated=tot_updated,
            jobs_passed_filter=tot_passed,
            errors=all_errors[:50],
            company_logs=all_logs,
        )
        crawler_runs_col().update_one(
            {"_id": run_id},
            {
                "$set": {
                    "finished_at": datetime.now(timezone.utc),
                    "status": "done",
                    "result": result.model_dump(),
                    "company_logs": all_logs[-500:],
                    "progress": {
                        "attempted": tot_attempted,
                        "ok": tot_ok,
                        "failed": tot_failed,
                        "passed": tot_passed,
                        "total": total,
                        "offset": offset,
                    },
                }
            },
        )
        return result

    def start_run(self, *, total: int | None = None) -> str:
        _, boards = self._board_companies(offset=0, limit=1)
        doc = {
            "started_at": datetime.now(timezone.utc),
            "status": "queued",
            "companies": total if total is not None else boards,
            "mode": "all_batches",
            "company_logs": [],
            "progress": {
                "attempted": 0,
                "ok": 0,
                "failed": 0,
                "passed": 0,
                "total": total if total is not None else boards,
            },
        }
        return str(crawler_runs_col().insert_one(doc).inserted_id)

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
                    "mode": doc.get("mode"),
                    "progress": doc.get("progress"),
                    "result": doc.get("result"),
                    "company_logs": doc.get("company_logs") or [],
                }
            )
        return out
