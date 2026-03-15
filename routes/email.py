"""
Email action routes: send-one, test-email, check-replies, send-followup.
"""

from datetime import datetime
import re
from bson import ObjectId
from fastapi import APIRouter

from config import recruiters_col, templates_col, logger
from models import TestEmailRequest, SendOneRequest
from services.email_builder import build_email, build_followup_email
from services.email_sender import send_email, is_blacklisted
from services.reply_checker import check_replies
from services.followup import send_followup_if_due

router = APIRouter(tags=["email"])


@router.post("/send-one")
def send_one_email(req: SendOneRequest = SendOneRequest()):
    try:
        recruiter = recruiters_col.find_one({"status": "new"})
        if not recruiter:
            logger.warning("No recruiters found with status 'new'")
            return {"ok": False, "msg": "empty"}

        # 0. Blacklist check
        if is_blacklisted(recruiter["email"]):
            logger.warning(f"Skipping {recruiter['email']} - Blacklisted")
            recruiters_col.update_one(
                {"_id": recruiter["_id"]}, {"$set": {"status": "blacklisted"}}
            )
            return {"ok": False, "msg": "blacklisted"}

        # 0.5. Verification check
        if recruiter.get("is_fake"):
            logger.warning(f"Skipping {recruiter['email']} - Marked as Fake/Invalid")
            recruiters_col.update_one(
                {"_id": recruiter["_id"]}, {"$set": {"status": "skipped_fake"}}
            )
            return {"ok": False, "msg": "fake"}

        logger.info(
            f"Starting email process for {recruiter['email']} ({recruiter.get('company')})"
        )

        template_doc = None
        template_id = req.templateId if req else None

        if template_id:
            template_doc = templates_col.find_one({"_id": ObjectId(template_id)})
        else:
            # Round-robin selection for initial templates
            initial_templates = list(
                templates_col.find({"type": "initial"}).sort("createdAt", 1)
            )
            if initial_templates:
                total_sent = recruiters_col.count_documents(
                    {
                        "status": {"$in": ["sent", "replied", "error"]},
                        "followupStage": {"$in": [0, None]},
                    }
                )
                template_doc = initial_templates[total_sent % len(initial_templates)]
                template_id = str(template_doc["_id"])

        email_data = build_email(recruiter, template_doc)

        success, error_msg = send_email(email_data)

        if success:
            update_fields = {
                "status": "sent",
                "sentAt": datetime.utcnow(),
                "subjectUsed": email_data["Subject"],
            }
            if template_doc:
                update_fields["templateUsed"] = str(template_doc["_id"])
                update_fields["templateName"] = template_doc.get("name")

            recruiters_col.update_one(
                {"_id": recruiter["_id"]}, {"$set": update_fields}
            )
            return {"ok": True}
        else:
            recruiters_col.update_one(
                {"_id": recruiter["_id"]},
                {"$set": {"status": "error", "errorDetail": error_msg}},
            )
            return {"ok": False, "err": error_msg}
    except Exception as e:
        logger.error(f"Error in send_one_email: {e}")
        return {"ok": False, "err": "fail"}


@router.post("/test-email")
def test_email_endpoint(data: TestEmailRequest):
    """
    Send a test email using any template type.
    Supports: initial, followup1, breakup.
    When a templateId is provided, the selected DB template is used
    regardless of type.
    """
    try:
        req_data = data.dict()
        logger.info(
            f"Test email request received for {req_data['email']} ({req_data['company']})"
        )
        recruiter = {
            "_id": "test_id_123",
            "email": req_data["email"],
            "name": req_data["name"],
            "company": req_data["company"],
        }

        template_type = req_data.get("templateType", "initial")
        template_id = req_data.get("templateId")

        # Load explicit DB template if provided
        template_doc = None
        if template_id:
            template_doc = templates_col.find_one({"_id": ObjectId(template_id)})

        # Verification check for test email
        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', req_data["email"]):
             return {"status": "error", "detail": "Invalid email syntax"}
        
        domain = req_data["email"].split('@')[1].lower()
        if "mailinator" in domain or "tempmail" in domain:
            return {"status": "error", "detail": "Test emails to disposable domains are blocked"}

        if template_type == "initial":
            email_data = build_email(recruiter, template_doc)
        elif template_type == "followup1":
            email_data = build_followup_email(
                recruiter, stage=1, template_doc=template_doc
            )
        elif template_type == "breakup":
            email_data = build_followup_email(
                recruiter, stage=2, template_doc=template_doc
            )
        else:
            return {"status": "error", "detail": "Invalid template type"}

        success, error_msg = send_email(email_data)

        if success:
            logger.info(
                f"Test email ({template_type}) successfully sent to {recruiter['email']}"
            )
            return {
                "status": "success",
                "message": f"Sent {template_type} email to {recruiter['email']}",
            }
        else:
            return {"status": "error", "detail": error_msg}

    except Exception as e:
        logger.error(f"Test email error: {e}")
        return {"status": "error", "detail": str(e)}


@router.post("/check-replies")
def check_replies_api():
    updated = check_replies()
    return {"ok": True, "count": updated}


@router.post("/send-followup")
def send_followup_api():
    return send_followup_if_due()
