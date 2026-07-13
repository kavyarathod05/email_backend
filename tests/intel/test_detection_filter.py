"""Detection tests covering all allowlisted role titles."""

from intel.modules.detection.engine import ALLOWED_ROLE_LABELS, detect_internship
from intel.modules.filtering.engine import apply_filters


def test_all_allowed_role_titles_pass():
    for title in ALLOWED_ROLE_LABELS:
        r = detect_internship(title)
        assert r.is_internship, f"should accept: {title} ({r.reason})"
        assert r.role_family, f"missing family for: {title}"


def test_detect_swe_intern():
    r = detect_internship("Software Engineer Intern - Backend")
    assert r.is_internship
    assert r.role_family in ("swe", "backend", "sde")


def test_detect_llm_and_agentic():
    assert detect_internship("LLM Intern").is_internship
    assert detect_internship("Agentic AI Intern").role_family == "agentic_ai"
    assert detect_internship("Generative AI Intern").role_family == "generative_ai"


def test_detect_research_engineer():
    r = detect_internship("Research Engineer Intern")
    assert r.is_internship
    assert r.role_family == "research_engineer"


def test_detect_rejects_sales():
    r = detect_internship("Sales Intern")
    assert not r.is_internship


def test_detect_rejects_ft():
    r = detect_internship("Senior Software Engineer")
    assert not r.is_internship


def test_filter_keeps_india():
    f = apply_filters(
        title="SDE Intern",
        location_text="Bengaluru, India",
        description="Join our team",
        is_remote_hint=None,
    )
    assert f.passed
    assert f.is_india


def test_filter_rejects_wrong_grad_year():
    f = apply_filters(
        title="SWE Intern",
        location_text="Remote",
        description="Class of 2026 only",
        is_remote_hint=True,
    )
    assert not f.passed
    assert f.grad_year.value == "other"


def test_filter_keeps_unknown_grad():
    f = apply_filters(
        title="ML Intern",
        location_text="Remote",
        description="Summer internship",
        is_remote_hint=True,
    )
    assert f.passed
    assert f.grad_year.value == "unknown"
