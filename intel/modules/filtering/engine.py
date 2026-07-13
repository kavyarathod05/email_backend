"""Smart filters: India OR Remote + season/grad year tags."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from intel.core.models.job import GradYearEligibility, SeasonTag

INDIA_RE = re.compile(
    r"\b(india|bengaluru|bangalore|hyderabad|pune|mumbai|chennai|delhi|"
    r"gurgaon|gurugram|noida|kolkata|ahmedabad|remote[\s-]?india|"
    r"in[\s-]?remote)\b",
    re.I,
)
REMOTE_RE = re.compile(r"\b(remote|work\s*from\s*home|wfh|distributed)\b", re.I)

# Summer 2027 / 2027 internship
SUMMER_2027_RE = re.compile(
    r"(summer\s*2027|intern(ship)?\s*(for\s*)?2027|2027\s*intern|"
    r"may\s*2027|june\s*2027|jul(y)?\s*2027)",
    re.I,
)
OTHER_SEASON_RE = re.compile(
    r"(summer\s*202[456]|intern(ship)?\s*(for\s*)?202[456]|202[456]\s*intern|"
    r"summer\s*2028)",
    re.I,
)

GRAD_2028_RE = re.compile(
    r"(class\s*of\s*2028|graduat(ing|ion)?\s*(in\s*)?2028|2028\s*batch|"
    r"batch\s*of\s*2028|expected\s*2028|grad\s*year\s*2028)",
    re.I,
)
GRAD_OTHER_RE = re.compile(
    r"(class\s*of\s*202[4567]|graduat(ing|ion)?\s*(in\s*)?202[4567]|"
    r"202[4567]\s*batch|batch\s*of\s*202[4567])",
    re.I,
)


@dataclass
class FilterResult:
    passed: bool
    is_india: bool | None
    is_remote: bool | None
    grad_year: GradYearEligibility
    season: SeasonTag
    reasons: list[str] = field(default_factory=list)


def apply_filters(
    *,
    title: str,
    location_text: str | None,
    description: str | None,
    is_remote_hint: bool | None,
) -> FilterResult:
    blob = f"{title}\n{location_text or ''}\n{(description or '')[:8000]}"
    reasons: list[str] = []

    is_india = bool(INDIA_RE.search(blob))
    is_remote = bool(is_remote_hint) if is_remote_hint is not None else bool(
        REMOTE_RE.search(blob)
    )
    if REMOTE_RE.search(blob):
        is_remote = True

    # Geo: keep if India OR Remote OR location unknown
    location_unknown = not (location_text and location_text.strip()) and not is_india and not is_remote
    if is_india or is_remote or location_unknown:
        geo_ok = True
        if location_unknown:
            reasons.append("location_unknown_kept")
        elif is_india:
            reasons.append("india")
        if is_remote:
            reasons.append("remote")
    else:
        # Has a location but neither India nor remote (e.g. US-only)
        geo_ok = False
        reasons.append("geo_not_india_or_remote")

    # Season
    if SUMMER_2027_RE.search(blob):
        season = SeasonTag.summer_2027
        reasons.append("season_summer_2027")
    elif OTHER_SEASON_RE.search(blob) and not SUMMER_2027_RE.search(blob):
        season = SeasonTag.other
        reasons.append("season_other_rejected")
        return FilterResult(
            passed=False,
            is_india=is_india or None,
            is_remote=is_remote or None,
            grad_year=GradYearEligibility.unknown,
            season=season,
            reasons=reasons,
        )
    else:
        season = SeasonTag.unknown
        reasons.append("season_unknown_kept")

    # Grad year
    if GRAD_2028_RE.search(blob):
        grad = GradYearEligibility.y2028
        reasons.append("grad_2028")
    elif GRAD_OTHER_RE.search(blob) and not GRAD_2028_RE.search(blob):
        grad = GradYearEligibility.other
        reasons.append("grad_other_rejected")
        return FilterResult(
            passed=False,
            is_india=is_india or None,
            is_remote=is_remote or None,
            grad_year=grad,
            season=season,
            reasons=reasons,
        )
    else:
        grad = GradYearEligibility.unknown
        reasons.append("grad_unknown_kept")

    passed = geo_ok
    if not passed:
        return FilterResult(
            passed=False,
            is_india=is_india or None,
            is_remote=is_remote or None,
            grad_year=grad,
            season=season,
            reasons=reasons,
        )

    return FilterResult(
        passed=True,
        is_india=is_india if is_india else (None if location_unknown else False),
        is_remote=is_remote if is_remote else None,
        grad_year=grad,
        season=season,
        reasons=reasons,
    )
