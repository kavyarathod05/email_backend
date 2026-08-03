"""Smart filters: India (strict) + optional remote + season/grad year tags."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from intel.core.models.job import GradYearEligibility, SeasonTag

INDIA_RE = re.compile(
    r"\b("
    r"india|indian|"
    r"bengaluru|bangalore|hyderabad|pune|mumbai|chennai|delhi|new\s*delhi|"
    r"gurgaon|gurugram|noida|kolkata|ahmedabad|jaipur|chandigarh|kochi|"
    r"trivandrum|thiruvananthapuram|coimbatore|indore|bhopal|lucknow|"
    r"remote[\s\-]*(in\s*)?india|india[\s\-]*remote|in[\s\-]?remote"
    r")\b",
    re.I,
)
REMOTE_RE = re.compile(
    r"\b(remote|work\s*from\s*home|wfh|distributed|anywhere|work\s*from\s*anywhere)\b",
    re.I,
)

# Explicit non-India geo — reject unless India also clearly present
FOREIGN_GEO_RE = re.compile(
    r"\b("
    r"united\s*states|\bUSA\b|\bU\.S\.A\.?\b|\bUS\b|"
    r"united\s*kingdom|\bUK\b|\bU\.K\.?\b|"
    r"canada|australia|germany|france|netherlands|singapore|japan|"
    r"ireland|switzerland|sweden|norway|denmark|finland|poland|"
    r"brazil|mexico|spain|italy|portugal|israel|uae|dubai|"
    r"hong\s*kong|south\s*korea|korea|philippines|indonesia|vietnam|"
    r"new\s*zealand|south\s*africa|"
    r"new\s*york|nyc|san\s*francisco|sf\s*bay|bay\s*area|seattle|"
    r"austin|boston|chicago|los\s*angeles|atlanta|denver|dallas|"
    r"london|manchester|berlin|munich|amsterdam|paris|toronto|"
    r"vancouver|sydney|melbourne|dublin|zurich|tel\s*aviv|"
    r"remote[\s\-]*(us|usa|uk|u\.k\.|canada|europe|eu|emea|americas)|"
    r"(us|usa|uk|canada|europe)[\s\-]*remote|"
    r"based\s*in\s*(us|usa|uk|canada|europe|london|nyc|seattle)"
    r")\b",
    re.I,
)

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
    require_india: bool = True,
    allow_remote: bool = False,
) -> FilterResult:
    """
    Geo rules (defaults match product):
      - require_india=True  → must mention India / Indian city (strict)
      - allow_remote=True   → also keep global Remote (not foreign-locked)
    """
    loc = (location_text or "").strip()
    geo_blob = f"{title}\n{loc}\n{(description or '')[:2000]}"
    season_blob = f"{title}\n{loc}\n{(description or '')[:8000]}"
    reasons: list[str] = []

    is_india = bool(INDIA_RE.search(geo_blob))
    is_remote = bool(is_remote_hint) if is_remote_hint is not None else False
    if REMOTE_RE.search(geo_blob):
        is_remote = True

    has_foreign = bool(FOREIGN_GEO_RE.search(geo_blob))
    remote_foreign_only = bool(
        is_remote
        and has_foreign
        and not is_india
        and re.search(
            r"remote[\s\-]*(us|usa|uk|u\.k\.|canada|europe|eu|emea|americas)|"
            r"(us|usa|uk|canada|europe)[\s\-]*remote|"
            r"based\s*in\s*(us|usa|uk|canada|europe)",
            geo_blob,
            re.I,
        )
    )

    if is_india and not remote_foreign_only:
        geo_ok = True
        reasons.append("india")
        if is_remote:
            reasons.append("remote")
    elif allow_remote and is_remote and not has_foreign and not remote_foreign_only:
        geo_ok = True
        reasons.append("remote")
    elif allow_remote and is_remote and is_india:
        geo_ok = True
        reasons.append("india")
        reasons.append("remote")
    else:
        geo_ok = False
        if require_india and not is_india:
            reasons.append("geo_india_required")
        elif has_foreign and not is_india:
            reasons.append("geo_foreign_rejected")
        elif not loc and not is_india and not is_remote:
            reasons.append("geo_unknown_rejected")
        else:
            reasons.append("geo_not_india_or_remote")

    if SUMMER_2027_RE.search(season_blob):
        season = SeasonTag.summer_2027
        reasons.append("season_summer_2027")
    elif OTHER_SEASON_RE.search(season_blob) and not SUMMER_2027_RE.search(season_blob):
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

    if GRAD_2028_RE.search(season_blob):
        grad = GradYearEligibility.y2028
        reasons.append("grad_2028")
    elif GRAD_OTHER_RE.search(season_blob) and not GRAD_2028_RE.search(season_blob):
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

    if not geo_ok:
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
        is_india=True if is_india else False,
        is_remote=True if is_remote else False,
        grad_year=grad,
        season=season,
        reasons=reasons,
    )
