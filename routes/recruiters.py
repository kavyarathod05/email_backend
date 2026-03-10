"""
Recruiter management routes: add, list, update, CSV/text import.
"""

import csv
import re
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File

from config import recruiters_col, logger
from models import CSVImportRequest

router = APIRouter(prefix="/recruiters", tags=["recruiters"])


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


@router.post("")
def add_recruiter(data: dict):
    try:
        email_addr = data.get("email")
        if not email_addr:
            raise HTTPException(status_code=400, detail="Email is required")

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
            "createdAt": datetime.utcnow(),
        }

        recruiters_col.insert_one(recruiter)
        return {"message": "Recruiter added successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding recruiter: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("")
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


@router.patch("/{email}")
def update_status(email: str, data: dict):
    try:
        update = {}
        if "status" in data:
            update["status"] = data["status"]
        if "replied" in data:
            update["replied"] = data["replied"]

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


# --------------- CSV / Text Import ---------------


def _build_recruiter_from_row(norm_row: dict) -> dict:
    """Build a recruiter document from a normalised CSV row."""
    # Lead Enrichment
    email_addr = norm_row["email"]
    name = norm_row.get("name", "")
    if not name:
        name = extract_first_name(email_addr)

    company = normalize_company(norm_row.get("company", ""))

    return {
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
        "createdAt": datetime.utcnow(),
    }


@router.post("/import-csv")
async def import_csv(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files allowed")

    try:
        content = await file.read()
        text = content.decode("utf-8-sig")
        lines = text.splitlines()
        reader = csv.DictReader(lines)
        if reader.fieldnames:
            reader.fieldnames = [f.strip().lower() for f in reader.fieldnames]

        added, skipped = 0, 0
        for row in reader:
            norm_row = {
                k.strip().lower(): (v or "").strip() for k, v in row.items() if k
            }
            email_addr = norm_row.get("email", "")
            if not email_addr:
                skipped += 1
                continue

            email_addr = email_addr.lower()
            norm_row["email"] = email_addr
            if recruiters_col.find_one({"email": email_addr}):
                skipped += 1
                continue

            recruiters_col.insert_one(_build_recruiter_from_row(norm_row))
            added += 1

        return {"message": "CSV import completed", "added": added, "skipped": skipped}
    except Exception as e:
        logger.error(f"CSV Import Error: {e}")
        raise HTTPException(status_code=500, detail="CSV processing failed")


@router.post("/import-text")
async def import_text(data: CSVImportRequest):
    if not data.csvText:
        raise HTTPException(status_code=400, detail="CSV text is required")

    try:
        text = data.csvText.strip().replace("\r\n", "\n").replace("\r", "\n")
        lines = text.splitlines()
        if not lines:
            return {"message": "No data provided", "added": 0, "skipped": 0}

        reader = csv.DictReader(lines)
        if reader.fieldnames:
            reader.fieldnames = [f.strip().lower() for f in reader.fieldnames]

        added, skipped, rows_seen = 0, 0, 0
        for row in reader:
            rows_seen += 1
            norm_row = {
                k.strip().lower(): (v or "").strip() for k, v in row.items() if k
            }
            email_addr = norm_row.get("email", "")
            logger.info(
                f"Processing row {rows_seen}: email='{email_addr}' norm_row={norm_row}"
            )
            if not email_addr:
                logger.warning(
                    f"Row {rows_seen} skipped: no email. Row data: {norm_row}"
                )
                skipped += 1
                continue

            email_addr = email_addr.lower()
            norm_row["email"] = email_addr
            if recruiters_col.find_one({"email": email_addr}):
                logger.info(f"Row {rows_seen} skipped: duplicate email '{email_addr}'")
                skipped += 1
                continue

            recruiters_col.insert_one(_build_recruiter_from_row(norm_row))
            added += 1
            logger.info(f"Added recruiter: {email_addr}")

        return {"message": "Text import completed", "added": added, "skipped": skipped}
    except Exception as e:
        logger.error(f"CSV Text Import Error: {e}")
        raise HTTPException(status_code=500, detail="CSV processing failed")
