from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel
import os
from config import recruiters_col, logger

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

class BounceReport(BaseModel):
    email: str
    is_fake: bool
    bounce_reason: str

def verify_token(authorization: str = Header(None)):
    secret = os.getenv("BOUNCE_WEBHOOK_SECRET")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized: Missing or invalid token format")
    
    token = authorization.split(" ")[1]
    if token != secret:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid token")
    return token

@router.post("/bounce")
def handle_bounce(report: BounceReport, token: str = Depends(verify_token)):
    try:
        logger.info(f"Received bounce report for {report.email}: {report.bounce_reason}")
        
        # Find and update the recruiter/lead record
        result = recruiters_col.update_one(
            {"email": report.email},
            {
                "$set": {
                    "is_fake": report.is_fake,
                    "bounce_reason": report.bounce_reason,
                    "status": "bounced"
                }
            }
        )
        
        if result.matched_count == 0:
            logger.warning(f"No record found for emailed: {report.email}")
            raise HTTPException(status_code=404, detail="Email not found in database")
            
        logger.info(f"Successfully updated record for {report.email}")
        return {"ok": True, "message": "Bounce report processed"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing bounce webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
