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
        }
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail="Database connection error")


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
