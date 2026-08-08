"""Normalized job + pipeline models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from intel.core.models.company import AtsProvider


class JobStatus(str, Enum):
    open = "open"
    closed = "closed"
    unknown = "unknown"


class GradYearEligibility(str, Enum):
    y2028 = "2028"
    other = "other"
    unknown = "unknown"


class SeasonTag(str, Enum):
    summer_2027 = "summer_2027"
    other = "other"
    unknown = "unknown"


class NormalizedJob(BaseModel):
    external_job_id: str
    ats_provider: AtsProvider
    company_slug: str
    company_name: str
    title: str
    location_text: str | None = None
    locations: list[str] = Field(default_factory=list)
    is_remote: bool | None = None
    description_text: str | None = None
    apply_url: str
    posted_at: datetime | None = None
    raw: dict | None = None


class JobOut(BaseModel):
    id: str
    company_id: str | None = None
    company_name: str
    company_slug: str
    ats_provider: str
    external_job_id: str
    title: str
    apply_url: str
    location_text: str | None = None
    is_remote: bool | None = None
    is_india: bool | None = None
    is_internship: bool = True
    grad_year_eligibility: str = "unknown"
    season_tag: str = "unknown"
    link_ok: bool = False
    status: str = "open"
    filter_pass: bool = False
    filter_reasons: list[str] = Field(default_factory=list)
    role_family: str | None = None
    match_score: float | None = None
    match_reasons: list[str] = Field(default_factory=list)
    posted_at: datetime | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    closed_at: datetime | None = None
    source: str | None = None
    tracked: bool = False
    tracked_at: datetime | None = None
    application_note: str | None = None


class JobListResponse(BaseModel):
    items: list[JobOut]
    total: int
    limit: int
    offset: int


class CrawlRunResult(BaseModel):
    companies_attempted: int
    companies_ok: int
    companies_failed: int
    jobs_fetched: int
    jobs_new: int
    jobs_updated: int
    jobs_passed_filter: int
    errors: list[str] = Field(default_factory=list)
    company_logs: list[dict] = Field(default_factory=list)


class SchedulerTickResult(BaseModel):
    crawl: CrawlRunResult
    verified: int
    newly_notified: int
    message: str
