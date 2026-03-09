"""
Email Outreach Automation — Application Entrypoint.

All business logic lives in the routes/ and services/ packages.
This file only creates the app, mounts routers, and starts the server.
"""
import os
import uvicorn

from config import create_app

# Create the configured FastAPI app (MongoDB + CORS already set up)
app = create_app()

# Register all route modules
from routes.health import router as health_router
from routes.templates import router as templates_router
from routes.recruiters import router as recruiters_router
from routes.tracking import router as tracking_router
from routes.email import router as email_router
from routes.dashboard import router as dashboard_router

app.include_router(health_router)
app.include_router(templates_router)
app.include_router(recruiters_router)
app.include_router(tracking_router)
app.include_router(email_router)
app.include_router(dashboard_router)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)