"""Company Mongo repository."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from intel.adapters.mongo import companies_col
from intel.core.errors import ConflictError, NotFoundError
from intel.modules.companies.utils import name_key, slugify


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "name": doc["name"],
        "slug": doc["slug"],
        "website": doc.get("website"),
        "careers_url": doc.get("careers_url"),
        "ats_provider": doc.get("ats_provider", "unknown"),
        "board_token": doc.get("board_token"),
        "board_url": doc.get("board_url"),
        "country": doc.get("country"),
        "india_hiring": doc.get("india_hiring"),
        "remote_hiring": doc.get("remote_hiring"),
        "internship_history": doc.get("internship_history"),
        "new_grad_history": doc.get("new_grad_history"),
        "engineering_size": doc.get("engineering_size", "unknown"),
        "priority": doc.get("priority", 3),
        "active": doc.get("active", True),
        "source": doc.get("source"),
        "created_at": doc["created_at"],
        "updated_at": doc["updated_at"],
        "verified_at": doc.get("verified_at"),
    }


class CompanyRepository:
    def __init__(self, collection: Collection | None = None):
        self.col = collection if collection is not None else companies_col()

    def count(self, *, active: bool | None = None) -> int:
        q: dict[str, Any] = {}
        if active is not None:
            q["active"] = active
        return self.col.count_documents(q)

    def list(
        self,
        *,
        q: str | None = None,
        active: bool | None = None,
        ats_provider: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        filt: dict[str, Any] = {}
        if active is not None:
            filt["active"] = active
        if ats_provider:
            filt["ats_provider"] = ats_provider
        if q:
            filt["$or"] = [
                {"name": {"$regex": q, "$options": "i"}},
                {"slug": {"$regex": q, "$options": "i"}},
            ]
        total = self.col.count_documents(filt)
        cursor = (
            self.col.find(filt)
            .sort([("priority", -1), ("name", 1)])
            .skip(offset)
            .limit(limit)
        )
        return [_serialize(d) for d in cursor], total

    def get_by_id(self, company_id: str) -> dict[str, Any]:
        if not ObjectId.is_valid(company_id):
            raise NotFoundError("Company not found")
        doc = self.col.find_one({"_id": ObjectId(company_id)})
        if not doc:
            raise NotFoundError("Company not found")
        return _serialize(doc)

    def get_by_slug(self, slug: str) -> dict[str, Any] | None:
        doc = self.col.find_one({"slug": slug})
        return _serialize(doc) if doc else None

    def insert(self, data: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        slug = data.get("slug") or slugify(data["name"])
        doc = {
            **data,
            "slug": slug,
            "name_key": name_key(data["name"]),
            "created_at": now,
            "updated_at": now,
            "verified_at": data.get("verified_at"),
        }
        # Resolve slug collisions by suffix
        base_slug = slug
        for i in range(0, 50):
            candidate = base_slug if i == 0 else f"{base_slug}-{i}"
            doc["slug"] = candidate
            try:
                result = self.col.insert_one(doc)
                doc["_id"] = result.inserted_id
                return _serialize(doc)
            except DuplicateKeyError as e:
                # unique name_key conflict
                if "name_key" in str(e):
                    raise ConflictError(f"Company already exists: {data['name']}") from e
                continue
        raise ConflictError(f"Could not allocate slug for {data['name']}")

    def upsert_by_name_key(self, data: dict[str, Any], *, overwrite_empty: bool = True) -> str:
        """
        Insert or update by name_key.
        Returns: 'inserted' | 'updated' | 'skipped'
        """
        nk = name_key(data["name"])
        existing = self.col.find_one({"name_key": nk})
        now = _now()

        if existing is None:
            payload = {**data}
            payload.pop("slug", None)
            try:
                self.insert(payload)
                return "inserted"
            except ConflictError:
                # Lost race or leftover unique key — treat as update path
                existing = self.col.find_one({"name_key": nk})
                if existing is None:
                    return "skipped"
            except Exception:
                existing = self.col.find_one({"name_key": nk})
                if existing is None:
                    return "skipped"

        updates: dict[str, Any] = {"updated_at": now}
        for field in (
            "website",
            "careers_url",
            "ats_provider",
            "board_token",
            "board_url",
            "country",
            "india_hiring",
            "remote_hiring",
            "internship_history",
            "new_grad_history",
            "engineering_size",
            "priority",
            "active",
            "source",
        ):
            new_val = data.get(field)
            if new_val is None:
                continue
            old_val = existing.get(field)
            if overwrite_empty:
                if old_val in (None, "", "unknown") or field in ("priority", "source", "active"):
                    if new_val != old_val:
                        updates[field] = new_val
            elif new_val != old_val:
                updates[field] = new_val

        if " " in data["name"] and " " not in existing.get("name", ""):
            updates["name"] = data["name"]

        if len(updates) == 1:  # only updated_at
            return "skipped"

        self.col.update_one({"_id": existing["_id"]}, {"$set": updates})
        return "updated"

    def update(self, company_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        if not ObjectId.is_valid(company_id):
            raise NotFoundError("Company not found")
        patch = {k: v for k, v in patch.items() if v is not None}
        if not patch:
            return self.get_by_id(company_id)
        if "name" in patch:
            patch["name_key"] = name_key(patch["name"])
        patch["updated_at"] = _now()
        try:
            result = self.col.find_one_and_update(
                {"_id": ObjectId(company_id)},
                {"$set": patch},
                return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError as e:
            raise ConflictError("Company name conflicts with an existing record") from e
        if not result:
            raise NotFoundError("Company not found")
        return _serialize(result)

    def soft_deactivate(self, company_id: str) -> dict[str, Any]:
        return self.update(company_id, {"active": False})
