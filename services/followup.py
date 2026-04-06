"""
Follow-up engine: checks for due follow-ups and sends them.
"""
from datetime import datetime, timedelta, timezone

from config import recruiters_col, logger
from services.email_builder import build_followup_email
from services.email_sender import send_email


def send_followup_if_due() -> dict:
    """
    Find exactly ONE recruiter due for a follow-up and send the email.

    Timing rules:
      - Stage 0 → 1: 4 days after initial sentAt
      - Stage 1 → 2: 6 days after followupAt
    """
    try:
        now = datetime.now(timezone.utc)

        query = {
            "status": "sent",
            "replied": False,
            "$or": [
                {
                    # Scenario 2: Resume clicked but no reply (36 hours)
                    "clicked": True,
                    "followupStage": {"$in": [0, None]},
                    "sentAt": {"$lte": now - timedelta(hours=36)},
                },
                {
                    # Scenario 1: Opened but no reply (3 days)
                    "opened": True,
                    "clicked": False,
                    "followupStage": {"$in": [0, None]},
                    "sentAt": {"$lte": now - timedelta(days=3)},
                },
                {
                    # Scenario 3: Not opened (Resend after 4 days)
                    "opened": False,
                    "followupStage": {"$in": [0, None]},
                    "sentAt": {"$lte": now - timedelta(days=4)},
                },
                {
                    # Stage 2 breakup (6 days after last followup)
                    "followupStage": 1,
                    "followupAt": {"$lte": now - timedelta(days=6)},
                },
            ],
        }

        recruiter = recruiters_col.find_one(query)

        if not recruiter:
            logger.info("No follow-ups due at this time.")
            return {"status": "no followups due"}


        logger.info(f"Found due follow-up for: {recruiter['email']}")

        current_stage = recruiter.get("followupStage", 0)
        next_stage = current_stage + 1

        # Build the email (DB round-robin handled inside builder)
        email_data = build_followup_email(recruiter, next_stage)

        if not email_data["HTMLPart"]:
            error_msg = "Empty body generated"
            logger.error(f"ABORTING: {error_msg} for {recruiter['email']}")
            recruiters_col.update_one(
                {"_id": recruiter["_id"]},
                {"$set": {"status": "error", "errorDetail": error_msg, "errorAt": datetime.now(timezone.utc)}},
            )
            return {"status": "error", "detail": error_msg}

        success, error_msg, message_id = send_email(email_data)

        if success:
            update_fields = {
                "followupSent": True,
                "followupAt": now,
                "followupStage": next_stage,
            }
            if message_id:
                update_fields["messageId"] = message_id
            if email_data.get("templateUsed"):
                update_fields["templateUsed"] = email_data["templateUsed"]
                update_fields["templateName"] = email_data["templateName"]

            update_op = {"$set": update_fields}
            if email_data.get("inReplyTo"):
                update_op["$addToSet"] = {"tags": "same thread"}

            recruiters_col.update_one(
                {"_id": recruiter["_id"]}, update_op
            )

            logger.info(
                f"Follow-up Stage {next_stage} marked as sent for {recruiter['email']}"
            )
            return {
                "status": "followup sent",
                "email": recruiter["email"],
                "company": recruiter.get("company"),
            }
        else:
            recruiters_col.update_one(
                {"_id": recruiter["_id"]},
                {"$set": {"status": "error", "errorDetail": error_msg, "errorAt": datetime.now(timezone.utc)}},
            )
            return {"status": "error", "detail": error_msg}

    except Exception as e:
        logger.error(f"Follow-up Process Error: {e}")
        if 'recruiter' in locals() and recruiter and "_id" in recruiter:
            recruiters_col.update_one(
                {"_id": recruiter["_id"]},
                {"$set": {"status": "error", "errorDetail": str(e), "errorAt": datetime.now(timezone.utc)}},
            )
        return {"status": "error", "detail": str(e)}
