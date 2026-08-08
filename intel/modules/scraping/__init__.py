"""Shared politeness utilities for HTML career-page scrapers."""

from intel.modules.scraping.fetch import fetch_text
from intel.modules.scraping.robots import origin_of, robots_allowed

__all__ = ["fetch_text", "origin_of", "robots_allowed"]
