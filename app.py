from fastapi import FastAPI, HTTPException, UploadFile, File, status, Response, Query
from fastapi.responses import RedirectResponse
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import uvicorn
import os
import csv
import smtplib
import imaplib
import email
import logging
import urllib.parse
from email.message import EmailMessage
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import io
import re

def extract_first_name(email_addr: str) -> str:
    """
    Extracts a first name from an email address.
    Example: john.smith@stripe.com -> John
    """
    if not email_addr or "@" not in email_addr:
        return "there"
    
    local_part = email_addr.split("@")[0]
    # Replace separators with spaces
    name_cleaned = re.sub(r"[\._\-]", " ", local_part)
    tokens = name_cleaned.split()
    
    if tokens:
        first_token = tokens[0]
        # Edge case: no separators, take first 4-6 chars
        if len(tokens) == 1 and len(first_token) > 7:
             # If it's a long string without separators, hard to guess, but let's try a heuristic
             # or just take the first part. User says take first 4-6 chars.
             return first_token[:5].capitalize()
        return first_token.capitalize()
    
    return "there"

def normalize_company(company_name: str) -> str:
    """
    Normalizes company name to proper case and removes trailing spaces.
    """
    if not company_name:
        return ""
    return company_name.strip().title()

# Generic/personal email domains — skip AI personalization for these
GENERIC_DOMAINS = {
    "gmail.com", "yahoo.com", "yahoo.co.in", "hotmail.com", "outlook.com",
    "live.com", "aol.com", "icloud.com", "mail.com", "protonmail.com",
    "zoho.com", "yandex.com", "gmx.com", "rediffmail.com",
}

def is_generic_email(email_addr: str) -> bool:
    """Returns True if the email is from a personal/generic domain (gmail, yahoo, etc.)."""
    if not email_addr or "@" not in email_addr:
        return True
    domain = email_addr.split("@")[1].lower().strip()
    return domain in GENERIC_DOMAINS

class CSVImportRequest(BaseModel):
    csvText: str

class TestEmailRequest(BaseModel):
    email: str
    name: str = "Test Name"
    company: str = "Test Company"
    templateType: str = "initial"
    templateId: Optional[str] = None

class TemplateBase(BaseModel):
    name: str
    subject: str
    htmlBody: str
    type: str = "initial"

class SendOneRequest(BaseModel):
    templateId: Optional[str] = None

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load env variables
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB")

if not MONGO_URI or not MONGO_DB:
    raise Exception("Missing MongoDB environment variables")

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client[MONGO_DB]
    # Test connection
    client.server_info()
    recruiters_col = db["temp"]
    templates_col = db["templates"]
    logger.info("Connected to MongoDB successfully")
except Exception as e:
    logger.error(f"MongoDB Connection Error: {e}")
    raise Exception(f"Could not connect to MongoDB: {e}")

app = FastAPI()

# Proper CORS Setup
frontend_origin = os.getenv("FRONTEND_ORIGIN", "").rstrip("/")
origins = [
    frontend_origin,
    "http://localhost:5173",
    "http://localhost:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in origins if o],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- HEALTH ----------------

@app.get("/")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow()}

# ---------------- TEMPLATES ----------------

@app.get("/templates")
def list_templates():
    try:
        results = []
        for t in templates_col.find().sort("createdAt", -1):
            t["_id"] = str(t["_id"])
            results.append(t)
        return results
    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise HTTPException(status_code=500, detail="Error fetching templates")

@app.post("/templates")
def create_template(data: TemplateBase):
    try:
        template = {
            "name": data.name,
            "subject": data.subject,
            "htmlBody": data.htmlBody,
            "type": data.type,
            "createdAt": datetime.utcnow()
        }
        result = templates_col.insert_one(template)
        return {"message": "Template created", "id": str(result.inserted_id)}
    except Exception as e:
        logger.error(f"Error creating template: {e}")
        raise HTTPException(status_code=500, detail="Error creating template")

@app.put("/templates/{template_id}")
def update_template(template_id: str, data: TemplateBase):
    try:
        update_data = {
            "name": data.name,
            "subject": data.subject,
            "htmlBody": data.htmlBody,
            "type": data.type,
            "updatedAt": datetime.utcnow()
        }
        result = templates_col.update_one({"_id": ObjectId(template_id)}, {"$set": update_data})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Template not found")
        return {"message": "Template updated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating template: {e}")
        raise HTTPException(status_code=500, detail="Error updating template")

@app.delete("/templates/{template_id}")
def delete_template(template_id: str):
    try:
        result = templates_col.delete_one({"_id": ObjectId(template_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Template not found")
        return {"message": "Template deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting template: {e}")
        raise HTTPException(status_code=500, detail="Error deleting template")

# ---------------- TEST WEBHOOKS ----------------

@app.post("/test/open/{email}")
def test_open_event(email: str):
    recruiters_col.update_one(
        {"email": email},
        {"$set": {"opened": True, "openedAt": datetime.now(timezone.utc)}}
    )
    return {"message": "Simulated open"}

@app.post("/test/click/{email}")
def test_click_event(email: str):
    recruiters_col.update_one(
        {"email": email},
        {"$set": {"clicked": True, "clickedAt": datetime.now(timezone.utc)}}
    )
    return {"message": "Simulated click"}

# ---------------- TRACKING ----------------

@app.get("/track/open/{email}")
def track_open(email: str):
    try:
        recruiters_col.update_one(
            {"email": email},
            {"$set": {"opened": True, "openedAt": datetime.now(timezone.utc)}}
        )
    except Exception as e:
        logger.error(f"Error tracking open for {email}: {e}")
    
    # Return 1x1 transparent GIF
    pixel = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
    return Response(content=pixel, media_type="image/gif")

@app.get("/track/click/{email}")
def track_click(email: str, url: str):
    try:
        recruiters_col.update_one(
            {"email": email},
            {"$set": {"clicked": True, "clickedAt": datetime.now(timezone.utc)}}
        )
    except Exception as e:
        logger.error(f"Error tracking click for {email}: {e}")
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)

# ---------------- ADD RECRUITER ----------------

@app.post("/recruiters")
def add_recruiter(data: dict):
    try:
        email_addr = data.get("email")
        if not email_addr:
            raise HTTPException(status_code=400, detail="Email is required")

        email_addr = email_addr.lower()
        if recruiters_col.find_one({"email": email_addr}):
            raise HTTPException(status_code=409, detail="Recruiter already exists")

        # Lead Enrichment
        name = data.get("name", "")
        if not name:
            name = extract_first_name(email_addr)
        
        company = normalize_company(data.get("company", ""))

        recruiter = {
            "email": email_addr,
            "name": name,
            "company": company,
            "status": "new",
            "sentAt": None,
            "replied": False,
            "followupSent": False,
            "followupStage": 0,
            "opened": False,
            "clicked": False,
            "techStack": data.get("techStack", ""),
            "createdAt": datetime.utcnow()
        }

        recruiters_col.insert_one(recruiter)
        return {"message": "Recruiter added successfully", "name": name, "company": company}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding recruiter: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

# ---------------- LIST RECRUITERS ----------------

@app.get("/recruiters")
def list_recruiters(status: str = None):
    try:
        query = {}
        if status:
            query["status"] = status

        results = []
        for r in recruiters_col.find(query):
            r["_id"] = str(r["_id"])
            results.append(r)
        return results
    except Exception as e:
        logger.error(f"Error listing recruiters: {e}")
        raise HTTPException(status_code=500, detail="Error fetching data")

# ---------------- UPDATE STATUS ----------------

@app.patch("/recruiters/{email}")
def update_status(email: str, data: dict):
    try:
        update = {}
        if "status" in data: update["status"] = data["status"]
        if "replied" in data: update["replied"] = data["replied"]

        if not update:
            raise HTTPException(status_code=400, detail="No fields to update")

        result = recruiters_col.update_one({"email": email}, {"$set": update})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Recruiter not found")

        return {"message": "Recruiter updated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating status: {e}")
        raise HTTPException(status_code=500, detail="Update failed")

# ---------------- CSV IMPORT ----------------

@app.post("/recruiters/import-csv")
async def import_csv(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files allowed")

    try:
        content = await file.read()
        text = content.decode("utf-8-sig")  # strip BOM if present
        lines = text.splitlines()
        reader = csv.DictReader(lines)
        # Normalize headers: strip whitespace/CR and lowercase
        if reader.fieldnames:
            reader.fieldnames = [f.strip().lower() for f in reader.fieldnames]

        added, skipped = 0, 0
        for row in reader:
            # Normalize row keys too (handles any extra whitespace)
            norm_row = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
            email_addr = norm_row.get("email", "")
            if not email_addr:
                skipped += 1
                continue

            email_addr = email_addr.lower()
            if recruiters_col.find_one({"email": email_addr}):
                skipped += 1
                continue

            # Lead Enrichment
            name = norm_row.get("name", "")
            if not name:
                name = extract_first_name(email_addr)
            
            company = normalize_company(norm_row.get("company", ""))

            recruiter = {
                "email": email_addr,
                "name": name,
                "company": company,
                "status": "new",
                "sentAt": None,
                "replied": False,
                "followupSent": False,
                "followupStage": 0,
                "opened": False,
                "clicked": False,
                "techStack": norm_row.get("techstack", ""),
                "createdAt": datetime.utcnow()
            }
            recruiters_col.insert_one(recruiter)
            added += 1

        return {"message": "CSV import completed", "added": added, "skipped": skipped}
    except Exception as e:
        logger.error(f"CSV Import Error: {e}")
        raise HTTPException(status_code=500, detail="CSV processing failed")

@app.post("/recruiters/import-text")
async def import_text(data: CSVImportRequest):
    if not data.csvText:
        raise HTTPException(status_code=400, detail="CSV text is required")

    try:
        # Normalize line endings and strip BOM
        text = data.csvText.strip().replace("\r\n", "\n").replace("\r", "\n")
        lines = text.splitlines()
        if not lines:
            return {"message": "No data provided", "added": 0, "skipped": 0}

        reader = csv.DictReader(lines)
        # Normalize headers: strip whitespace/CR and lowercase
        if reader.fieldnames:
            reader.fieldnames = [f.strip().lower() for f in reader.fieldnames]

        added, skipped = 0, 0
        rows_seen = 0
        for row in reader:
            rows_seen += 1
            # Normalize row keys too
            norm_row = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
            email_addr = norm_row.get("email", "")
            logger.info(f"Processing row {rows_seen}: email='{email_addr}' norm_row={norm_row}")
            if not email_addr:
                logger.warning(f"Row {rows_seen} skipped: no email. Row data: {norm_row}")
                skipped += 1
                continue

            email_addr = email_addr.lower()
            if recruiters_col.find_one({"email": email_addr}):
                logger.info(f"Row {rows_seen} skipped: duplicate email '{email_addr}'")
                skipped += 1
                continue

            # Lead Enrichment
            name = norm_row.get("name", "")
            if not name:
                name = extract_first_name(email_addr)
            
            company = normalize_company(norm_row.get("company", ""))

            recruiter = {
                "email": email_addr,
                "name": name,
                "company": company,
                "status": "new",
                "sentAt": None,
                "replied": False,
                "followupSent": False,
                "followupStage": 0,
                "opened": False,
                "clicked": False,
                "techStack": norm_row.get("techstack", ""),
                "createdAt": datetime.utcnow()
            }
            recruiters_col.insert_one(recruiter)
            added += 1
            logger.info(f"Added recruiter: {email_addr}")

        return {"message": "Text import completed", "added": added, "skipped": skipped}
    except Exception as e:
        logger.error(f"CSV Text Import Error: {e}")
        raise HTTPException(status_code=500, detail="CSV processing failed")
# ---------------- EMAIL LOGIC ----------------
import requests

HF_API_KEY = os.getenv("HF_API_KEY", "")
HF_MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct"
HF_API_URL = "https://router.huggingface.co/v1/chat/completions"

# --- In-memory company sentence cache (reduces API calls, no external DB needed) ---
_company_sentence_cache: dict = {}

def _hf_generate(prompt: str, max_tokens: int = 60) -> str:
    """Call Hugging Face Inference API (free tier) using chat/completions format."""
    if not HF_API_KEY:
        return ""
    try:
        resp = requests.post(
            HF_API_URL,
            headers={"Authorization": f"Bearer {HF_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": HF_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.7
            },
            timeout=20
        )
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        else:
            logger.warning(f"HF API returned {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.error(f"HF API error: {e}")
    return ""

def generate_company_sentence(company: str) -> str:
    if company in _company_sentence_cache:
        return _company_sentence_cache[company]
    prompt = (
        f"Write one sentence (under 20 words) about {company} that is specific and engineering-focused. "
        f"Mention the company name. Reference engineering, technology, scale, or product impact. "
        f'Avoid generic phrases like "great company". Output only the sentence.'
    )
    result = _hf_generate(prompt)
    if result:
        _company_sentence_cache[company] = result
    return result

def generate_opening_line(company: str) -> str:
    prompt = (
        f"Write one short opening line (max 20 words) for a cold email to a recruiter at {company}. "
        f"I am a backend engineer interested in scalable systems and AI. "
        f"Reference {company}'s engineering scale or backend challenges. Natural, professional tone. Output only the sentence."
    )
    return _hf_generate(prompt)

def generate_subject_lines(company: str) -> list:
    prompt = (
        f"Generate exactly 5 short email subject lines for a Summer 2026 Backend Intern application at {company}. "
        f"Rules: max 6 words each, professional, curiosity-driven. "
        f"Output only the 5 lines, one per line, no numbering, no extra text."
    )
    raw = _hf_generate(prompt, max_tokens=120)
    if raw:
        lines = [l.strip().lstrip("0123456789.-*) ") for l in raw.split("\n") if l.strip()]
        lines = [l for l in lines if 0 < len(l) < 80][:5]
        if len(lines) >= 3:
            return lines
    # Fallback subjects
    return [
        f"Summer 2026 Backend Intern",
        f"Backend Intern — {company}",
        f"Quick Question About Internships",
        f"Engineer Interested in {company}",
        f"Internship Opportunity Inquiry",
    ]

def build_email(recruiter, template_doc=None):
    # Retrieve env variables
    resume_link = os.getenv("RESUME_LINK")
    if template_doc:
        html_template = template_doc.get("htmlBody", "")
        subject_template = template_doc.get("subject", "")
    else:
        html_template = os.getenv("EMAIL_TEMPLATE_HTML")
        subject_template = os.getenv("EMAIL_SUBJECT") # Get it as a template

    # Create personal variables
    name = recruiter.get("name") or "there"
    company = recruiter.get("company") or "your team"

    # --- AI Personalization (skip for generic domains like gmail.com) ---
    company_sentence = ""
    opening_line = ""
    recruiter_email = recruiter.get("email", "")
    
    if not is_generic_email(recruiter_email) and company != "your team":
        try:
            company_sentence = generate_company_sentence(company)
            opening_line = generate_opening_line(company)
        except Exception as e:
            logger.error(f"Error generating AI personalization: {e}")
    else:
        logger.info(f"Skipping AI personalization for generic domain: {recruiter_email}")

    # --- 1. Format the Subject with Company Name ---
    try:
        subject = subject_template.format(company=company)
    except Exception:
        subject = subject_template

    # --- 3. Tracking Setup ---
    tracking_base = os.getenv("TRACKING_BASE_URL", "").rstrip("/")
    pixel_img = ""
    if tracking_base:
        encoded_resume = urllib.parse.quote(resume_link)
        resume_link = f"{tracking_base}/track/click/{recruiter['email']}?url={encoded_resume}"
        pixel_img = f'<img src="{tracking_base}/track/open/{recruiter["email"]}" width="1" height="1" style="display:none;" />'

    # --- 4. Build Mailto Buttons (Psychological CTA) ---
    def make_mailto(subj, body_text):
        quoted_subj = urllib.parse.quote(subj)
        quoted_body = urllib.parse.quote(body_text)
        return f"mailto:rathodkavya2005@gmail.com?subject={quoted_subj}&body={quoted_body}"

    yes_link = make_mailto(f"Re: Internship @ {company}", f"Hi Kavya,\n\nI saw your application for {company}. Let's chat. When are you free?")
    no_link = make_mailto(f"Contact for Internship @ {company}", f"Hi Kavya,\n\nI'm not the best person to speak with. You should reach out to [Name/Email] instead.")
    
    mailto_html = f"""
    <div style="margin-top: 25px; padding: 15px; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0;">
        <p style="margin-top: 0; color: #64748b; font-size: 14px;">One-click quick reply:</p>
        <a href="{yes_link}" style="display: inline-block; padding: 10px 18px; background: #22c55e; color: white; text-decoration: none; border-radius: 6px; font-weight: 600; margin-right: 10px;">Yes, let's chat</a>
        <a href="{no_link}" style="display: inline-block; padding: 10px 18px; background: #94a3b8; color: white; text-decoration: none; border-radius: 6px; font-weight: 600;">Not the right person</a>
    </div>
    """

    # --- 5. Build the HTML content ---
    resume_url = resume_link
    resume_html = f'<a href="{resume_url}" target="_blank" style="color: #2563eb; font-weight: 600; text-decoration: underline;">Resume</a>'

    try:
        html_body = html_template.format(
            name=name,
            company=company,
            company_sentence=company_sentence,
            opening_line=opening_line,
            resume_url=resume_url,
            resume_link=resume_html
        )
    except KeyError as e:
        logger.error(f"Template formatting error: Missing key {e}")
        # Fallback replacement
        html_body = html_template.replace("{resume_link}", resume_html).replace("{name}", name).replace("{company}", company)
        html_body = html_body.replace("{company_sentence}", company_sentence).replace("{opening_line}", opening_line)

    # Inject Mailto Buttons and Tracking Pixel
    html_body += mailto_html
    html_body += pixel_img

    return {
        "To": recruiter["email"],
        "Subject": subject,
        "HTMLPart": html_body
    }
def send_email(email_data):
    """
    Sends the email data to the Google Apps Script Bridge.
    """
    SCRIPT_URL = os.getenv("GOOGLE_SCRIPT_URL") 
    
    # We pass the data exactly as the Google Script expects it
    payload = {
        "to": email_data["To"],
        "subject": email_data["Subject"],
        "htmlBody": email_data["HTMLPart"]
    }
    
    try:
        # Use a timeout so Render doesn't hang if Google is slow
        response = requests.post(SCRIPT_URL, json=payload, timeout=10)
        
        if response.status_code == 200:
            # Stricter check: Look for "Success" in the body
            if "Success" in response.text:
                logger.info(f"Email successfully delivered to Google Bridge for {email_data['To']}")
                return True, None
            else:
                error_msg = f"Google Bridge returned 200 but failed: {response.text}"
                logger.error(error_msg)
                return False, error_msg
        else:
            error_msg = f"Google Bridge Error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            return False, error_msg
    except Exception as e:
        error_msg = f"Failed to connect to Google Bridge: {e}"
        logger.error(error_msg)
        return False, error_msg

@app.post("/send-one")
def send_one_email(req: SendOneRequest = SendOneRequest()):
    try:
        recruiter = recruiters_col.find_one({"status": "new"})
        if not recruiter:
            return {"ok": False, "msg": "empty"} 
            
        template_doc = None
        template_id = req.templateId if req else None
        company = recruiter.get("company", "your team")
        
        # 1. Subject Line A/B Testing & AI Suggestions (skip for generic domains)
        ai_subjects = []
        recruiter_email = recruiter.get("email", "")
        if not is_generic_email(recruiter_email) and company != "your team":
            try:
                ai_subjects = generate_subject_lines(company)
            except Exception as e:
                logger.error(f"Error generating AI subject lines: {e}")

        if template_id:
            template_doc = templates_col.find_one({"_id": ObjectId(template_id)})
        else:
            # Selection logic
            initial_templates = list(templates_col.find({"type": "initial"}).sort("createdAt", 1))
            if initial_templates:
                total_sent = recruiters_col.count_documents({
                    "status": {"$in": ["sent", "replied", "error"]}, 
                    "followupStage": {"$in": [0, None]}
                })
                template_doc = initial_templates[total_sent % len(initial_templates)]
                template_id = str(template_doc["_id"])

        # 2. Build and Customize Subject
        email_data = build_email(recruiter, template_doc)
        
        # Override subject with AI variant if available (Rotation logic)
        if ai_subjects:
            total_sent_company = recruiters_col.count_documents({"company": company, "status": "sent"})
            chosen_subject = ai_subjects[total_sent_company % len(ai_subjects)]
            email_data["Subject"] = chosen_subject

        success, error_msg = send_email(email_data)

        if success:
            update_fields = {
                "status": "sent", 
                "sentAt": datetime.utcnow(),
                "subjectUsed": email_data["Subject"]
            }
            if template_doc:
                update_fields["templateUsed"] = str(template_doc["_id"])
                update_fields["templateName"] = template_doc.get("name")

            recruiters_col.update_one(
                {"_id": recruiter["_id"]},
                {"$set": update_fields}
            )
            return {"ok":True, "subject": email_data["Subject"]}
        else:
            recruiters_col.update_one(
                {"_id": recruiter["_id"]},
                {"$set": {"status": "error", "errorDetail": error_msg}}
            )
            return {"ok":False, "err": error_msg}
    except Exception as e:
        logger.error(f"Error in send_one_email: {e}")
        return {"ok":False , "err":"fail"}
# ---------------- REPLY CHECKER ----------------

def check_replies():
    try:
        mail = imaplib.IMAP4_SSL(os.getenv("IMAP_SERVER"), int(os.getenv("IMAP_PORT")))
        mail.login(os.getenv("GMAIL_ID"), os.getenv("GMAIL_APP_PASSWORD"))
        mail.select("inbox")

        status, messages = mail.search(None, 'UNSEEN')
        if status != "OK":
            mail.logout()
            return 0

        updated = 0
        for e_id in messages[0].split():
            _, msg_data = mail.fetch(e_id, "(RFC822)")
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            sender = email.utils.parseaddr(msg.get("From"))[1].lower()
            subject = msg.get("Subject", "")

            body_snippet = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body_snippet = part.get_payload(decode=True).decode(errors="ignore")[:200]
                        break
            else:
                body_snippet = msg.get_payload(decode=True).decode(errors="ignore")[:200]

            result = recruiters_col.update_one(
                {"email": sender, "replied": False},
                {"$set": {
                    "replied": True, "status": "replied",
                    "replyAt": datetime.utcnow(), "replySubject": subject,
                    "replySnippet": body_snippet
                }}
            )
            if result.modified_count: updated += 1
        
        mail.logout()
        return updated
    except Exception as e:
        logger.error(f"IMAP Error: {e}")
        return 0

@app.post("/check-replies")
def check_replies_api():
    updated = check_replies()
    return {"ok": True, "count": updated} # Keep it short
# ---------------- FOLLOW UP ----------------
import os
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone

# ---------------- FOLLOW UP LOGIC ----------------

def build_followup_email(recruiter, stage):
    """
    Builds the follow-up email with behavioral branching.
    """
    rec_name = recruiter.get("name") or "there"
    rec_company = recruiter.get("company") or "your company"
    clicked = recruiter.get("clicked", False)
    opened = recruiter.get("opened", False)
    resume_link = os.getenv("RESUME_LINK")
    
    # 1. Determine Behavioral Subject/Body
    if stage == 1:
        if clicked:
            subject_template = "Glad you saw my resume | Kavya @ {company}"
            html_template = """<p>Hi {name},</p>
            <p>I noticed you took a look at my resume earlier — happy to provide more details if helpful.</p>
            <p>I'm really excited about the work {company} is doing and would love to discuss how my background in building high-traffic systems could be a fit for your Summer '26 internship roles.</p>
            <p>Do you have 10 minutes for a quick chat later this week?</p>"""
        elif opened:
            subject_template = "Quick question about {company} internship"
            html_template = """<p>Hi {name},</p>
            <p>Just checking in in case my previous email got buried. Would love to connect if you're considering Summer '26 interns.</p>
            <p>I've attached my {resume_link} again for convenience. Would you be open to a brief chat?</p>"""
        else:
            # Scenario 3: Not opened - Resend with new subject line
            subject_template = "Quick question about internships"
            html_template = os.getenv("EMAIL_TEMPLATE_HTML", "<p>Hi {name},</p><p>I'm follow up on my internship application at {company}. I've attached my {resume_link} for your review.</p>")
    else:
        # Stage 2 (Breakup)
        subject_template = os.getenv("BREAKUP_SUBJECT", "Wrapping up | Summer '26 Intern @{company}")
        html_template = os.getenv("BREAKUP_TEMPLATE_HTML")

    # 2. Format the Subject
    try:
        subject = subject_template.format(company=rec_company)
    except Exception:
        subject = f"Following up | {rec_company}"

    # 3. Add Tracking
    tracking_base = os.getenv("TRACKING_BASE_URL", "").rstrip("/")
    pixel_img = ""
    if tracking_base:
        encoded_resume = urllib.parse.quote(resume_link)
        resume_link = f"{tracking_base}/track/click/{recruiter['email']}?url={encoded_resume}"
        pixel_img = f'<img src="{tracking_base}/track/open/{recruiter["email"]}" width="1" height="1" style="display:none;" />'

    # 4. Build Mailto Buttons
    def make_mailto(subj, body_text):
        quoted_subj = urllib.parse.quote(subj)
        quoted_body = urllib.parse.quote(body_text)
        return f"mailto:rathodkavya2005@gmail.com?subject={quoted_subj}&body={quoted_body}"

    yes_link = make_mailto(f"Re: Internship @ {rec_company}", f"Hi Kavya,\n\nI saw your application. Let's chat. When are you free?")
    no_link = make_mailto(f"Contact for Internship @ {rec_company}", f"Hi Kavya,\n\nI'm not the best person to speak with. You should reach out to [Name/Email] instead.")
    
    mailto_html = f"""
    <div style="margin-top: 25px; padding: 15px; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0;">
        <p style="margin-top: 0; color: #64748b; font-size: 14px;">One-click quick reply:</p>
        <a href="{yes_link}" style="display: inline-block; padding: 10px 18px; background: #22c55e; color: white; text-decoration: none; border-radius: 6px; font-weight: 600; margin-right: 10px;">Yes, let's chat</a>
        <a href="{no_link}" style="display: inline-block; padding: 10px 18px; background: #94a3b8; color: white; text-decoration: none; border-radius: 6px; font-weight: 600;">Not the right person</a>
    </div>
    """

    # 5. Build HTML Body
    resume_url = resume_link
    resume_html = f'<a href="{resume_url}" target="_blank" style="color: #2563eb; font-weight: 600; text-decoration: underline;">Resume</a>'

    try:
        html_body = html_template.format(
            name=rec_name,
            company=rec_company,
            resume_url=resume_url,
            resume_link=resume_html
        )
    except Exception:
        html_body = html_template.replace("{resume_link}", resume_html).replace("{name}", rec_name).replace("{company}", rec_company)

    html_body += mailto_html
    html_body += pixel_img

    return {
        "To": recruiter["email"],
        "Subject": subject,
        "HTMLPart": html_body
    }

def send_followup_if_due():
    """
    Checks for exactly ONE recruiter due for a followup.
    """
    try:
        now = datetime.now(timezone.utc)

        # Query Logic:
        # 1. Status is 'sent' AND No Reply yet
        # 2. AND (Either it's stage 0 and 4 days have passed OR stage 1 and 6 days have passed since last)
        query = {
            "status": "sent",
            "replied": False,
            "$or": [
                {
                    # Scenario 2: Resume clicked but no reply (24-48 hours)
                    "clicked": True,
                    "followupStage": {"$in": [0, None]},
                    "sentAt": {"$lte": now - timedelta(hours=36)}
                },
                {
                    # Scenario 1: Opened but no reply (3 days)
                    "opened": True,
                    "clicked": False,
                    "followupStage": {"$in": [0, None]},
                    "sentAt": {"$lte": now - timedelta(days=3)}
                },
                {
                    # Scenario 3: Not opened (Resend after 4 days)
                    "opened": False,
                    "followupStage": {"$in": [0, None]},
                    "sentAt": {"$lte": now - timedelta(days=4)}
                },
                {
                    # Stage 2 breakup (6 days after last followup)
                    "followupStage": 1,
                    "followupAt": {"$lte": now - timedelta(days=6)}
                }
            ]
        }

        recruiter = recruiters_col.find_one(query)

        if not recruiter:
            logger.info("No follow-ups due at this time.")
            return {"status": "no followups due"}

        logger.info(f"Found due follow-up for: {recruiter['email']}")

        # Determine next stage
        current_stage = recruiter.get("followupStage", 0)
        next_stage = current_stage + 1

        # Build the email data
        email_data = build_followup_email(recruiter, next_stage)
        
        # Check if body is empty before sending
        if not email_data["HTMLPart"]:
            error_msg = "Empty body generated"
            logger.error(f"ABORTING: {error_msg} for {recruiter['email']}")
            recruiters_col.update_one({"_id": recruiter["_id"]}, {"$set": {"status": "error", "errorDetail": error_msg}})
            return {"status": "error", "detail": error_msg}

        # SEND using the existing working function
        success, error_msg = send_email(email_data)

        if success:
            # Update Database
            update_fields = {
                "followupSent": True,
                "followupAt": now,
                "followupStage": next_stage
            }
            if email_data.get("templateUsed"):
                update_fields["templateUsed"] = email_data["templateUsed"]
                update_fields["templateName"] = email_data["templateName"]

            recruiters_col.update_one(
                {"_id": recruiter["_id"]},
                {"$set": update_fields}
            )

            logger.info(f"Follow-up Stage {next_stage} marked as sent for {recruiter['email']}")
            return {
                "status": "followup sent", 
                "email": recruiter["email"],
                "company": recruiter.get("company")
            }
        else:
            recruiters_col.update_one(
                {"_id": recruiter["_id"]},
                {
                    "$set": {
                        "status": "error",
                        "errorDetail": error_msg
                    }
                }
            )
            return {"status": "error", "detail": error_msg}

    except Exception as e:
        logger.error(f"Follow-up Process Error: {e}")
        return {"status": "error", "detail": str(e)}
    
@app.post("/send-followup")
def send_followup_api():
    return send_followup_if_due()

@app.get("/dashboard/analytics")
def dashboard_analytics():
    try:
        pipeline_sent = [
            {"$match": {"sentAt": {"$ne": None}}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$sentAt"}},
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]
        sent_per_day = list(recruiters_col.aggregate(pipeline_sent))

        pipeline_templates = [
            {"$match": {"status": {"$in": ["sent", "replied"]}}},
            {"$group": {
                "_id": {"$ifNull": ["$templateName", "Default"]},
                "sent": {"$sum": 1},
                "opened": {"$sum": {"$cond": [{"$eq": ["$opened", True]}, 1, 0]}},
                "clicked": {"$sum": {"$cond": [{"$eq": ["$clicked", True]}, 1, 0]}},
                "replied": {"$sum": {"$cond": [{"$eq": ["$replied", True]}, 1, 0]}}
            }}
        ]
        template_metrics = list(recruiters_col.aggregate(pipeline_templates))

        return {
            "sentPerDay": [{"date": x["_id"], "count": x["count"]} for x in sent_per_day],
            "templateMetrics": [{"name": x["_id"], "sent": x["sent"], "opened": x["opened"], "clicked": x["clicked"], "replied": x["replied"]} for x in template_metrics]
        }
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        raise HTTPException(status_code=500, detail="Analytics error")

@app.get("/dashboard/stats")
def dashboard_stats():
    try:
        return {
            "total": recruiters_col.count_documents({}),
            "new": recruiters_col.count_documents({"status": "new"}),
            "sent": recruiters_col.count_documents({"status": "sent"}),
            "replied": recruiters_col.count_documents({"status": "replied"}),
            "errors": recruiters_col.count_documents({"status": "error"}),
            "followups": recruiters_col.count_documents({"followupSent": True}),
            "opened": recruiters_col.count_documents({"opened": True}),
            "clicked": recruiters_col.count_documents({"clicked": True})
        }
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail="Database connection error")

@app.get("/dashboard/recruiters")
def dashboard_recruiters(status: str = None):
    try:
        query = {}
        if status: query["status"] = status
        data = []
        for r in recruiters_col.find(query).sort("createdAt", -1):
            r["_id"] = str(r["_id"])
            # Ensure PyMongo's naive UTC datetimes are serialized as UTC by appending 'Z'
            for key, value in r.items():
                if hasattr(value, "isoformat"):
                    r[key] = value.isoformat() + "Z"
            data.append(r)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail="Database connection error")

@app.post("/test-email")
def test_email_endpoint(data: TestEmailRequest):
    try:
        req_data = data.dict()
        recruiter = {
            "_id": "test_id_123",
            "email": req_data["email"],
            "name": req_data["name"],
            "company": req_data["company"]
        }
        
        template_type = req_data.get("templateType", "initial")
        
        if template_type == "initial":
            template_doc = None
            if req_data.get("templateId"):
                template_doc = templates_col.find_one({"_id": ObjectId(req_data["templateId"])})
            email_data = build_email(recruiter, template_doc)
        elif template_type == "followup1":
            email_data = build_followup_email(recruiter, stage=1)
        elif template_type == "breakup":
            email_data = build_followup_email(recruiter, stage=2)
        else:
            return {"status": "error", "detail": "Invalid template type"}
            
        success, error_msg = send_email(email_data)
        
        if success:
            return {"status": "success", "message": f"Sent {template_type} email to {recruiter['email']}"}
        else:
            return {"status": "error", "detail": error_msg}
            
    except Exception as e:
        logger.error(f"Test email error: {e}")
        return {"status": "error", "detail": str(e)}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)