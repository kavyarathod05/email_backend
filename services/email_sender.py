"""
Email delivery using scalable SMTP and fallback to API.
"""

import os
import smtplib
import email.utils
from email.message import EmailMessage
from config import logger

def _send_via_smtp(email_data: dict) -> tuple[bool, str | None, str | None]:
    """
    Scalable SMTP implementation. Works with:
    - Gmail App Passwords (500/day limit)
    - Google Workspace (2000/day limit)
    - Amazon SES, SendGrid, Mailgun, etc. (Unlimited/Scalable)
    """
    # Use standard Gmail SMTP by default, but allow overriding for scalable providers
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")

    if not smtp_user or not smtp_pass:
        return False, "SMTP credentials missing in environment (.env). Please add SMTP_USER and SMTP_PASSWORD.", None

    msg = EmailMessage()
    msg['Subject'] = email_data["Subject"]
    
    # We allow FROM_NAME overriding, e.g., "Kavya <kavya@example.com>"
    from_name = os.getenv("SMTP_FROM_NAME", "")
    if from_name:
        msg['From'] = f"{from_name} <{smtp_user}>"
    else:
        msg['From'] = smtp_user
        
    msg['To'] = email_data["To"]
    
    # Generate our own Message-ID for tracking replies in threads
    domain = smtp_user.split('@')[-1] if '@' in smtp_user else 'local'
    message_id = email.utils.make_msgid(domain=domain)
    msg['Message-ID'] = message_id

    # Handle threading / follow-ups
    if email_data.get("inReplyTo"):
        msg['In-Reply-To'] = email_data["inReplyTo"]
        msg['References'] = email_data["inReplyTo"]

    # Set the content directly to HTML to prevent clients from showing it as empty
    msg.set_content(email_data["HTMLPart"], subtype='html')

    try:
        # SMTP_SSL is generally port 465, but we use starttls on 587
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            
        logger.info(f"SMTP: Email SENT to {email_data['To']} | Subject: '{email_data['Subject']}'")
        # Return cleanly extracted ID without surrounding brackets
        return True, None, message_id.strip('<>')
    except Exception as e:
        error_msg = f"SMTP Delivery Error: {e}"
        logger.error(error_msg)
        return False, error_msg, None

def send_email(email_data: dict) -> tuple[bool, str | None, str | None]:
    """
    Sends email using the configured scalable provider.
    Returns (success: bool, error_message: str | None, message_id: str | None).
    """
    return _send_via_smtp(email_data)
