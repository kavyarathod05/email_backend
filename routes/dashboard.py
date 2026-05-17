"""
Dashboard routes: analytics, stats, recruiter list.
"""
from fastapi import APIRouter, HTTPException

from config import recruiters_col, logger

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/analytics")
def dashboard_analytics():
    try:
        pipeline_sent = [
            {"$match": {"sentAt": {"$ne": None}}},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {"format": "%Y-%m-%d", "date": "$sentAt"}
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id": 1}},
        ]
        sent_per_day = list(recruiters_col.aggregate(pipeline_sent))

        pipeline_templates = [
            {"$match": {"status": {"$in": ["sent", "replied"]}}},
            {
                "$group": {
                    "_id": {"$ifNull": ["$templateName", "Default"]},
                    "sent": {"$sum": 1},
                    "opened": {
                        "$sum": {"$cond": [{"$eq": ["$opened", True]}, 1, 0]}
                    },
                    "clicked": {
                        "$sum": {"$cond": [{"$eq": ["$clicked", True]}, 1, 0]}
                    },
                    "replied": {
                        "$sum": {"$cond": [{"$eq": ["$replied", True]}, 1, 0]}
                    },
                }
            },
        ]
        template_metrics = list(recruiters_col.aggregate(pipeline_templates))

        return {
            "sentPerDay": [
                {"date": x["_id"], "count": x["count"]} for x in sent_per_day
            ],
            "templateMetrics": [
                {
                    "name": x["_id"],
                    "sent": x["sent"],
                    "opened": x["opened"],
                    "clicked": x["clicked"],
                    "replied": x["replied"],
                }
                for x in template_metrics
            ],
        }
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        raise HTTPException(status_code=500, detail="Analytics error")


@router.get("/stats")
def dashboard_stats():
    try:
        return {
            "total": recruiters_col.count_documents({}),
            "new": recruiters_col.count_documents({"status": "new"}),
            "sent": recruiters_col.count_documents({"status": "sent"}),
            "replied": recruiters_col.count_documents({"status": "replied"}),
            "errors": recruiters_col.count_documents({"status": "error"}),
            "followups": recruiters_col.count_documents({"followupSent": True}),
            "opened": recruiters_col.count_documents({"opened": True}),
            "clicked": recruiters_col.count_documents({"clicked": True}),
            "fake": recruiters_col.count_documents({"is_fake": True}),
            "risky": recruiters_col.count_documents({"is_risky": True}),
            "top_tier": recruiters_col.count_documents({"companyType": "top_tier"}),
        }
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail="Database connection error")


@router.get("/daily-report")
def dashboard_daily_report():
    try:
        pipeline = [
            {"$addFields": {
                "reportDate": {"$ifNull": ["$sentAt", {"$ifNull": ["$updatedAt", "$createdAt"]}]}
            }},
            {"$match": {"reportDate": {"$ne": None}}},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {"format": "%Y-%m-%d", "date": "$reportDate"}
                    },
                    "sent": {"$sum": {"$cond": [{"$in": ["$status", ["sent", "replied"]]}, 1, 0]}},
                    "errors": {"$sum": {"$cond": [{"$eq": ["$status", "error"]}, 1, 0]}},
                    "fake": {"$sum": {"$cond": [{"$eq": ["$is_fake", True]}, 1, 0]}},
                    "top_tier": {"$sum": {
                        "$cond": [
                            {"$and": [
                                {"$in": ["$status", ["sent", "replied"]]},
                                {"$in": ["$companyType", ["Top Tier", "top_tier", "topTier"]]}
                            ]}, 1, 0
                        ]
                    }},
                    "startup": {"$sum": {
                        "$cond": [
                            {"$and": [
                                {"$in": ["$status", ["sent", "replied"]]},
                                {"$in": ["$companyType", ["Startup", "startup"]]}
                            ]}, 1, 0
                        ]
                    }},
                }
            },
            {"$sort": {"_id": -1}},
        ]
        
        results = list(recruiters_col.aggregate(pipeline))
        
        formatted = []
        for r in results:
            if not r["_id"]:
                continue
            formatted.append({
                "date": r["_id"],
                "sent": r.get("sent", 0),
                "errors": r.get("errors", 0),
                "fake": r.get("fake", 0),
                "topTier": r.get("top_tier", 0),
                "startup": r.get("startup", 0)
            })
            
        return formatted
    except Exception as e:
        logger.error(f"Daily report error: {e}")
        raise HTTPException(status_code=500, detail="Daily report error")


@router.get("/recruiters")
def dashboard_recruiters(status: str = None):
    try:
        query = {}
        if status:
            query["status"] = status
        data = []
        for r in recruiters_col.find(query).sort("createdAt", -1):
            r["_id"] = str(r["_id"])
            for key, value in r.items():
                if hasattr(value, "isoformat"):
                    r[key] = value.isoformat() + "Z"
            data.append(r)
        return data
    except Exception:
        raise HTTPException(status_code=500, detail="Database connection error")


@router.get("/queue")
def dashboard_queue():
    """
    Returns the queue of upcoming emails.
    Shows the next 20 'new' recruiters, and the next 20 pending follow-ups.
    """
    try:
        # Next initial emails
        initial_queue = list(recruiters_col.find({"status": "new"}).sort("createdAt", 1).limit(20))
        for r in initial_queue:
            r["_id"] = str(r["_id"])
            for key, value in r.items():
                if hasattr(value, "isoformat"):
                    r[key] = value.isoformat() + "Z"
        
        # Next follow-ups
        followup_queue = list(recruiters_col.find({
            "status": "sent",
            "replied": False,
            "followupSent": False,
            "followupStage": {"$in": [0, 1]}
        }).sort("sentAt", 1).limit(20))
        
        for r in followup_queue:
            r["_id"] = str(r["_id"])
            for key, value in r.items():
                if hasattr(value, "isoformat"):
                    r[key] = value.isoformat() + "Z"

        return {
            "initial": initial_queue,
            "followups": followup_queue
        }
    except Exception as e:
        logger.error(f"Queue error: {e}")
        raise HTTPException(status_code=500, detail="Database connection error")
