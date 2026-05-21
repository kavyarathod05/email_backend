"""
Centralized configuration: environment variables, MongoDB, logging, and CORS.
"""
import os
import logging
from dotenv import load_dotenv
from pymongo import MongoClient
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# --------------- Logging ---------------
import collections
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("email_automation")

LOG_BUFFER = collections.deque(maxlen=300)

class InMemoryLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            LOG_BUFFER.append(msg)
        except Exception:
            self.handleError(record)

in_memory_handler = InMemoryLogHandler()
in_memory_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(in_memory_handler)
logging.getLogger("apscheduler").addHandler(in_memory_handler)

# --------------- Environment ---------------
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB")

if not MONGO_URI or not MONGO_DB:
    raise Exception("Missing MongoDB environment variables")

# --------------- MongoDB ---------------
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client[MONGO_DB]
    client.server_info()
    recruiters_col = db["temp"]
    templates_col = db["templates"]
    emails_col = db["generated_emails"]
    logger.info("Connected to MongoDB successfully")
except Exception as e:
    logger.error(f"MongoDB Connection Error: {e}")
    raise Exception(f"Could not connect to MongoDB: {e}")


# --------------- App Factory ---------------
def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(title="Email Outreach Automation")

    frontend_origin = os.getenv("FRONTEND_ORIGIN", "").rstrip("/")
    origins = [
        frontend_origin,
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    application.add_middleware(
        CORSMiddleware,
        allow_origins=[o for o in origins if o],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return application
