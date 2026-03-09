"""
Pydantic request models used across routes.
"""
from pydantic import BaseModel
from typing import Optional


class CSVImportRequest(BaseModel):
    csvText: str


class TestEmailRequest(BaseModel):
    email: str
    name: str = "Test Name"
    company: str = "Test Company"
    templateType: str = "initial"
    templateId: Optional[str] = None


class TemplateBase(BaseModel):
    name: str
    subject: str
    htmlBody: str
    type: str = "initial"


class SendOneRequest(BaseModel):
    templateId: Optional[str] = None
