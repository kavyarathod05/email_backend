"""Shared User-Agent and timeouts for scrapers."""

import httpx

USER_AGENT = (
    "InternshipLinkIntel/0.2 "
    "(+https://github.com/kavyarathod05/email_backend; polite career poller)"
)
DEFAULT_TIMEOUT = httpx.Timeout(25.0, connect=10.0)
