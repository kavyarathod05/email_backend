"""Company domain models."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class AtsProvider(str, Enum):
    greenhouse = "greenhouse"
    lever = "lever"
    ashby = "ashby"
    workday = "workday"
    smartrecruiters = "smartrecruiters"
    teamtailor = "teamtailor"
    jobvite = "jobvite"
    workable = "workable"
    oracle = "oracle"
    successfactors = "successfactors"
    icims = "icims"
    bamboohr = "bamboohr"
    rippling = "rippling"
    # Custom career-page scrapers (config-driven; need careers_url)
    json_ld = "json_ld"
    sitemap = "sitemap"
    playwright = "playwright"
    unknown = "unknown"


# Adapters that scrape HTML career pages instead of ATS JSON APIs
CUSTOM_SCRAPE_PROVIDERS = frozenset(
    {
        AtsProvider.json_ld.value,
        AtsProvider.sitemap.value,
        AtsProvider.playwright.value,
    }
)


class EngineeringSize(str, Enum):
    xs = "xs"
    s = "s"
    m = "m"
    l = "l"
    xl = "xl"
    unknown = "unknown"


class CompanyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    website: str | None = None
    careers_url: str | None = None
    ats_provider: AtsProvider = AtsProvider.unknown
    board_token: str | None = None
    board_url: str | None = None
    country: str | None = None
    india_hiring: bool | None = None
    remote_hiring: bool | None = None
    internship_history: bool | None = None
    new_grad_history: bool | None = None
    engineering_size: EngineeringSize = EngineeringSize.unknown
    priority: int = Field(default=3, ge=1, le=5)
    active: bool = True
    source: str | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class CompanyCreate(CompanyBase):
    slug: str | None = None


class CompanyUpdate(BaseModel):
    name: str | None = None
    website: str | None = None
    careers_url: str | None = None
    ats_provider: AtsProvider | None = None
    board_token: str | None = None
    board_url: str | None = None
    country: str | None = None
    india_hiring: bool | None = None
    remote_hiring: bool | None = None
    internship_history: bool | None = None
    new_grad_history: bool | None = None
    engineering_size: EngineeringSize | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    active: bool | None = None
    source: str | None = None


class CompanyOut(CompanyBase):
    id: str
    slug: str
    created_at: datetime
    updated_at: datetime
    verified_at: datetime | None = None

    model_config = {"from_attributes": True}


class CompanyImportItem(BaseModel):
    name: str
    website: str | None = None
    careers_url: str | None = None
    ats_provider: AtsProvider | None = None
    board_token: str | None = None
    priority: int | None = Field(default=None, ge=1, le=5)


class CompanyImportRequest(BaseModel):
    """Import companies from JSON list or newline-separated names in `text`."""

    companies: list[CompanyImportItem] | None = None
    text: str | None = None  # one company name per line
    source: str = "manual_import"


class CompanyImportResult(BaseModel):
    inserted: int
    updated: int
    skipped: int
    total_in_db: int
    details: list[dict[str, Any]] = Field(default_factory=list)


class CompanyListResponse(BaseModel):
    items: list[CompanyOut]
    total: int
    limit: int
    offset: int
