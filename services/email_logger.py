"""
Service to log all generated outreach and test emails into MongoDB.
"""

from datetime import datetime
from config import emails_col, logger

def save_generated_email(
    recruiter: dict,
    subject: str,
    body: str,
    stage: int | str,
    status: str,
    error_detail: str | None = None,
    message_id: str | None = None,
    template_id: str | None = None,
    template_name: str | None = None
) -> str | None:
    """
    Saves a generated email record in the database.
    """
    try:
        doc = {
            "recruiterEmail": recruiter.get("email"),
            "recruiterName": recruiter.get("name") or "there",
            "company": recruiter.get("company") or "",
            "companyType": recruiter.get("companyType") or "startup",
            "subject": subject,
            "body": body,
            "stage": stage,
            "status": status,
            "errorDetail": error_detail,
            "messageId": message_id,
            "templateId": template_id,
            "templateName": template_name,
            "sentAt": datetime.utcnow()
        }
        
        result = emails_col.insert_one(doc)
        logger.info(f"Stored generated email for {recruiter.get('email')} (Stage: {stage}, Collection ID: {result.inserted_id})")
        return str(result.inserted_id)
    except Exception as e:
        logger.error(f"Failed to store generated email to MongoDB: {e}")
        return None
