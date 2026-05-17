"""
Internal job scheduler. Replaces external cron jobs.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from routes.email import send_one_email, send_followup_api
from config import logger
from datetime import datetime

scheduler = BackgroundScheduler()

def scheduled_send_one():
    logger.info(f"[{datetime.now()}] Internal Scheduler: Triggering send_one_email")
    try:
        send_one_email()
    except Exception as e:
        logger.error(f"Internal Scheduler Error (send_one): {e}")

def scheduled_followup():
    logger.info(f"[{datetime.now()}] Internal Scheduler: Triggering send_followup_api")
    try:
        send_followup_api()
    except Exception as e:
        logger.error(f"Internal Scheduler Error (followup): {e}")

def start_scheduler():
    """
    Start the background scheduler.
    Currently configured to run:
    - Initial emails: Every 5 minutes
    - Followups: Every hour at the 15th minute
    ONLY during Mon-Fri, 9 AM to 5 PM.
    """
    scheduler.add_job(
        scheduled_send_one,
        trigger=CronTrigger(minute="*/5", hour="9-17", day_of_week="mon-fri"),
        id="send_initial_email_job",
        replace_existing=True,
    )
    
    scheduler.add_job(
        scheduled_followup,
        trigger=CronTrigger(minute="15", hour="9-17", day_of_week="mon-fri"),
        id="send_followup_email_job",
        replace_existing=True,
    )
    
    scheduler.start()
    logger.info("Internal APScheduler started. Emails will be sent automatically at scheduled times.")

def stop_scheduler():
    scheduler.shutdown()
    logger.info("Internal APScheduler stopped.")
