"""Mongo for internship intel — same MongoDB client/DB as outreach."""

from __future__ import annotations

import logging

from pymongo import ASCENDING
from pymongo.collection import Collection
from pymongo.database import Database

from config import client, db

logger = logging.getLogger("email_automation.intel.mongo")


def get_client():
    return client


def get_db(settings=None) -> Database:
    return db


def companies_col(database: Database | None = None) -> Collection:
    return (database or get_db())["companies"]


def ping_mongo(settings=None) -> bool:
    try:
        client.admin.command("ping")
        return True
    except Exception as e:
        logger.warning("Mongo ping failed: %s", e)
        return False


def ensure_indexes(database: Database | None = None) -> None:
    col = companies_col(database)
    col.create_index([("slug", ASCENDING)], unique=True, name="uniq_slug")
    col.create_index([("name_key", ASCENDING)], unique=True, name="uniq_name_key")
    col.create_index([("ats_provider", ASCENDING)], name="idx_ats_provider")
    col.create_index(
        [("priority", ASCENDING), ("active", ASCENDING)], name="idx_priority_active"
    )
    col.create_index([("active", ASCENDING)], name="idx_active")
    from intel.modules.jobs.repository import ensure_job_indexes

    ensure_job_indexes(database)
    logger.info("Intel Mongo indexes ensured")


def close_client() -> None:
    # Shared with outreach — do not close here
    pass
