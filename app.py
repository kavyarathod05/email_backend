"""
Email Outreach Automation + Internship Link Intelligence.

Same Render service. Outreach routes unchanged; intel under /api/v1/*.
"""
import os

import uvicorn
from fastapi import Request
from fastapi.responses import JSONResponse

from config import create_app, logger

from routes.health import router as health_router
from routes.templates import router as templates_router
from routes.recruiters import router as recruiters_router
from routes.tracking import router as tracking_router
from routes.email import router as email_router
from routes.dashboard import router as dashboard_router
from routes.auth import router as auth_router
from routes.webhook import router as webhook_router

from intel import intel_api_router, ensure_indexes
from intel.core.errors import AppError
from services.scheduler import start_scheduler, stop_scheduler

app = create_app()

app.include_router(health_router)
app.include_router(templates_router)
app.include_router(recruiters_router)
app.include_router(tracking_router)
app.include_router(email_router)
app.include_router(dashboard_router)
app.include_router(auth_router)
app.include_router(webhook_router)

# Internship discovery (companies, jobs, crawlers) — same process
app.include_router(intel_api_router)


@app.exception_handler(AppError)
async def intel_app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code, "message": exc.message},
    )


@app.on_event("startup")
def startup_event():
    start_scheduler()
    try:
        ensure_indexes()
    except Exception as e:
        logger.warning("Intel index setup skipped/failed: %s", e)


@app.on_event("shutdown")
def shutdown_event():
    stop_scheduler()


if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
