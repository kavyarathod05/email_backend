"""Internship Link Intelligence — mounted on the same FastAPI app as outreach."""

from intel.api.v1 import api_router as intel_api_router
from intel.adapters.mongo import ensure_indexes

__all__ = ["intel_api_router", "ensure_indexes"]
