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

        # 1. Handle regular 'error' status
        error_query = {
            "status": "error",
            "$or": [
                {"errorAt": {"$lte": retry_threshold}},
                {
                    "errorAt": {"$exists": False},
                    "createdAt": {"$lte": retry_threshold}
                }
            ]
        }
        error_update = {
            "$set": {
                "status": "new",
                "errorDetail": None,
                "errorAt": None
            }
        }
        error_result = recruiters_col.update_many(error_query, error_update)

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
        
        total_modified = error_result.modified_count + fake_result.modified_count
        if total_modified > 0:
            logger.info(f"Retried {total_modified} records ({error_result.modified_count} errors, {fake_result.modified_count} fakes) moved to 'new'")
        
        return total_modified

    except Exception as e:
        logger.error(f"Error in retry_failed_emails: {e}")
        return 0
