"""
Email builder: constructs HTML email payloads for initial, follow-up, and breakup stages.

Template placeholder:
  - {name}        → recruiter name or "there"
  - {company}     → recruiter company or "your team"
  - {resume_link} → bold, clickable <a> tag with click-tracking URL
"""
import os
import urllib.parse

from config import logger, templates_col
from services.ai_service import generate_company_sentence, generate_opening_line, generate_subject_lines

# Generic/personal email domains — skip AI personalization for these
GENERIC_DOMAINS = {
    "gmail.com", "yahoo.com", "yahoo.co.in", "hotmail.com", "outlook.com",
    "live.com", "aol.com", "icloud.com", "mail.com", "protonmail.com",
    "zoho.com", "yandex.com", "gmx.com", "rediffmail.com",
}

def is_generic_email(email_addr: str) -> bool:
    """Returns True if the email is from a personal/generic domain."""
    if not email_addr or "@" not in email_addr:
        return True
    domain = email_addr.split("@")[1].lower().strip()
    return domain in GENERIC_DOMAINS


# ────────────────────── Shared Helpers ──────────────────────

def _get_tracking_urls(recruiter_email: str, resume_raw: str):
    """
    Returns (resume_url, pixel_html).
    If TRACKING_BASE_URL is set, resume_url is wrapped in click tracker
    and pixel_html contains a 1x1 open-tracking image.
    """
    tracking_base = os.getenv("TRACKING_BASE_URL", "").rstrip("/")
    if tracking_base:
        encoded = urllib.parse.quote(resume_raw)
        resume_url = f"{tracking_base}/track/click/{recruiter_email}?url={encoded}"
        pixel_html = (
            f'<img src="{tracking_base}/track/open/{recruiter_email}" '
            f'width="1" height="1" style="display:none;" />'
        )
    else:
        resume_url = resume_raw
        pixel_html = ""
    return resume_url, pixel_html


def _build_resume_link(resume_url: str) -> str:
    """Build a bold, clickable resume <a> tag with click-tracking."""
    return (
        f'<a href="{resume_url}" target="_blank" '
        f'style="color: #2563eb; font-weight: 700; text-decoration: underline;">'
        f'Resume</a>'
    )


def _build_mailto_buttons(company: str):
    """Build the one-click quick-reply mailto buttons HTML block."""

    def _quote_mailto(subj, body_text):
        qs = urllib.parse.quote(subj)
        qb = urllib.parse.quote(body_text)
        return f"mailto:rathodkavya2005@gmail.com?subject={qs}&body={qb}"

    yes_link = _quote_mailto(
        f"Re: Internship @ {company}",
        f"Hi Kavya,\n\nI saw your application for {company}. Let's chat. When are you free?",
    )
    no_link = _quote_mailto(
        f"Contact for Internship @ {company}",
        f"Hi Kavya,\n\nI'm not the best person to speak with. You should reach out to [Name/Email] instead.",
    )

    return f"""
    <div style="margin-top: 25px; padding: 15px; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0;">
        <p style="margin-top: 0; color: #64748b; font-size: 14px;">One-click quick reply:</p>
        <a href="{yes_link}" style="display: inline-block; padding: 10px 18px; background: #22c55e; color: white; text-decoration: none; border-radius: 6px; font-weight: 600; margin-right: 10px;">Yes, let's chat</a>
        <a href="{no_link}" style="display: inline-block; padding: 10px 18px; background: #94a3b8; color: white; text-decoration: none; border-radius: 6px; font-weight: 600;">Not the right person</a>
    </div>
    """


def _resolve_template(html_template: str, subject_template: str,
                       name: str, company: str,
                       resume_link_html: str,
                       company_sentence: str = "",
                       opening_line: str = ""):
    """
    Safely substitute placeholders in a template string.

    Supported placeholders:
      {name}             — recruiter name
      {company}          — recruiter company
      {resume_link}      — bold, clickable <a> tag with click-tracking
      {company_sentence} — AI-generated company description
      {opening_line}     — AI-generated opening line
    """
    try:
        subject = subject_template.format(name=name, company=company)
    except Exception:
        subject = subject_template

    try:
        html_body = html_template.format(
            name=name,
            company=company,
            resume_link=resume_link_html,
            company_sentence=company_sentence,
            opening_line=opening_line,
        )
    except Exception as e:
        logger.warning(f"Template formatting failed (.format()), using .replace() fallback: {e}")
        html_body = html_template
        replacements = {
            "{name}": name,
            "{company}": company,
            "{resume_link}": resume_link_html,
            "{company_sentence}": company_sentence,
            "{opening_line}": opening_line,
        }
        for placeholder, value in replacements.items():
            html_body = html_body.replace(placeholder, value)

    return subject, html_body


# ────────────────────── Build Initial Email ──────────────────────

def build_email(recruiter: dict, template_doc: dict | None = None) -> dict:
    """
    Build the initial outreach email payload.
    Uses the given DB template_doc, or falls back to .env defaults.
    """
    resume_raw = os.getenv("RESUME_LINK", "")
    name = recruiter.get("name") or "there"
    company = recruiter.get("company") or ""

    # Choose template source
    if template_doc:
        html_template = template_doc.get("htmlBody", "")
        subject_template = template_doc.get("subject", "")
    else:
        html_template = os.getenv("EMAIL_TEMPLATE_HTML", "")
        subject_template = os.getenv("EMAIL_SUBJECT", "")

    # Tracking
    resume_url, pixel_html = _get_tracking_urls(recruiter["email"], resume_raw)
    resume_link_html = _build_resume_link(resume_url)

    # AI Personalization
    company_sentence = ""
    opening_line = ""
    if company and company != "your team":
        try:
            logger.info(f"Triggering AI personalization for {recruiter['email']} ({company})")
            company_sentence = generate_company_sentence(company)
            opening_line = generate_opening_line(company)
            logger.info(f"AI Personalization applied: {company_sentence[:40]}...")
        except Exception as e:
            logger.error(f"Error generating AI personalization: {e}")
    else:
        logger.info(f"Skipping AI personalization due to missing company: {recruiter['email']}")

    subject, html_body = _resolve_template(
        html_template, subject_template,
        name, company, resume_link_html,
        company_sentence, opening_line
    )

    html_body += _build_mailto_buttons(company)
    html_body += pixel_html

    return {
        "To": recruiter["email"],
        "Subject": subject,
        "HTMLPart": html_body,
    }


# ────────────────────── Build Follow-up / Breakup Email ──────────────────────

def _get_behavioral_template(stage: int, recruiter: dict):
    """
    Return (subject_template, html_template) based on recruiter engagement.
    Stage 1 uses behavioral branching; Stage 2 is always the breakup.
    """
    if stage == 1:
        clicked = recruiter.get("clicked", False)
        opened = recruiter.get("opened", False)

        if clicked:
            return (
                "Glad you saw my resume | Kavya @ {company}",
                """<p>Hi {name},</p>
                <p>I noticed you took a look at my resume recently—thanks for checking it out!
                I'm really excited about the work {company} is doing and would love to discuss how my background in building high-traffic systems could be a fit for your Summer '26 internship roles.</p>
                <p>Do you have 10 minutes for a quick chat later this week?</p>""",
            )
        elif opened:
            return (
                "Quick question about {company} internship",
                """<p>Hi {name},</p>
                <p>I'm following up on my previous email. I noticed you opened it, and I wanted to share a specific highlight:
                I recently led a team of 5 to build a system handling <b>10k daily traffic</b>, which I think would be relevant to the scale {company} operates at.</p>
                <p>I've attached my {resume_link} again for convenience. Would you be open to a brief chat?</p>""",
            )
        else:
            return (
                os.getenv("FOLLOWUP_SUBJECT", "Following up | Summer '26 Intern @{company}"),
                os.getenv("FOLLOWUP_TEMPLATE_HTML", ""),
            )
    else:
        # Stage 2 — breakup
        return (
            os.getenv("BREAKUP_SUBJECT", "Wrapping up | Summer '26 Intern @{company}"),
            os.getenv("BREAKUP_TEMPLATE_HTML", ""),
        )


def build_followup_email(recruiter: dict, stage: int,
                         template_doc: dict | None = None) -> dict:
    """
    Build a follow-up or breakup email payload.

    Priority:
      1. Explicit template_doc (from test panel or manual override)
      2. DB templates of matching type with round-robin
      3. Behavioral branching / .env fallback
    """
    name = recruiter.get("name") or "there"
    company = recruiter.get("company") or ""
    resume_raw = os.getenv("RESUME_LINK", "")

    # --- Determine template ---
    template_used_id = None
    template_used_name = None

    if template_doc:
        html_template = template_doc.get("htmlBody", "")
        subject_template = template_doc.get("subject", "")
        template_used_id = str(template_doc.get("_id", ""))
        template_used_name = template_doc.get("name", "")
    else:
        # Behavioral branching is prioritized for Stage 1 in the AI branch
        if stage == 1:
            clicked = recruiter.get("clicked", False)
            opened = recruiter.get("opened", False)
            
            if clicked or opened:
                subject_template, html_template = _get_behavioral_template(stage, recruiter)
            else:
                # If not opened/clicked, check for DB templates or use fallback
                template_type = "followup1"
                db_templates = list(
                    templates_col.find({"type": template_type}).sort("createdAt", 1)
                )
                if db_templates:
                    from config import recruiters_col
                    total_at_stage = recruiters_col.count_documents(
                        {"followupStage": stage}
                    )
                    chosen = db_templates[total_at_stage % len(db_templates)]
                    html_template = chosen.get("htmlBody", "")
                    subject_template = chosen.get("subject", "")
                    template_used_id = str(chosen["_id"])
                    template_used_name = chosen.get("name", "")
                else:
                    subject_template, html_template = _get_behavioral_template(stage, recruiter)
        else:
            # Stage 2 — breakup
            template_type = "breakup"
            db_templates = list(
                templates_col.find({"type": template_type}).sort("createdAt", 1)
            )
            if db_templates:
                from config import recruiters_col
                total_at_stage = recruiters_col.count_documents(
                    {"followupStage": stage}
                )
                chosen = db_templates[total_at_stage % len(db_templates)]
                html_template = chosen.get("htmlBody", "")
                subject_template = chosen.get("subject", "")
                template_used_id = str(chosen["_id"])
                template_used_name = chosen.get("name", "")
            else:
                subject_template, html_template = _get_behavioral_template(stage, recruiter)

    # --- Tracking ---
    resume_url, pixel_html = _get_tracking_urls(recruiter["email"], resume_raw)
    resume_link_html = _build_resume_link(resume_url)

    # --- AI Personalization ---
    company_sentence = ""
    opening_line = ""
    if company and company != "your team" and stage == 1:
        try:
            logger.info(f"Triggering AI personalization for followup: {recruiter['email']} ({company})")
            company_sentence = generate_company_sentence(company)
            opening_line = generate_opening_line(company)
            logger.info(f"AI Followup Personalization applied.")
        except Exception as e:
            logger.error(f"Error generating AI personalization for followup: {e}")

    # --- Subject Line Rotation for Cold Followups (Scenario 3) ---
    if stage == 1 and not recruiter.get("opened") and company != "your team":
        try:
            ai_subjects = generate_subject_lines(company)
            if ai_subjects:
                from config import recruiters_col
                sent_to_company = recruiters_col.count_documents(
                    {"company": company, "status": "sent"}
                )
                subject_template = ai_subjects[sent_to_company % len(ai_subjects)]
        except Exception as e:
            logger.error(f"Error rotating AI subjects for followup: {e}")

    subject, html_body = _resolve_template(
        html_template, subject_template,
        name, company, resume_link_html,
        company_sentence, opening_line
    )

    html_body += _build_mailto_buttons(company)
    html_body += pixel_html

    result = {
        "To": recruiter["email"],
        "Subject": subject,
        "HTMLPart": html_body,
    }
    if template_used_id:
        result["templateUsed"] = template_used_id
        result["templateName"] = template_used_name

    return result
