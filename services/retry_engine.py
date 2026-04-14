"""
Retry engine for failed emails.
"""
from datetime import datetime, timedelta, timezone
from config import recruiters_col, logger

def retry_failed_emails() -> int:
    """
    Find recruiters with status 'error' or 'skipped_fake' that are older than 24 hours
    and move them back to 'new' status.
    """
    try:
        now = datetime.now(timezone.utc)
        retry_threshold = now - timedelta(hours=24)

        # 1a. Handle 'error' status for records that WERE already sent (Restore to 'sent' for follow-up engine)
        followup_error_query = {
            "status": "error",
            "sentAt": {"$exists": True},
            "$or": [
                {"errorAt": {"$lte": retry_threshold}},
                {"errorAt": {"$exists": False}, "createdAt": {"$lte": retry_threshold}}
            ]
        }
        followup_error_update = {
            "$set": {"status": "sent", "errorDetail": None, "errorAt": None}
        }
        followup_result = recruiters_col.update_many(followup_error_query, followup_error_update)

        # 1b. Handle 'error' status for records NEVER sent (Restore to 'new')
        new_error_query = {
            "status": "error",
            "sentAt": {"$exists": False},
            "$or": [
                {"errorAt": {"$lte": retry_threshold}},
                {"errorAt": {"$exists": False}, "createdAt": {"$lte": retry_threshold}}
            ]
        }
        new_error_update = {
            "$set": {"status": "new", "errorDetail": None, "errorAt": None}
        }
        new_result = recruiters_col.update_many(new_error_query, new_error_update)

        # 2. Handle 'skipped_fake' status
        fake_query = {
            "status": "skipped_fake",
            "$or": [
                {"fakeAt": {"$lte": retry_threshold}},
                {
                    "fakeAt": {"$exists": False},
                    "createdAt": {"$lte": retry_threshold}
                }
            ]
        }
        fake_update = {
            "$set": {
                "status": "new",
                "is_fake": False,
                "fakeAt": None
            }
        }
        fake_result = recruiters_col.update_many(fake_query, fake_update)
        
        total_modified = followup_result.modified_count + new_result.modified_count + fake_result.modified_count
        if total_modified > 0:
            logger.info(
                f"Retried {total_modified} records ({followup_result.modified_count} follow-ups restored, "
                f"{new_result.modified_count} new restored, {fake_result.modified_count} fakes) moved to correct status"
            )
        
        return total_modified

    except Exception as e:
        logger.error(f"Error in retry_failed_emails: {e}")
        return 0
