"""Verify apply URLs are live."""

from __future__ import annotations

import logging

from intel.adapters.http_client import head_ok
from intel.modules.jobs.repository import JobRepository

logger = logging.getLogger("internship_platform.verify")


class VerifyService:
    def __init__(self, jobs: JobRepository | None = None):
        self.jobs = jobs or JobRepository()

    async def verify_pending(self, limit: int = 100) -> int:
        pending = self.jobs.jobs_needing_verify(limit=limit)
        verified = 0
        for doc in pending:
            ok = await head_ok(doc["apply_url"])
            self.jobs.mark_link(doc["_id"], ok)
            if ok:
                verified += 1
            else:
                logger.info("Dead link job=%s url=%s", doc.get("title"), doc.get("apply_url"))
        return verified
