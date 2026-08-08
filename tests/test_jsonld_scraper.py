"""Tests for custom career scrapers (JSON-LD + link discovery)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from intel.core.models.company import AtsProvider
from intel.modules.ats.providers.json_ld import JsonLdScraperAdapter
from intel.modules.matching.ranker import score_job
from intel.modules.scraping.jsonld import extract_json_ld_jobs, jobposting_to_normalized
from intel.modules.scraping.links import extract_job_links


LISTING_HTML = """
<html><body>
  <h1>Careers</h1>
  <a href="/jobs/swe-intern">Software Engineer Intern - Bengaluru</a>
  <a href="/jobs/ml-intern">Machine Learning Intern</a>
  <a href="/about">About us</a>
</body></html>
"""

DETAIL_SWE = """
<html><head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "JobPosting",
  "title": "Software Engineer Intern",
  "description": "Build APIs in Bangalore, India",
  "url": "https://example.com/jobs/swe-intern",
  "jobLocation": {
    "@type": "Place",
    "address": {"@type": "PostalAddress", "addressLocality": "Bengaluru", "addressCountry": "IN"}
  }
}
</script>
</head><body><h1>Software Engineer Intern</h1></body></html>
"""

DETAIL_ML = """
<html><head>
<script type="application/ld+json">
{"@graph":[{"@type":"JobPosting","title":"ML Intern","url":"/jobs/ml-intern","jobLocation":"Hyderabad, India"}]}
</script>
</head><body><h1>ML Intern</h1></body></html>
"""

CONCAT_JSON_LD = """
<html><head>
<script type="application/ld+json">
{"@type":"Organization","name":"Acme"}
{"@type":"JobPosting","title":"SDE Intern","url":"https://example.com/jobs/sde"}
</script>
</head></html>
"""


def test_extract_json_ld_jobs_basic():
    jobs = extract_json_ld_jobs(DETAIL_SWE, base_url="https://example.com/careers")
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Software Engineer Intern"


def test_extract_concatenated_json_ld():
    jobs = extract_json_ld_jobs(CONCAT_JSON_LD, base_url="https://example.com/")
    assert len(jobs) == 1
    assert jobs[0]["title"] == "SDE Intern"


def test_jobposting_to_normalized():
    jobs = extract_json_ld_jobs(DETAIL_SWE, base_url="https://example.com/careers")
    nj = jobposting_to_normalized(
        jobs[0],
        company_name="Example",
        company_slug="example",
        provider=AtsProvider.json_ld,
    )
    assert nj is not None
    assert nj.apply_url.startswith("http")
    assert "Bengaluru" in (nj.location_text or "")


def test_extract_job_links():
    links = extract_job_links(LISTING_HTML, base_url="https://example.com/careers")
    assert "https://example.com/jobs/swe-intern" in links
    assert "https://example.com/jobs/ml-intern" in links
    assert all("/about" not in u for u in links)


def test_json_ld_adapter_follows_listing_links():
    adapter = JsonLdScraperAdapter()

    async def fake_fetch(url: str, **kwargs):
        if "careers" in url and "jobs/" not in url:
            return LISTING_HTML
        if "swe-intern" in url:
            return DETAIL_SWE
        if "ml-intern" in url:
            return DETAIL_ML
        return None

    async def run():
        with patch(
            "intel.modules.ats.providers.json_ld.fetch_text",
            new=AsyncMock(side_effect=fake_fetch),
        ):
            return await adapter.list_jobs(
                board_token="https://example.com/careers",
                company_name="Example",
                company_slug="example",
            )

    jobs = asyncio.run(run())
    titles = {j.title for j in jobs}
    assert "Software Engineer Intern" in titles
    assert "ML Intern" in titles
    assert all(j.ats_provider == AtsProvider.json_ld for j in jobs)


def test_json_ld_adapter_direct_job_page():
    adapter = JsonLdScraperAdapter()

    async def run():
        with patch(
            "intel.modules.ats.providers.json_ld.fetch_text",
            new=AsyncMock(return_value=DETAIL_SWE),
        ):
            return await adapter.list_jobs(
                board_token="https://example.com/jobs/swe-intern",
                company_name="Example",
                company_slug="example",
            )

    jobs = asyncio.run(run())
    assert len(jobs) == 1
    assert jobs[0].title == "Software Engineer Intern"


def test_ranker_prefers_swe_india():
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
