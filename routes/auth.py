"""
Authentication routes: login and session check.
"""
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from config import logger

router = APIRouter(prefix="/auth", tags=["auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(request: LoginRequest):
    dashboard_id = os.getenv("DASHBOARD_ID")
    dashboard_password = os.getenv("DASHBOARD_PASSWORD")
    
    if not dashboard_id or not dashboard_password:
        logger.error("DASHBOARD_ID or DASHBOARD_PASSWORD not set in environment")
        raise HTTPException(status_code=500, detail="Authentication configuration error")
        
    if request.username == dashboard_id and request.password == dashboard_password:
        return {"success": True, "user": dashboard_id}
    
    raise HTTPException(status_code=401, detail="Invalid credentials")
