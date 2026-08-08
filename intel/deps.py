"""FastAPI dependency factories for internship intel."""

from intel.modules.companies.service import CompanyService
from intel.modules.jobs.crawl_service import CrawlService
from intel.modules.jobs.repository import JobRepository
from intel.modules.jobs.verify_service import VerifyService
from intel.modules.notifications.service import NotificationService
from intel.modules.scheduler.service import SchedulerService


def get_company_service() -> CompanyService:
    return CompanyService()


def get_job_repo() -> JobRepository:
    return JobRepository()


def get_crawl_service() -> CrawlService:
    return CrawlService()


def get_verify_service() -> VerifyService:
    return VerifyService()


def get_scheduler_service() -> SchedulerService:
    return SchedulerService()


def get_notification_service() -> NotificationService:
    return NotificationService()
