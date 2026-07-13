"""Slug / name-key helpers for company identity."""

import re


def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s or "company"


def name_key(name: str) -> str:
    """Dedupe key: lowercase alphanumeric only (Google == google)."""
    return re.sub(r"[^a-z0-9]", "", name.lower())
