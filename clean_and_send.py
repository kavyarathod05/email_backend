import requests
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("MONGO_DB")]
col = db["temp"]

BASE_URL = "http://localhost:10000"
TEST_EMAIL = "rathodkavya2005@gmail.com"

def run_test():
    print("--- Cleaning Database ---")
    deleted = col.delete_many({})
    print(f"Deleted {deleted.deleted_count} records.")

    print(f"--- Adding {TEST_EMAIL} ---")
    res = requests.post(f"{BASE_URL}/recruiters", json={
        "email": TEST_EMAIL,
        "name": "Kavya",
        "company": "Kavya Inc"
    })
    print("Added:", res.json())

    print("--- Sending Email ---")
    res = requests.post(f"{BASE_URL}/send-one")
    print("Sent:", res.json())
    
    doc = col.find_one({"email": TEST_EMAIL})
    print("\n✅ Current Document State:")
    print(f"Email: {doc.get('email')}")
    print(f"Status: {doc.get('status')}")
    print(f"Opened: {doc.get('opened')}")
    print("\nNow, go check your email, open it, and then check the Dashboard in your browser (http://localhost:5173/) to see if 'Opened' updates!")

if __name__ == "__main__":
    run_test()
