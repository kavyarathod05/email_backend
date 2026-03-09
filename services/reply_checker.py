"""
IMAP-based reply detection.
"""
import os
import email
import imaplib
from datetime import datetime

from config import recruiters_col, logger


def check_replies() -> int:
    """
    Scan the inbox for UNSEEN messages and mark matching recruiters as replied.
    Returns the number of recruiters updated.
    """
    try:
        mail = imaplib.IMAP4_SSL(
            os.getenv("IMAP_SERVER"), int(os.getenv("IMAP_PORT"))
        )
        mail.login(os.getenv("GMAIL_ID"), os.getenv("GMAIL_APP_PASSWORD"))
        mail.select("inbox")

        status, messages = mail.search(None, "UNSEEN")
        if status != "OK":
            mail.logout()
            return 0

        updated = 0
        for e_id in messages[0].split():
            _, msg_data = mail.fetch(e_id, "(RFC822)")
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            sender = email.utils.parseaddr(msg.get("From"))[1].lower()
            subject = msg.get("Subject", "")

            body_snippet = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body_snippet = (
                            part.get_payload(decode=True).decode(errors="ignore")[:200]
                        )
                        break
            else:
                body_snippet = (
                    msg.get_payload(decode=True).decode(errors="ignore")[:200]
                )

            result = recruiters_col.update_one(
                {"email": sender, "replied": False},
                {
                    "$set": {
                        "replied": True,
                        "status": "replied",
                        "replyAt": datetime.utcnow(),
                        "replySubject": subject,
                        "replySnippet": body_snippet,
                    }
                },
            )
            if result.modified_count:
                updated += 1

        mail.logout()
        return updated
    except Exception as e:
        logger.error(f"IMAP Error: {e}")
        return 0
