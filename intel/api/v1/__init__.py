from fastapi import APIRouter

from intel.api.v1 import companies, health, jobs

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(companies.router)
api_router.include_router(jobs.router)
api_router.include_router(health.router)
