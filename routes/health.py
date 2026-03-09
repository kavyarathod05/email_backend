"""
Health check route.
"""
from datetime import datetime
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow()}
