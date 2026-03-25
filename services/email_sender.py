"""
Email delivery via Google Apps Script Bridge.
"""
import os
import requests

from config import logger



def is_blacklisted(email: str) -> bool:
    """
    Check if the email is in the Google Sheet blacklist via the GAS bridge.
    """
    script_url = os.getenv("GOOGLE_SCRIPT_URL")
    if not script_url:
        logger.error("GOOGLE_SCRIPT_URL not found in environment")
        return False

    payload = {
        "action": "check_blacklist",
        "email": email
    }

    try:
        response = requests.post(script_url, json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                return result.get("blacklisted", False)
        logger.error(f"Blacklist check failed: {response.status_code} - {response.text}")
        return False
    except Exception as e:
        logger.error(f"Error checking blacklist: {e}")
        return False


def send_email(email_data: dict) -> tuple[bool, str | None, str | None]:
    """
    POST the email payload to the Google Apps Script bridge.
    Returns (success: bool, error_message: str | None, message_id: str | None).
    """
    script_url = os.getenv("GOOGLE_SCRIPT_URL")

    payload = {
        "to": email_data["To"],
        "subject": email_data["Subject"],
        "htmlBody": email_data["HTMLPart"],
    }
    if email_data.get("inReplyTo"):
        payload["inReplyTo"] = email_data["inReplyTo"]

    try:
        response = requests.post(script_url, json=payload, timeout=10)

        if response.status_code == 200:
            try:
                resp_json = response.json()
            except Exception:
                error_msg = f"Google Bridge returned 200 but invalid JSON: {response.text}"
                logger.error(error_msg)
                return False, error_msg, None

            if resp_json.get("Success") is True:
                message_id = resp_json.get("messageId")
                logger.info(
                    f"Email SENT to {email_data['To']} | Subject: '{email_data['Subject']}' | Bridge Response: {resp_json}"
                )
                return True, None, message_id
            else:
                error_msg = f"Google Bridge returned 200 but reported failure: {resp_json}"
                logger.error(error_msg)
                return False, error_msg, None
        else:
            error_msg = f"Google Bridge Error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            return False, error_msg, None
    except Exception as e:
        error_msg = f"Failed to connect to Google Bridge: {e}"
        logger.error(error_msg)
        return False, error_msg, None
