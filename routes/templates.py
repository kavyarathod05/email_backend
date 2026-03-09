"""
Template CRUD routes.
"""
from datetime import datetime
from bson import ObjectId
from fastapi import APIRouter, HTTPException

from config import templates_col, logger
from models import TemplateBase

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("")
def list_templates():
    try:
        results = []
        for t in templates_col.find().sort("createdAt", -1):
            t["_id"] = str(t["_id"])
            results.append(t)
        return results
    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise HTTPException(status_code=500, detail="Error fetching templates")


@router.post("")
def create_template(data: TemplateBase):
    try:
        template = {
            "name": data.name,
            "subject": data.subject,
            "htmlBody": data.htmlBody,
            "type": data.type,
            "createdAt": datetime.utcnow(),
        }
        result = templates_col.insert_one(template)
        return {"message": "Template created", "id": str(result.inserted_id)}
    except Exception as e:
        logger.error(f"Error creating template: {e}")
        raise HTTPException(status_code=500, detail="Error creating template")


@router.put("/{template_id}")
def update_template(template_id: str, data: TemplateBase):
    try:
        update_data = {
            "name": data.name,
            "subject": data.subject,
            "htmlBody": data.htmlBody,
            "type": data.type,
            "updatedAt": datetime.utcnow(),
        }
        result = templates_col.update_one(
            {"_id": ObjectId(template_id)}, {"$set": update_data}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Template not found")
        return {"message": "Template updated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating template: {e}")
        raise HTTPException(status_code=500, detail="Error updating template")


@router.delete("/{template_id}")
def delete_template(template_id: str):
    try:
        result = templates_col.delete_one({"_id": ObjectId(template_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Template not found")
        return {"message": "Template deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting template: {e}")
        raise HTTPException(status_code=500, detail="Error deleting template")
