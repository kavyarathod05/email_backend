"""Company intelligence service — seed + import + CRUD."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from intel.core.errors import NotFoundError
from intel.core.models.company import (
    CompanyCreate,
    CompanyImportRequest,
    CompanyImportResult,
    CompanyListResponse,
    CompanyOut,
    CompanyUpdate,
)
from intel.modules.companies.repository import CompanyRepository

logger = logging.getLogger("internship_platform.companies")

SEED_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "seeds" / "companies_seed.json"
)


class CompanyService:
    def __init__(self, repo: CompanyRepository | None = None):
        self.repo = repo or CompanyRepository()

    def list_companies(
        self,
        *,
        q: str | None = None,
        active: bool | None = True,
        ats_provider: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> CompanyListResponse:
        items, total = self.repo.list(
            q=q,
            active=active,
            ats_provider=ats_provider,
            limit=min(limit, 500),
            offset=max(offset, 0),
        )
        return CompanyListResponse(
            items=[CompanyOut(**i) for i in items],
            total=total,
            limit=limit,
            offset=offset,
        )

    def get(self, company_id: str) -> CompanyOut:
        return CompanyOut(**self.repo.get_by_id(company_id))

    def create(self, body: CompanyCreate) -> CompanyOut:
        data = body.model_dump()
        if body.slug:
            data["slug"] = body.slug
        else:
            data.pop("slug", None)
        # enum → value
        data["ats_provider"] = body.ats_provider.value
        data["engineering_size"] = body.engineering_size.value
        return CompanyOut(**self.repo.insert(data))

    def update(self, company_id: str, body: CompanyUpdate) -> CompanyOut:
        patch = body.model_dump(exclude_unset=True)
        if "ats_provider" in patch and patch["ats_provider"] is not None:
            patch["ats_provider"] = patch["ats_provider"].value
        if "engineering_size" in patch and patch["engineering_size"] is not None:
            patch["engineering_size"] = patch["engineering_size"].value
        return CompanyOut(**self.repo.update(company_id, patch))

    def deactivate(self, company_id: str) -> CompanyOut:
        return CompanyOut(**self.repo.soft_deactivate(company_id))

    def import_companies(self, body: CompanyImportRequest) -> CompanyImportResult:
        rows: list[dict[str, Any]] = []
        details: list[dict[str, Any]] = []

        if body.companies:
            for item in body.companies:
                row = item.model_dump(exclude_none=True)
                if "ats_provider" in row:
                    row["ats_provider"] = row["ats_provider"].value
                row.setdefault("source", body.source)
                rows.append(row)

        if body.text:
            for line in body.text.splitlines():
                name = line.strip()
                if not name or name.startswith("#"):
                    continue
                rows.append({"name": name, "source": body.source, "active": True})

        inserted = updated = skipped = 0
        for row in rows:
            row.setdefault("active", True)
            row.setdefault("ats_provider", "unknown")
            row.setdefault("engineering_size", "unknown")
            row.setdefault("priority", 3)
            status = self.repo.upsert_by_name_key(row)
            if status == "inserted":
                inserted += 1
            elif status == "updated":
                updated += 1
            else:
                skipped += 1
            details.append({"name": row["name"], "status": status})

        total = self.repo.count()
        logger.info(
            "Import finished inserted=%s updated=%s skipped=%s total=%s",
            inserted,
            updated,
            skipped,
            total,
        )
        return CompanyImportResult(
            inserted=inserted,
            updated=updated,
            skipped=skipped,
            total_in_db=total,
            details=details[:200],  # cap response size
        )

    def seed_from_file(self, path: Path | None = None) -> CompanyImportResult:
        seed_path = path or SEED_PATH
        if not seed_path.exists():
            raise NotFoundError(f"Seed file not found: {seed_path}")
        raw = json.loads(seed_path.read_text(encoding="utf-8"))
        details: list[dict[str, Any]] = []
        inserted = updated = skipped = 0
        for row in raw:
            payload = {
                "name": row["name"],
                "website": row.get("website"),
                "careers_url": row.get("careers_url"),
                "ats_provider": row.get("ats_provider", "unknown"),
                "board_token": row.get("board_token"),
                "priority": row.get("priority", 3),
                "active": row.get("active", True),
                "source": row.get("source", "companies_seed.json"),
                "engineering_size": "unknown",
            }
            try:
                status = self.repo.upsert_by_name_key(payload)
            except Exception as e:
                logger.warning("Seed skip %s: %s", payload["name"], e)
                skipped += 1
                details.append({"name": payload["name"], "status": "error", "error": str(e)})
                continue
            if status == "inserted":
                inserted += 1
            elif status == "updated":
                updated += 1
            else:
                skipped += 1
            details.append({"name": payload["name"], "status": status})

        total = self.repo.count()
        logger.info(
            "Seed finished inserted=%s updated=%s skipped=%s total=%s path=%s",
            inserted,
            updated,
            skipped,
            total,
            seed_path,
        )
        return CompanyImportResult(
            inserted=inserted,
            updated=updated,
            skipped=skipped,
            total_in_db=total,
            details=details[:200],
        )
