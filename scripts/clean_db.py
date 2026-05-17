import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("MONGO_DB")]
col = db["temp"]

# Delete ALL recruiters
result = col.delete_many({})
print(f"Deleted ALL {result.deleted_count} recruiters from the database.")
