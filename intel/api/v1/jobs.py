"""Jobs + crawler + scheduler HTTP API."""

from fastapi import APIRouter, Depends, Header, Query

from intel.config import get_settings
from intel.core.errors import AppError
from intel.core.models.job import CrawlRunResult, JobListResponse, JobOut, SchedulerTickResult
from intel.deps import get_crawl_service, get_job_repo, get_scheduler_service, get_verify_service
from intel.modules.jobs.crawl_service import CrawlService
from intel.modules.jobs.repository import JobRepository
from intel.modules.jobs.verify_service import VerifyService
from intel.modules.scheduler.service import SchedulerService

router = APIRouter(tags=["jobs"])


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    new_today: bool = Query(False),
    company: str | None = Query(None),
    filter_pass: bool | None = Query(True),
    link_ok: bool | None = Query(None, description="Default: no filter; set true for verified only"),
    status: str = Query("open"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    repo: JobRepository = Depends(get_job_repo),
) -> JobListResponse:
    items, total = repo.list_jobs(
        new_today=new_today,
        company=company,
        filter_pass=filter_pass,
        link_ok=link_ok,
        status=status,
        limit=limit,
        offset=offset,
    )
    return JobListResponse(
        items=[JobOut(**i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/jobs/today", response_model=JobListResponse)
def todays_jobs(
    limit: int = Query(100, ge=1, le=500),
    repo: JobRepository = Depends(get_job_repo),
) -> JobListResponse:
    items, total = repo.list_jobs(
        new_today=True,
        filter_pass=True,
        link_ok=None,
        status="open",
        limit=limit,
        offset=0,
    )
    return JobListResponse(
        items=[JobOut(**i) for i in items],
        total=total,
        limit=limit,
        offset=0,
    )


@router.get("/crawlers/providers", response_model=dict)
def list_providers() -> dict:
    from intel.modules.ats import all_providers
    import intel.modules.ats  # noqa: F401

    return {
        "providers": sorted(p.value for p in all_providers().keys()),
        "count": len(all_providers()),
    }


@router.get("/crawlers/runs")
def list_crawl_runs(
    limit: int = Query(5, ge=1, le=20),
    svc: CrawlService = Depends(get_crawl_service),
) -> dict:
    """Latest crawl runs with per-company logs for the dashboard."""
    return {"runs": svc.latest_runs(limit=limit)}


@router.post("/crawlers/run", response_model=CrawlRunResult)
async def run_crawlers(
    svc: CrawlService = Depends(get_crawl_service),
) -> CrawlRunResult:
    return await svc.crawl_all()


@router.post("/crawlers/verify", response_model=dict)
async def verify_links(
    limit: int = Query(100, ge=1, le=500),
    svc: VerifyService = Depends(get_verify_service),
) -> dict:
    n = await svc.verify_pending(limit=limit)
    return {"verified_ok": n}


@router.post("/scheduler/tick", response_model=SchedulerTickResult)
async def scheduler_tick(
    x_scheduler_secret: str | None = Header(default=None),
    svc: SchedulerService = Depends(get_scheduler_service),
) -> SchedulerTickResult:
    settings = get_settings()
    if settings.scheduler_secret and x_scheduler_secret != settings.scheduler_secret:
        raise AppError("Unauthorized", code="unauthorized", status_code=401)
    return await svc.tick()
