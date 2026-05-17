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

def scheduled_batch_harvest():
    logger.info(f"[{datetime.now()}] Internal Scheduler: Triggering automated Batch Lead Harvest (5 companies, 4 leads)")
    try:
        from scripts.harvest_scheduler import run_batch_harvest
        run_batch_harvest(batch_size=5, leads_per_company=4)
    except Exception as e:
        logger.error(f"Internal Scheduler Error (batch_harvest): {e}")

def start_scheduler():
    """
    Start the background scheduler.
    Currently configured to run:
    - Initial emails: Every 5 minutes during business hours
    - Automated Batch Harvester: Every hour, 24/7 (runs all the time)
    """
    # 1. Email Sending Job
    scheduler.add_job(
        scheduled_send_one,
        trigger=CronTrigger(minute="*/5", hour="9-17", day_of_week="mon-fri"),
        id="send_initial_email_job",
        replace_existing=True,
    )
    
    # 2. Automated Batch Lead Harvester (Runs every single hour, 24/7/365)
    scheduler.add_job(
        scheduled_batch_harvest,
        trigger=CronTrigger(minute="0"),
        id="automated_batch_harvest_job",
        replace_existing=True,
    )
    
    # Temporarily disabled per user request
    # scheduler.add_job(
    #     scheduled_followup,
    #     trigger=CronTrigger(minute="15", hour="9-17", day_of_week="mon-fri"),
    #     id="send_followup_email_job",
    #     replace_existing=True,
    # )
    
    scheduler.start()
    logger.info("Internal APScheduler started. Emails and Automated Harvester will run automatically.")

def stop_scheduler():
    scheduler.shutdown()
    logger.info("Internal APScheduler stopped.")
