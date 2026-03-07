from fastapi import FastAPI, HTTPException, UploadFile, File, status, Response, Query
from fastapi.responses import RedirectResponse
from pymongo import MongoClient
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

class TestEmailRequest(BaseModel):
    email: str
    name: str = "Test Name"
    company: str = "Test Company"
    templateType: str = "initial"

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

        if recruiters_col.find_one({"email": email_addr}):
            raise HTTPException(status_code=409, detail="Recruiter already exists")

        recruiter = {
            "email": email_addr,
            "name": data.get("name", ""),
            "company": data.get("company", ""),
            "status": "new",
            "sentAt": None,
            "replied": False,
            "followupSent": False,
            "followupStage": 0,
            "opened": False,
            "clicked": False,
            "createdAt": datetime.utcnow()
        }

        recruiters_col.insert_one(recruiter)
        return {"message": "Recruiter added successfully"}
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
        lines = content.decode("utf-8").splitlines()
        reader = csv.DictReader(lines)

        added, skipped = 0, 0
        for row in reader:
            email_addr = row.get("Email")
            if not email_addr:
                skipped += 1
                continue

            email_addr = email_addr.strip().lower()
            if recruiters_col.find_one({"email": email_addr}):
                skipped += 1
                continue

            recruiter = {
                "email": email_addr,
                "name": row.get("Name", "").strip(),
                "company": row.get("Company", "").strip(),
                "status": "new",
                "sentAt": None,
                "replied": False,
                "followupSent": False,
                "createdAt": datetime.utcnow()
            }
            recruiters_col.insert_one(recruiter)
            added += 1

        return {"message": "CSV import completed", "added": added, "skipped": skipped}
    except Exception as e:
        logger.error(f"CSV Import Error: {e}")
        raise HTTPException(status_code=500, detail="CSV processing failed")

# ---------------- EMAIL LOGIC ----------------
import requests

def build_email(recruiter):
    # Retrieve env variables
    resume_link = os.getenv("RESUME_LINK")
    html_template = os.getenv("EMAIL_TEMPLATE_HTML")
    subject_template = os.getenv("EMAIL_SUBJECT") # Get it as a template

    # Create personal variables
    name = recruiter.get("name") or "there"
    company = recruiter.get("company") or "your team"

    # --- 1. Format the Subject with Company Name ---
    try:
        # This replaces {company} in the subject line
        subject = subject_template.format(company=company)
    except Exception:
        # Fallback if format fails or placeholder is missing
        subject = subject_template

    # --- 2. Add Tracking if available ---
    tracking_base = os.getenv("TRACKING_BASE_URL", "").rstrip("/")
    pixel_img = ""
    if tracking_base:
        encoded_resume = urllib.parse.quote(resume_link)
        resume_link = f"{tracking_base}/track/click/{recruiter['email']}?url={encoded_resume}"
        pixel_img = f'<img src="{tracking_base}/track/open/{recruiter["email"]}" width="1" height="1" style="display:none;" />'

    # --- 3. Build the HTML content ---
    html_body = html_template.format(
        name=name,
        company=company,
        resume_link=resume_link
    )
    html_body += pixel_img

    # Return a clean dictionary that the Google Script understands
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
            logger.info(f"Email successfully delivered to Google Bridge for {email_data['To']}")
            return True, None
        else:
            error_msg = f"Google Bridge Error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            return False, error_msg
    except Exception as e:
        error_msg = f"Failed to connect to Google Bridge: {e}"
        logger.error(error_msg)
        return False, error_msg

@app.post("/send-one")
def send_one_email():
    try:
        recruiter = recruiters_col.find_one({"status": "new"})
        if not recruiter:
            return {"ok": False, "msg": "empty"} # Minimal response
        # build_email now returns a dict, not an EmailMessage object
        email_data = build_email(recruiter)
        success, error_msg = send_email(email_data)

        if success:
            recruiters_col.update_one(
                {"_id": recruiter["_id"]},
                {"$set": {"status": "sent", "sentAt": datetime.utcnow()}}
            )
            return {"ok":True}
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
    Builds the follow-up email matching the 'send-one' structure exactly.
    """
    # 1. Get Data & Defaults
    rec_name = recruiter.get("name") or "there"
    rec_company = recruiter.get("company") or "your company"
    
    # 2. Load Configuration from ENV based on stage
    resume_link = os.getenv("RESUME_LINK")
    if stage == 1:
        subject_template = os.getenv("FOLLOWUP_SUBJECT", "Following up | Summer '26 Intern @{company}")
        html_template = os.getenv("FOLLOWUP_TEMPLATE_HTML")
    else:
        subject_template = os.getenv("BREAKUP_SUBJECT", "Wrapping up | Summer '26 Intern @{company}")
        html_template = os.getenv("BREAKUP_TEMPLATE_HTML")
    
    # --- LOGGING START ---
    logger.info(f"Building follow-up stage {stage} for: {recruiter['email']}")
    if not html_template:
        logger.error(f"CRITICAL: Template is missing or empty in .env for stage {stage}")
    # --- LOGGING END ---

    # 3. Format the Subject
    try:
        subject = subject_template.format(company=rec_company)
    except Exception as e:
        logger.warning(f"Subject format failed: {e}. Using fallback.")
        subject = f"Following up | Summer '26 Intern @{rec_company}" if stage == 1 else f"Wrapping up | Summer '26 Intern @{rec_company}"

    # 4. Add Tracking if available
    tracking_base = os.getenv("TRACKING_BASE_URL", "").rstrip("/")
    pixel_img = ""
    if tracking_base:
        encoded_resume = urllib.parse.quote(resume_link)
        resume_link = f"{tracking_base}/track/click/{recruiter['email']}?url={encoded_resume}"
        pixel_img = f'<img src="{tracking_base}/track/open/{recruiter["email"]}" width="1" height="1" style="display:none;" />'

    # 5. Format the HTML Body
    if html_template:
        try:
            html_body = html_template.format(
                name=rec_name,
                company=rec_company,
                resume_link=resume_link
            )
            html_body += pixel_img
            # Log length to verify it's not empty
            logger.info(f"Generated HTML Body Length: {len(html_body)} chars")
        except KeyError as e:
            logger.error(f"Template Error: Missing placeholder {e} in template")
            html_body = f"<p>Hi {rec_name}, just following up for {rec_company}. (Template Error)</p>" + pixel_img
        except Exception as e:
            logger.error(f"Body formatting failed: {e}")
            html_body = f"<p>Hi {rec_name}, just following up for {rec_company}.</p>" + pixel_img
    else:
        # Fallback if ENV is missing
        html_body = f"<p>Hi {rec_name}, just following up for {rec_company}.</p>" + pixel_img

    # 6. RETURN DICTIONARY (Crucial: Matches build_email structure)
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
                    "followupStage": {"$in": [0, None]},
                    "sentAt": {"$lte": now - timedelta(days=4)}
                },
                {
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
            recruiters_col.update_one(
                {"_id": recruiter["_id"]},
                {
                    "$set": {
                        "followupSent": True,
                        "followupAt": now,
                        "followupStage": next_stage
                    }
                }
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
            email_data = build_email(recruiter)
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