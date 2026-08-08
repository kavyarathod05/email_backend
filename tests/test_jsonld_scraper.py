"""Unit tests for JSON-LD career scraping (offline fixtures)."""

from __future__ import annotations

from intel.core.models.company import AtsProvider
from intel.modules.scraping.jsonld import extract_json_ld_jobs, jobposting_to_normalized


SAMPLE_HTML = """
<html><head><title>Careers</title>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "JobPosting",
  "title": "Software Engineer Intern",
  "description": "Build APIs in Bangalore, India",
  "datePosted": "2026-01-15",
  "url": "https://example.com/jobs/swe-intern",
  "jobLocation": {
    "@type": "Place",
    "address": {
      "@type": "PostalAddress",
      "addressLocality": "Bengaluru",
      "addressCountry": "IN"
    }
  }
}
</script>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "JobPosting",
      "title": "ML Intern",
      "url": "/jobs/ml-intern",
      "jobLocation": "Hyderabad, India"
    }
  ]
}
</script>
</head><body></body></html>
"""


def test_extract_json_ld_jobs():
    jobs = extract_json_ld_jobs(SAMPLE_HTML, base_url="https://example.com/careers")
    assert len(jobs) == 2
    titles = {j["title"] for j in jobs}
    assert "Software Engineer Intern" in titles
    assert "ML Intern" in titles


def test_jobposting_to_normalized():
    jobs = extract_json_ld_jobs(SAMPLE_HTML, base_url="https://example.com/careers")
    nj = jobposting_to_normalized(
        jobs[0],
        company_name="Example",
        company_slug="example",
        provider=AtsProvider.json_ld,
    )
    assert nj is not None
    assert nj.ats_provider == AtsProvider.json_ld
    assert "Intern" in nj.title
    assert nj.apply_url.startswith("http")
    assert nj.external_job_id


def test_ranker_prefers_swe_india():
    from intel.modules.matching.ranker import score_job

    high = score_job(
        {
            "title": "Software Engineer Intern",
            "location_text": "Bengaluru, India",
            "is_india": True,
            "role_family": "swe",
            "filter_reasons": ["india"],
            "description_text": "backend internship",
            "detection_confidence": 0.9,
            "grad_year_eligibility": "2028",
            "season_tag": "summer_2027",
        }
    )
    low = score_job(
        {
            "title": "Marketing Intern",
            "location_text": "New York",
            "is_india": False,
            "role_family": None,
            "filter_reasons": [],
            "description_text": "sales marketing",
        }
    )
    assert high.score > low.score
    assert any("India" in r or "tech" in r for r in high.reasons)
