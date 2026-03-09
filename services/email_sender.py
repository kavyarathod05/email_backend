"""
Email delivery via Google Apps Script Bridge.
"""
import os
import requests

from config import logger


def send_email(email_data: dict) -> tuple[bool, str | None]:
    """
    POST the email payload to the Google Apps Script bridge.
    Returns (success: bool, error_message: str | None).
    """
    script_url = os.getenv("GOOGLE_SCRIPT_URL")

    payload = {
        "to": email_data["To"],
        "subject": email_data["Subject"],
        "htmlBody": email_data["HTMLPart"],
    }

    try:
        response = requests.post(script_url, json=payload, timeout=10)

        if response.status_code == 200:
            if "Success" in response.text:
                logger.info(
                    f"Email SENT to {email_data['To']} | Subject: '{email_data['Subject']}'"
                )
                return True, None
            else:
                error_msg = f"Google Bridge returned 200 but failed: {response.text}"
                logger.error(error_msg)
                return False, error_msg
        else:
            error_msg = f"Google Bridge Error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            return False, error_msg
    except Exception as e:
        error_msg = f"Failed to connect to Google Bridge: {e}"
        logger.error(error_msg)
        return False, error_msg
