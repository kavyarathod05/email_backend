import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("MONGO_DB")]
col = db["recruiters"]
fake_count = col.count_documents({"is_fake": True})
print(f"Fake counts: {fake_count}")
client.close()
