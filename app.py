from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime
import uvicorn
import os
import csv
from fastapi import UploadFile, File
import smtplib
from email.message import EmailMessage
import imaplib
import email
from fastapi.middleware.cors import CORSMiddleware

# Load env variables
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB")

if not MONGO_URI or not MONGO_DB:
    raise Exception("Missing MongoDB environment variables")

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]

recruiters_col = db["temp"]

app = FastAPI()
frontend_origin = os.getenv("FRONTEND_ORIGIN")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- HEALTH ----------------

@app.get("/")
def health():
    return {"status": "Recruiter API running"}

# ---------------- ADD RECRUITER ----------------

@app.post("/recruiters")
def add_recruiter(data: dict):
    email = data.get("email")

    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    # prevent duplicates
    if recruiters_col.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="Recruiter already exists")

    recruiter = {
        "email": email,
        "name": data.get("name", ""),
        "company": data.get("company", ""),
        "status": "new",          # new | sent | replied
        "sentAt": None,
        "replied": False,
        "followupSent": False,
        "createdAt": datetime.utcnow()
    }

    recruiters_col.insert_one(recruiter)
    return {"message": "Recruiter added successfully"}

# ---------------- LIST RECRUITERS ----------------

@app.get("/recruiters")
def list_recruiters(status: str = None):
    query = {}
    if status:
        query["status"] = status

    results = []
    for r in recruiters_col.find(query):
        r["_id"] = str(r["_id"])
        results.append(r)

    return results

# ---------------- UPDATE STATUS ----------------

@app.patch("/recruiters/{email}")
def update_status(email: str, data: dict):
    update = {}

    if "status" in data:
        update["status"] = data["status"]

    if "replied" in data:
        update["replied"] = data["replied"]

    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = recruiters_col.update_one(
        {"email": email},
        {"$set": update}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Recruiter not found")

    return {"message": "Recruiter updated"}

@app.post("/recruiters/import-csv")
async def import_csv(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files allowed")

    content = await file.read()
    lines = content.decode("utf-8").splitlines()
    reader = csv.DictReader(lines)

    added = 0
    skipped = 0

    for row in reader:
        email = row.get("Email")
        if not email:
            skipped += 1
            continue

        email = email.strip().lower()

        # skip duplicates
        if recruiters_col.find_one({"email": email}):
            skipped += 1
            continue

        recruiter = {
            "email": email,
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

    return {
        "message": "CSV import completed",
        "added": added,
        "skipped": skipped
    }

EMAIL_SUBJECT = "Full-Stack / AI Intern | IIIT Gwalior | Summer 2026"

def build_email(recruiter):
    msg = EmailMessage()
    msg["From"] = os.getenv("GMAIL_ID")
    msg["To"] = recruiter["email"]
    msg["Subject"] = os.getenv("EMAIL_SUBJECT")

    html_template = os.getenv("EMAIL_TEMPLATE_HTML")
    resume_link = os.getenv("RESUME_LINK")

    if not html_template or not resume_link:
        raise Exception("EMAIL_TEMPLATE_HTML or RESUME_LINK missing in env")

    html_body = html_template.format(
        name=recruiter.get("name") or "there",
        company=recruiter.get("company") or "your team",
        resume_link=resume_link
    )

    # Plain-text fallback (important for deliverability)
    msg.set_content(
        f"Hi {recruiter.get('name','there')},\n\nPlease view my resume here:\n{resume_link}"
    )

    # HTML version (Gmail will use this)
    msg.add_alternative(html_body, subtype="html")

    return msg


def send_email(msg):
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(
            os.getenv("GMAIL_ID"),
            os.getenv("GMAIL_APP_PASSWORD")
        )
        server.send_message(msg)


@app.post("/send-one")
def send_one_email():
    recruiter = recruiters_col.find_one({"status": "new"})

    if not recruiter:
        return {"status": "no recruiters left"}

    msg = build_email(recruiter)
    send_email(msg)

    recruiters_col.update_one(
        {"_id": recruiter["_id"]},
        {
            "$set": {
                "status": "sent",
                "sentAt": datetime.utcnow()
            }
        }
    )

    return {
        "status": "email sent",
        "email": recruiter["email"]
    }


def check_replies():
    mail = imaplib.IMAP4_SSL(
        os.getenv("IMAP_SERVER"),
        int(os.getenv("IMAP_PORT"))
    )

    mail.login(
        os.getenv("GMAIL_ID"),
        os.getenv("GMAIL_APP_PASSWORD")
    )

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

        # Extract short body snippet
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
            {
                "$set": {
                    "replied": True,
                    "status": "replied",
                    "replyAt": datetime.utcnow(),
                    "replySubject": subject,
                    "replySnippet": body_snippet
                }
            }
        )

        if result.modified_count:
            updated += 1

    mail.logout()
    return updated

@app.post("/check-replies")
def check_replies_api():
    updated = check_replies()
    return {
        "status": "checked",
        "replies_marked": updated
    }

def build_followup_email(recruiter):
    msg = EmailMessage()
    msg["From"] = os.getenv("GMAIL_ID")
    msg["To"] = recruiter["email"]
    msg["Subject"] = os.getenv("FOLLOWUP_SUBJECT")

    html_template = os.getenv("FOLLOWUP_TEMPLATE_HTML")
    resume_link = os.getenv("RESUME_LINK")

    html_body = html_template.format(
        name=recruiter.get("name") or "there",
        company=recruiter.get("company") or "your team",
        resume_link=resume_link
    )

    msg.set_content(
        f"Hi {recruiter.get('name','there')},\n\nJust following up on my previous email.\n\nResume: {resume_link}"
    )
    msg.add_alternative(html_body, subtype="html")

    return msg

from datetime import timedelta

def send_followup_if_due():
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    recruiter = recruiters_col.find_one({
        "status": "sent",
        "replied": False,
        "followupSent": False,
        "sentAt": {"$lte": seven_days_ago}
    })

    if not recruiter:
        return {"status": "no followups due"}

    msg = build_followup_email(recruiter)
    send_email(msg)

    recruiters_col.update_one(
        {"_id": recruiter["_id"]},
        {
            "$set": {
                "followupSent": True,
                "followupAt": datetime.utcnow()
            }
        }
    )

    return {
        "status": "followup sent",
        "email": recruiter["email"]
    }


@app.post("/send-followup")
def send_followup_api():
    return send_followup_if_due()


@app.get("/dashboard/stats")
def dashboard_stats():
    return {
        "total": recruiters_col.count_documents({}),
        "new": recruiters_col.count_documents({"status": "new"}),
        "sent": recruiters_col.count_documents({"status": "sent"}),
        "replied": recruiters_col.count_documents({"status": "replied"})
    }


@app.get("/dashboard/recruiters")
def dashboard_recruiters(status: str = None):
    query = {}
    if status:
        query["status"] = status

    data = []
    for r in recruiters_col.find(query).sort("createdAt", -1):
        r["_id"] = str(r["_id"])
        data.append(r)

    return data


@app.get("/dashboard/stats")
def dashboard_stats():
    return {
        "total": recruiters_col.count_documents({}),
        "new": recruiters_col.count_documents({"status": "new"}),
        "sent": recruiters_col.count_documents({"status": "sent"}),
        "replied": recruiters_col.count_documents({"status": "replied"})
    }


@app.get("/dashboard/recruiters")
def dashboard_recruiters(status: str = None):
    query = {}
    if status:
        query["status"] = status

    data = []
    for r in recruiters_col.find(query).sort("createdAt", -1):
        r["_id"] = str(r["_id"])
        data.append(r)

    return data

if __name__ == "__main__":
    # Use the PORT provided by Render or default to 10000
    port = int(os.getenv("PORT", 10000))
    # '0.0.0.0' is required for Render to route traffic to your app
    uvicorn.run(app, host="0.0.0.0", port=port)