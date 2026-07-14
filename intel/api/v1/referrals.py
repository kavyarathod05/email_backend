"""Find company contacts + send referral emails for a job."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from config import logger, recruiters_col, templates_col
from intel.core.errors import AppError
from intel.deps import get_job_repo
from intel.modules.jobs.repository import JobRepository
from services.email_sender import send_email
from services.lead_finder import discover_and_save_employees

router = APIRouter(prefix="/referrals", tags=["referrals"])

_FAKE_EMAIL_SUFFIXES = ("@unknown.local", "@linkedin.local")


class SendReferralRequest(BaseModel):
    job_id: str
    resume_link: str = Field(..., min_length=8)
    template_id: str | None = None
    emails: list[str] | None = None
    dry_run: bool = False


class DiscoverRequest(BaseModel):
    job_id: str | None = None
    company: str | None = None
    limit: int = Field(12, ge=1, le=30)
    force: bool = False


def _company_query(company_name: str) -> dict:
    escaped = re.escape(company_name.strip())
    return {"company": {"$regex": escaped, "$options": "i"}}


def _can_email(email: str | None, doc: dict | None = None) -> bool:
    if not email:
        return False
    el = email.lower()
    if any(el.endswith(s) for s in _FAKE_EMAIL_SUFFIXES):
        return False
    if doc is not None and doc.get("emailGuessed") is False:
        return False
    return "@" in email


def _serialize_contact(doc: dict) -> dict:
    email = doc.get("email") or ""
    return {
        "email": email,
        "name": doc.get("name") or "",
        "company": doc.get("company") or "",
        "status": doc.get("status"),
        "title": doc.get("title") or doc.get("role") or "",
        "linkedin": doc.get("linkedin") or "",
        "can_email": _can_email(email, doc),
        "source": doc.get("source") or "",
    }


def _list_company_contacts(company: str, limit: int = 50) -> list[dict]:
    q = _company_query(company)
    cursor = recruiters_col.find(q).limit(limit)
    return [_serialize_contact(d) for d in cursor if d.get("email") or d.get("linkedin")]


def _build_referral_email(
    *,
    contact: dict,
    job: dict,
    resume_link: str,
    template_doc: dict,
) -> dict:
    name = contact.get("name") or "there"
    company = job.get("company_name") or contact.get("company") or ""
    job_title = job.get("title") or ""
    job_link = job.get("apply_url") or ""
    resume_html = (
        f'<a href="{resume_link}" target="_blank" '
        f'style="color: #2563eb; font-weight: 700; text-decoration: underline;">'
        "Resume</a>"
    )
    job_link_html = (
        f'<a href="{job_link}" target="_blank" '
        f'style="color: #2563eb; font-weight: 700; text-decoration: underline;">'
        f"{job_title or 'Job posting'}</a>"
    )

    subject_t = template_doc.get("subject") or "Referral request — {job_title} at {company}"
    body_t = template_doc.get("htmlBody") or ""

    replacements = {
        "{name}": name,
        "{company}": company,
        "{job_title}": job_title,
        "{job_link}": job_link_html,
        "{job_url}": job_link,
        "{resume_link}": resume_html,
        "{resume_url}": resume_link,
    }

    subject = subject_t
    html = body_t
    for k, v in replacements.items():
        subject = subject.replace(k, v)
        html = html.replace(k, v)

    return {
        "To": contact["email"],
        "Subject": subject,
        "HTMLPart": html,
    }


@router.get("/contacts")
def find_contacts(
    company: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """Members already in DB for this company."""
    contacts = _list_company_contacts(company, limit=limit)
    return {"company": company, "count": len(contacts), "contacts": contacts}


@router.post("/discover")
def discover_employees(
    body: DiscoverRequest,
    repo: JobRepository = Depends(get_job_repo),
) -> dict:
    """
    Auto-find employees for a job's company (engineers + campus/TA),
    save them with LinkedIn when available, return full contact list.
    """
    company = (body.company or "").strip()
    job = None
    if body.job_id:
        job = repo.get_by_id(body.job_id)
        if not job:
            raise AppError("Job not found", code="not_found", status_code=404)
        company = company or job["company_name"]

    if not company:
        raise AppError("company or job_id required", code="validation_error", status_code=400)

    existing = _list_company_contacts(company, limit=100)
    # Skip expensive discover if we already have enough unless force
    discover_meta = {
        "ran": False,
        "count_added": 0,
        "skipped": 0,
        "domain": "",
    }
    should_run = body.force or len(existing) < 3
    if should_run:
        try:
            result = discover_and_save_employees(
                company,
                limit=body.limit,
                job_id=body.job_id,
            )
            discover_meta = {
                "ran": True,
                "count_added": result.get("count_added", 0),
                "skipped": result.get("skipped", 0),
                "domain": result.get("domain") or "",
                "company": result.get("company") or company,
            }
            company = result.get("company") or company
        except Exception as e:
            logger.error(f"Referral discover failed for {company}: {e}")
            discover_meta = {
                "ran": True,
                "count_added": 0,
                "skipped": 0,
                "domain": "",
                "error": str(e),
            }

    contacts = _list_company_contacts(company, limit=100)
    return {
        "company": company,
        "job_id": body.job_id,
        "count": len(contacts),
        "contacts": contacts,
        "discover": discover_meta,
    }


@router.get("/templates")
def list_referral_templates() -> dict:
    docs = list(templates_col.find({"type": "referral"}).sort("createdAt", -1))
    items = []
    for t in docs:
        items.append(
            {
                "_id": str(t["_id"]),
                "name": t.get("name"),
                "subject": t.get("subject"),
                "htmlBody": t.get("htmlBody"),
                "type": t.get("type"),
            }
        )
    return {"items": items, "count": len(items)}


@router.post("/send")
def send_referrals(
    body: SendReferralRequest,
    repo: JobRepository = Depends(get_job_repo),
) -> dict:
    """
    Send referral request emails for a job.
    Placeholders: {name} {company} {job_title} {job_link} {job_url} {resume_link} {resume_url}
    """
    job = repo.get_by_id(body.job_id)
    if not job:
        raise AppError("Job not found", code="not_found", status_code=404)

    if body.template_id:
        try:
            template_doc = templates_col.find_one({"_id": ObjectId(body.template_id)})
        except Exception as e:
            raise AppError(f"Invalid template id: {e}", code="bad_request", status_code=400)
        if not template_doc:
            raise AppError("Template not found", code="not_found", status_code=404)
    else:
        template_doc = templates_col.find_one({"type": "referral"}, sort=[("createdAt", -1)])
        if not template_doc:
            raise AppError(
                "No referral template found. Create one in Templates (type: referral).",
                code="no_template",
                status_code=400,
            )

    if body.emails:
        contacts = []
        for email in body.emails:
            if not _can_email(email):
                continue
            doc = recruiters_col.find_one({"email": email})
            if doc:
                contacts.append(_serialize_contact(doc))
            else:
                contacts.append(
                    {
                        "email": email,
                        "name": "",
                        "company": job["company_name"],
                        "can_email": True,
                        "linkedin": "",
                        "title": "",
                    }
                )
    else:
        contacts = [
            c
            for c in _list_company_contacts(job["company_name"], limit=50)
            if c.get("can_email")
        ]

    if not contacts:
        raise AppError(
            f"No emailable contacts for {job['company_name']}. "
            "Open Find & refer to discover employees first.",
            code="no_contacts",
            status_code=404,
        )

    results = []
    sent = 0
    failed = 0
    for contact in contacts:
        payload = _build_referral_email(
            contact=contact,
            job=job,
            resume_link=body.resume_link.strip(),
            template_doc=template_doc,
        )
        if body.dry_run:
            results.append(
                {
                    "email": contact["email"],
                    "ok": True,
                    "dry_run": True,
                    "subject": payload["Subject"],
                }
            )
            sent += 1
            continue

        ok, err, msg_id = send_email(payload)
        if ok:
            sent += 1
            recruiters_col.update_one(
                {"email": contact["email"]},
                {
                    "$set": {
                        "lastReferralJobId": body.job_id,
                        "lastReferralAt": datetime.now(timezone.utc),
                        "lastReferralSubject": payload["Subject"],
                    }
                },
            )
        else:
            failed += 1
        results.append(
            {
                "email": contact["email"],
                "ok": ok,
                "error": err,
                "message_id": msg_id,
                "subject": payload["Subject"],
            }
        )

    return {
        "job_id": body.job_id,
        "company": job["company_name"],
        "job_title": job["title"],
        "job_link": job["apply_url"],
        "template_id": str(template_doc.get("_id")),
        "sent": sent,
        "failed": failed,
        "results": results,
    }
