"""Engineering internship detection — exact role allowlist from product requirements.

Accepted intern roles (title must include intern/co-op/trainee):
  Software Engineer, SDE, Backend, Frontend, Full Stack,
  AI Engineer, Machine Learning, Applied Scientist, Research Engineer,
  Infrastructure, Platform, Cloud, Systems, Security,
  Data Engineer, Generative AI, LLM, Agentic AI, Research Intern
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Ordered: more specific patterns first
ROLE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "agentic_ai",
        re.compile(r"\b(agentic\s*ai|ai\s*agent|llm\s*agent)\b", re.I),
    ),
    (
        "generative_ai",
        re.compile(r"\b(generative\s*ai|gen[\s-]?ai)\b", re.I),
    ),
    (
        "llm",
        re.compile(r"\b(llm|large\s*language\s*model)\b", re.I),
    ),
    (
        "applied_scientist",
        re.compile(r"\b(applied\s*scientist|research\s*scientist)\b", re.I),
    ),
    (
        "research_engineer",
        re.compile(r"\bresearch\s*engineer\b", re.I),
    ),
    (
        "ml",
        re.compile(
            r"\b(machine\s*learning|ml\s*engineer|ml\s*intern|deep\s*learning)\b",
            re.I,
        ),
    ),
    (
        "ai_engineer",
        re.compile(r"\b(ai\s*engineer|artificial\s*intelligence)\b", re.I),
    ),
    (
        "data_engineer",
        re.compile(r"\b(data\s*engineer)\b", re.I),
    ),
    (
        "security",
        re.compile(
            r"\b(security\s*engineer|cybersecurity|infosec|security\s*intern|"
            r"application\s*security|appsec)\b",
            re.I,
        ),
    ),
    (
        "infrastructure",
        re.compile(r"\b(infrastructure|infra\s*engineer|infra\s*intern)\b", re.I),
    ),
    (
        "platform",
        re.compile(r"\b(platform\s*engineer|platform\s*intern)\b", re.I),
    ),
    (
        "cloud",
        re.compile(r"\b(cloud\s*engineer|cloud\s*intern|cloud\s*infrastructure)\b", re.I),
    ),
    (
        "systems",
        re.compile(
            r"\b(systems\s*engineer|systems\s*intern|system\s*software|"
            r"sre|site\s*reliability|devops)\b",
            re.I,
        ),
    ),
    (
        "fullstack",
        re.compile(r"\b(full[\s-]?stack)\b", re.I),
    ),
    (
        "backend",
        re.compile(r"\b(backend|back[\s-]?end)\b", re.I),
    ),
    (
        "frontend",
        re.compile(r"\b(frontend|front[\s-]?end)\b", re.I),
    ),
    (
        "sde",
        re.compile(r"\b(software\s*development\s*engineer|sde)\b", re.I),
    ),
    (
        "swe",
        re.compile(
            r"\b(software\s*engineer|swe|software\s*developer|"
            r"software\s*intern|developer\s*intern|programming\s*intern)\b",
            re.I,
        ),
    ),
    (
        "research",
        re.compile(r"\bresearch\s*intern\b", re.I),
    ),
]

# Broad engineering/tech intern when specific family not matched
GENERIC_ENG_RE = re.compile(
    r"\b(software|engineering|engineer|technical|technology|developer|"
    r"programmer|computer\s*science|coding|swe|sde)\b",
    re.I,
)

INTERN_RE = re.compile(r"\b(intern(ship)?|co[\s-]?op|trainee)\b", re.I)

# Non-engineering internships to ignore
EXCLUDE_RE = re.compile(
    r"\b("
    r"sales(\s+intern)?|marketing|recruiter|recruiting|talent\s*acquisition|"
    r"hr\b|human\s*resources|people\s*ops|finance\s*intern|accounting|"
    r"legal\s*intern|paralegal|design\s*intern|product\s*design|"
    r"ux\s*design|ui\s*design|graphic\s*design|content(\s+writer)?|"
    r"social\s*media|customer\s*support|customer\s*success|"
    r"operations\s*intern|business\s*development|business\s*analyst|"
    r"mba\b|pharmacist|nurse|hardware\s*test|mechanical\s*intern|"
    r"civil\s*intern|electrical\s*intern(?!\s*software)|"
    r"product\s*manager\s*intern|pm\s*intern|program\s*manager\s*intern"
    r")\b",
    re.I,
)


@dataclass
class DetectionResult:
    is_internship: bool
    role_family: str | None
    confidence: float
    reason: str


def detect_internship(title: str, description: str | None = None) -> DetectionResult:
    text = (title or "").strip()
    if not text:
        return DetectionResult(False, None, 1.0, "empty_title")

    if EXCLUDE_RE.search(text) and not GENERIC_ENG_RE.search(text):
        return DetectionResult(False, None, 0.9, "excluded_non_eng_title")
    # If both exclude and eng match (e.g. "Security Intern"), prefer eng paths below
    if EXCLUDE_RE.search(text) and not re.search(
        r"\b(security|software|engineer|developer|data|ml|ai|cloud|platform|"
        r"infra|systems|backend|frontend|research)\b",
        text,
        re.I,
    ):
        return DetectionResult(False, None, 0.9, "excluded_non_eng_title")

    if not INTERN_RE.search(text):
        return DetectionResult(False, None, 0.95, "not_intern")

    # Match specific allowlisted roles (title first, then short description head)
    blob_head = f"{text}\n{(description or '')[:800]}"
    for family, pat in ROLE_PATTERNS:
        if pat.search(text) or pat.search(blob_head):
            return DetectionResult(True, family, 0.95, f"matched:{family}")

    if GENERIC_ENG_RE.search(text):
        return DetectionResult(True, "swe", 0.8, "matched:generic_eng")

    return DetectionResult(False, None, 0.7, "intern_but_not_allowed_role")


# Canonical list for docs / tests
ALLOWED_ROLE_LABELS = [
    "Software Engineer Intern",
    "Software Development Engineer Intern",
    "Backend Intern",
    "Frontend Intern",
    "Full Stack Intern",
    "AI Engineer Intern",
    "Machine Learning Intern",
    "Applied Scientist Intern",
    "Research Engineer Intern",
    "Infrastructure Intern",
    "Platform Intern",
    "Cloud Intern",
    "Systems Intern",
    "Security Intern",
    "Data Engineer Intern",
    "Generative AI Intern",
    "LLM Intern",
    "Agentic AI Intern",
    "Research Intern",
]
