"""Rule-based internship preference ranker (soft score after hard filters)."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any


DEFAULT_MUST_KEYWORDS = (
    "software",
    "sde",
    "swe",
    "backend",
    "frontend",
    "full stack",
    "fullstack",
    "platform",
    "infrastructure",
    "ml",
    "machine learning",
    "ai engineer",
    "data engineer",
    "security",
    "systems",
    "cloud",
    "llm",
    "research engineer",
)

DEFAULT_BOOST_KEYWORDS = (
    "india",
    "bangalore",
    "bengaluru",
    "hyderabad",
    "pune",
    "mumbai",
    "delhi",
    "gurugram",
    "gurgaon",
    "remote india",
    "2028",
    "summer 2027",
)

DEFAULT_PENALTY_KEYWORDS = (
    "phd",
    "quant",
    "trading",
    "hft",
    "marketing",
    "sales",
    "finance intern",
)


@dataclass
class PreferenceProfile:
    must_keywords: tuple[str, ...] = DEFAULT_MUST_KEYWORDS
    boost_keywords: tuple[str, ...] = DEFAULT_BOOST_KEYWORDS
    penalty_keywords: tuple[str, ...] = DEFAULT_PENALTY_KEYWORDS
    prefer_india: bool = True
    prefer_role_families: tuple[str, ...] = (
        "swe",
        "sde",
        "backend",
        "frontend",
        "fullstack",
        "ml",
        "ai_engineer",
        "llm",
        "data_engineer",
        "platform",
        "infrastructure",
        "security",
        "systems",
        "cloud",
        "research_engineer",
        "generative_ai",
        "agentic_ai",
    )


@dataclass
class RankResult:
    score: float
    reasons: list[str] = field(default_factory=list)


def load_profile() -> PreferenceProfile:
    """Load preference profile from INTEL_PREFERENCE_JSON or defaults."""
    raw = os.getenv("INTEL_PREFERENCE_JSON", "").strip()
    if not raw:
        path = os.getenv("INTEL_PREFERENCE_PATH", "").strip()
        if path and os.path.isfile(path):
            raw = open(path, encoding="utf-8").read()
    if not raw:
        return PreferenceProfile()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return PreferenceProfile()
    return PreferenceProfile(
        must_keywords=tuple(data.get("must_keywords") or DEFAULT_MUST_KEYWORDS),
        boost_keywords=tuple(data.get("boost_keywords") or DEFAULT_BOOST_KEYWORDS),
        penalty_keywords=tuple(
            data.get("penalty_keywords") or DEFAULT_PENALTY_KEYWORDS
        ),
        prefer_india=bool(data.get("prefer_india", True)),
        prefer_role_families=tuple(
            data.get("prefer_role_families")
            or PreferenceProfile().prefer_role_families
        ),
    )


def _blob(doc: dict[str, Any]) -> str:
    parts = [
        doc.get("title") or "",
        doc.get("location_text") or "",
        doc.get("role_family") or "",
        " ".join(doc.get("filter_reasons") or []),
        (doc.get("description_text") or "")[:2000],
    ]
    return " ".join(parts).lower()


def score_job(doc: dict[str, Any], profile: PreferenceProfile | None = None) -> RankResult:
    """Soft rank a filter_pass internship. Higher is better."""
    profile = profile or load_profile()
    text = _blob(doc)
    score = 0.0
    reasons: list[str] = []

    must_hits = [k for k in profile.must_keywords if k.lower() in text]
    if must_hits:
        score += 40 + min(20, len(must_hits) * 3)
        reasons.append(f"tech keywords: {', '.join(must_hits[:4])}")
    else:
        score -= 15
        reasons.append("weak tech-keyword match")

    family = (doc.get("role_family") or "").lower()
    if family and family in {f.lower() for f in profile.prefer_role_families}:
        score += 25
        reasons.append(f"role family: {family}")

    if profile.prefer_india and doc.get("is_india"):
        score += 20
        reasons.append("India location")
    elif doc.get("is_remote"):
        score += 8
        reasons.append("remote")

    boost_hits = [k for k in profile.boost_keywords if k.lower() in text]
    if boost_hits:
        score += min(15, len(boost_hits) * 3)
        reasons.append(f"boost: {', '.join(boost_hits[:3])}")

    pen_hits = [
        k
        for k in profile.penalty_keywords
        if re.search(rf"\b{re.escape(k.lower())}\b", text)
    ]
    if pen_hits:
        score -= 25
        reasons.append(f"penalty: {', '.join(pen_hits[:3])}")

    conf = doc.get("detection_confidence")
    if isinstance(conf, (int, float)):
        score += float(conf) * 10
        reasons.append(f"detection conf {conf:.2f}")

    if doc.get("grad_year_eligibility") == "2028":
        score += 10
        reasons.append("2028 eligible")
    if doc.get("season_tag") == "summer_2027":
        score += 8
        reasons.append("Summer 2027")

    return RankResult(score=round(score, 2), reasons=reasons)


def rank_jobs(
    docs: list[dict[str, Any]],
    *,
    profile: PreferenceProfile | None = None,
) -> list[tuple[dict[str, Any], RankResult]]:
    profile = profile or load_profile()
    ranked = [(d, score_job(d, profile)) for d in docs]
    ranked.sort(key=lambda x: x[1].score, reverse=True)
    return ranked
