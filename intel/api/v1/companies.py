"""Company Intelligence API."""

from fastapi import APIRouter, Depends, Query

from intel.core.errors import AppError
from intel.core.models.company import (
    CompanyCreate,
    CompanyImportRequest,
    CompanyImportResult,
    CompanyListResponse,
    CompanyOut,
    CompanyUpdate,
)
from intel.deps import get_company_service
from intel.modules.companies.service import CompanyService

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=CompanyListResponse)
def list_companies(
    q: str | None = Query(None, description="Search name/slug"),
    active: bool | None = Query(True),
    ats_provider: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    svc: CompanyService = Depends(get_company_service),
) -> CompanyListResponse:
    return svc.list_companies(
        q=q, active=active, ats_provider=ats_provider, limit=limit, offset=offset
    )


@router.post("/import", response_model=CompanyImportResult)
def import_companies(
    body: CompanyImportRequest,
    svc: CompanyService = Depends(get_company_service),
) -> CompanyImportResult:
    if not body.companies and not body.text:
        raise AppError("Provide `companies` and/or `text`", code="validation_error")
    return svc.import_companies(body)


@router.post("/seed", response_model=CompanyImportResult)
def seed_companies(
    svc: CompanyService = Depends(get_company_service),
) -> CompanyImportResult:
    """Load bundled seed (deduped top_tier list). Safe to re-run (upsert)."""
    return svc.seed_from_file()


@router.get("/{company_id}", response_model=CompanyOut)
def get_company(
    company_id: str,
    svc: CompanyService = Depends(get_company_service),
) -> CompanyOut:
    return svc.get(company_id)


@router.post("", response_model=CompanyOut, status_code=201)
def create_company(
    body: CompanyCreate,
    svc: CompanyService = Depends(get_company_service),
) -> CompanyOut:
    return svc.create(body)


@router.patch("/{company_id}", response_model=CompanyOut)
def update_company(
    company_id: str,
    body: CompanyUpdate,
    svc: CompanyService = Depends(get_company_service),
) -> CompanyOut:
    return svc.update(company_id, body)


@router.delete("/{company_id}", response_model=CompanyOut)
def deactivate_company(
    company_id: str,
    svc: CompanyService = Depends(get_company_service),
) -> CompanyOut:
    return svc.deactivate(company_id)
