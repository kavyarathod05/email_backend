"""
Open/click tracking and test webhook routes.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Response, status
from fastapi.responses import RedirectResponse

from config import recruiters_col, logger

router = APIRouter(tags=["tracking"])


# --------------- Live Tracking ---------------

@router.get("/track/open/{email}")
def track_open(email: str):
    try:
        recruiters_col.update_one(
            {"email": email},
            {"$set": {"opened": True, "openedAt": datetime.now(timezone.utc)}},
        )
    except Exception as e:
        logger.error(f"Error tracking open for {email}: {e}")

    # 1x1 transparent GIF
    pixel = (
        b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00"
        b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01"
        b"\x00\x00\x02\x02D\x01\x00;"
    )
    return Response(content=pixel, media_type="image/gif")


@router.get("/track/click/{email}")
def track_click(email: str, url: str):
    try:
        recruiters_col.update_one(
            {"email": email},
            {"$set": {"clicked": True, "clickedAt": datetime.now(timezone.utc)}},
        )
    except Exception as e:
        logger.error(f"Error tracking click for {email}: {e}")
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


# --------------- Test Webhooks ---------------

@router.post("/test/open/{email}")
def test_open_event(email: str):
    recruiters_col.update_one(
        {"email": email},
        {"$set": {"opened": True, "openedAt": datetime.now(timezone.utc)}},
    )
    return {"message": "Simulated open"}


@router.post("/test/click/{email}")
def test_click_event(email: str):
    recruiters_col.update_one(
        {"email": email},
        {"$set": {"clicked": True, "clickedAt": datetime.now(timezone.utc)}},
    )
    return {"message": "Simulated click"}
