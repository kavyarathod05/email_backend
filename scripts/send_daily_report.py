import os
import sys
import argparse
from datetime import datetime, time, timezone

# Add the parent directory to sys.path so we can import from config and services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import recruiters_col, logger
from services.email_sender import send_email

def generate_daily_report():
    """
    Query MongoDB for today's email statistics.
    """
    # Get the start of today in UTC
    now = datetime.now(timezone.utc)
    start_of_today = datetime.combine(now.date(), time.min).replace(tzinfo=timezone.utc)
    
    # 1. Total sent today (check sentAt or updated timestamp if status is sent)
    # Since sentAt is properly set when an email is sent:
    sent_today = recruiters_col.count_documents({
        "status": {"$in": ["sent", "replied"]},
        "sentAt": {"$gte": start_of_today}
    })
    
    # 2. Errors today (check updatedAt if status is error)
    errors_today = recruiters_col.count_documents({
        "status": "error",
        "updatedAt": {"$gte": start_of_today}
    })
    
    # 3. Fake emails detected today
    fake_today = recruiters_col.count_documents({
        "is_fake": True,
        "updatedAt": {"$gte": start_of_today}
    })
    
    # 4. Sent to Top Tier today
    top_tier_sent_today = recruiters_col.count_documents({
        "status": {"$in": ["sent", "replied"]},
        "sentAt": {"$gte": start_of_today},
        "companyType": {"$in": ["Top Tier", "top_tier"]}
    })
    
    # 5. Sent to Startup today
    startup_sent_today = recruiters_col.count_documents({
        "status": {"$in": ["sent", "replied"]},
        "sentAt": {"$gte": start_of_today},
        "companyType": {"$in": ["Startup", "startup"]}
    })
    
    return {
        "date": now.strftime("%Y-%m-%d"),
        "sent_today": sent_today,
        "errors_today": errors_today,
        "fake_today": fake_today,
        "top_tier_sent_today": top_tier_sent_today,
        "startup_sent_today": startup_sent_today
    }

def format_html_report(stats):
    return f"""
    <h2>Daily Email Automation Report for {stats['date']}</h2>
    <ul>
        <li><b>Total Emails Sent:</b> {stats['sent_today']}</li>
        <li><b>Errors Encountered:</b> {stats['errors_today']}</li>
        <li><b>Fake Emails Detected:</b> {stats['fake_today']}</li>
    </ul>
    <h3>Breakdown by Company Type (Sent):</h3>
    <ul>
        <li><b>Top Tier:</b> {stats['top_tier_sent_today']}</li>
        <li><b>Startup:</b> {stats['startup_sent_today']}</li>
    </ul>
    <p><small>This is an automated daily report from your email outreach system.</small></p>
    """

def main():
    parser = argparse.ArgumentParser(description="Generate and send daily email statistics report.")
    parser.add_argument("--email", type=str, help="Email address to send the report to.", default=os.getenv("ADMIN_EMAIL"))
    parser.add_argument("--dry-run", action="store_true", help="Print report to console without sending.")
    args = parser.parse_args()
    
    logger.info("Generating daily statistics report...")
    stats = generate_daily_report()
    html_report = format_html_report(stats)
    
    if args.dry_run:
        print("--- DRY RUN: Daily Report ---")
        print(f"Date: {stats['date']}")
        print(f"Sent: {stats['sent_today']}")
        print(f"Errors: {stats['errors_today']}")
        print(f"Fake: {stats['fake_today']}")
        print(f"Top Tier Sent: {stats['top_tier_sent_today']}")
        print(f"Startup Sent: {stats['startup_sent_today']}")
        sys.exit(0)
        
    if not args.email:
        logger.error("No email provided. Use --email or set ADMIN_EMAIL environment variable.")
        sys.exit(1)
        
    email_data = {
        "To": args.email,
        "Subject": f"Daily Email Outreach Report - {stats['date']}",
        "HTMLPart": html_report
    }
    
    logger.info(f"Sending daily report to {args.email}...")
    success, error_msg, message_id = send_email(email_data)
    
    if success:
        logger.info(f"Report successfully sent (Message ID: {message_id}).")
    else:
        logger.error(f"Failed to send report: {error_msg}")

if __name__ == "__main__":
    main()
