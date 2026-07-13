"""Scheduler tick — crawl → verify → notify."""

from __future__ import annotations

import logging

from intel.core.models.job import SchedulerTickResult
from intel.modules.jobs.crawl_service import CrawlService
from intel.modules.jobs.verify_service import VerifyService
from intel.modules.notifications.service import NotificationService

logger = logging.getLogger("internship_platform.scheduler")


class SchedulerService:
    def __init__(self):
        self.crawl = CrawlService()
        self.verify = VerifyService()
        self.notify = NotificationService()

    async def tick(self) -> SchedulerTickResult:
        crawl = await self.crawl.crawl_all()
        verified = await self.verify.verify_pending(limit=200)
        # Notify even if link check pending for brand-new filter_pass (still prefer link_ok)
        newly = await self.notify.notify_new_jobs(require_link_ok=False)
        msg = (
            f"crawl ok={crawl.companies_ok}/{crawl.companies_attempted} "
            f"new_jobs={crawl.jobs_new} passed={crawl.jobs_passed_filter} "
            f"verified={verified} notified={newly}"
        )
        logger.info(msg)
        return SchedulerTickResult(
            crawl=crawl,
            verified=verified,
            newly_notified=newly,
            message=msg,
        )
