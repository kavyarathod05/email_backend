"""Intel health endpoints (also available as /api/v1/health)."""

from fastapi import APIRouter

from intel.adapters.mongo import ping_mongo

router = APIRouter(tags=["intel-health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "internship_intel", "mounted_on": "email_backend"}


@router.get("/ready")
def ready() -> dict:
    mongo_ok = ping_mongo()
    return {
        "status": "ready" if mongo_ok else "degraded",
        "mongo": mongo_ok,
    }
