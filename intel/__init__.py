"""Internship Link Intelligence — mounted on the same FastAPI app as outreach."""

from __future__ import annotations

from typing import Any

__all__ = ["intel_api_router", "ensure_indexes"]


def __getattr__(name: str) -> Any:
    if name == "intel_api_router":
        from intel.api.v1 import api_router as intel_api_router

        return intel_api_router
    if name == "ensure_indexes":
        from intel.adapters.mongo import ensure_indexes

        return ensure_indexes
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
