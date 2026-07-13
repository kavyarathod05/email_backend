"""Job persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.collection import Collection

from intel.adapters.mongo import get_db


def _now() -> datetime:
    return datetime.now(timezone.utc)


def jobs_col(db=None) -> Collection:
    return (db or get_db())["jobs"]


def crawler_runs_col(db=None) -> Collection:
    return (db or get_db())["crawler_runs"]


def notifications_col(db=None) -> Collection:
    return (db or get_db())["notifications_log"]


def ensure_job_indexes(db=None) -> None:
    col = jobs_col(db)
    col.create_index(
        [("ats_provider", ASCENDING), ("external_job_id", ASCENDING)],
        unique=True,
        name="uniq_provider_external",
    )
    col.create_index(
        [("filter_pass", ASCENDING), ("status", ASCENDING), ("first_seen_at", DESCENDING)],
        name="idx_pass_status_seen",
    )
    col.create_index([("link_ok", ASCENDING), ("filter_pass", ASCENDING)], name="idx_link_pass")
    col.create_index([("company_slug", ASCENDING)], name="idx_company_slug")
    notifications_col(db).create_index(
        [("dedupe_key", ASCENDING)], unique=True, name="uniq_dedupe"
    )
    crawler_runs_col(db).create_index([("started_at", DESCENDING)], name="idx_run_started")


def _serialize(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "company_id": doc.get("company_id"),
        "company_name": doc["company_name"],
        "company_slug": doc["company_slug"],
        "ats_provider": doc["ats_provider"],
        "external_job_id": doc["external_job_id"],
        "title": doc["title"],
        "apply_url": doc["apply_url"],
        "location_text": doc.get("location_text"),
        "is_remote": doc.get("is_remote"),
        "is_india": doc.get("is_india"),
        "is_internship": doc.get("is_internship", True),
        "grad_year_eligibility": doc.get("grad_year_eligibility", "unknown"),
        "season_tag": doc.get("season_tag", "unknown"),
        "link_ok": doc.get("link_ok", False),
        "status": doc.get("status", "open"),
        "filter_pass": doc.get("filter_pass", False),
        "filter_reasons": doc.get("filter_reasons", []),
        "role_family": doc.get("role_family"),
        "first_seen_at": doc["first_seen_at"],
        "last_seen_at": doc["last_seen_at"],
        "closed_at": doc.get("closed_at"),
        "source": doc.get("source"),
    }


class JobRepository:
    def __init__(self, collection: Collection | None = None):
        self.col = collection if collection is not None else jobs_col()

    def upsert_observed(self, data: dict[str, Any]) -> str:
        """Returns inserted|updated."""
        now = _now()
        key = {
            "ats_provider": data["ats_provider"],
            "external_job_id": data["external_job_id"],
        }
        existing = self.col.find_one(key)
        if existing is None:
            doc = {
                **data,
                "first_seen_at": now,
                "last_seen_at": now,
                "status": "open",
                "closed_at": None,
            }
            self.col.insert_one(doc)
            return "inserted"

        updates = {
            "last_seen_at": now,
            "status": "open",
            "closed_at": None,
            "title": data["title"],
            "apply_url": data["apply_url"],
            "location_text": data.get("location_text"),
            "is_remote": data.get("is_remote"),
            "is_india": data.get("is_india"),
            "is_internship": data.get("is_internship"),
            "grad_year_eligibility": data.get("grad_year_eligibility"),
            "season_tag": data.get("season_tag"),
            "filter_pass": data.get("filter_pass"),
            "filter_reasons": data.get("filter_reasons", []),
            "role_family": data.get("role_family"),
            "description_text": data.get("description_text"),
            "company_name": data.get("company_name"),
            "company_id": data.get("company_id"),
        }
        self.col.update_one({"_id": existing["_id"]}, {"$set": updates})
        return "updated"

    def list_jobs(
        self,
        *,
        new_today: bool = False,
        filter_pass: bool | None = True,
        link_ok: bool | None = True,
        status: str = "open",
        company: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        filt: dict[str, Any] = {}
        if status:
            filt["status"] = status
        if filter_pass is not None:
            filt["filter_pass"] = filter_pass
        if link_ok is not None:
            filt["link_ok"] = link_ok
        if company:
            filt["$or"] = [
                {"company_name": {"$regex": company, "$options": "i"}},
                {"company_slug": {"$regex": company, "$options": "i"}},
            ]
        if new_today:
            start = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            filt["first_seen_at"] = {"$gte": start}

        total = self.col.count_documents(filt)
        cursor = (
            self.col.find(filt)
            .sort([("first_seen_at", DESCENDING)])
            .skip(offset)
            .limit(limit)
        )
        return [_serialize(d) for d in cursor], total

    def jobs_needing_verify(self, limit: int = 100) -> list[dict[str, Any]]:
        cursor = self.col.find(
            {"filter_pass": True, "status": "open", "link_ok": {"$ne": True}}
        ).limit(limit)
        return list(cursor)

    def mark_link(self, job_id: ObjectId, ok: bool) -> None:
        self.col.update_one({"_id": job_id}, {"$set": {"link_ok": ok}})

    def mark_missing_closed(self, seen_keys: set[tuple[str, str]], provider: str | None = None) -> int:
        """Mark open jobs not seen in this crawl as closed (optional per provider)."""
        # Conservative: only close when we crawled that company's board in this run —
        # handled at service layer with company_slug scope instead.
        return 0

    def mark_company_jobs_closed_except(
        self, company_slug: str, live_external_ids: set[str]
    ) -> int:
        now = _now()
        q: dict[str, Any] = {
            "company_slug": company_slug,
            "status": "open",
        }
        if live_external_ids:
            q["external_job_id"] = {"$nin": list(live_external_ids)}
        result = self.col.update_many(
            q,
            {"$set": {"status": "closed", "closed_at": now}},
        )
        return result.modified_count
