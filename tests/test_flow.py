import requests
import time
from pymongo import MongoClient
import os
from dotenv import load_dotenv

# Load ENV for DB access to manipulate timestamps for testing
load_dotenv()
client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("MONGO_DB")]
col = db["temp"]

BASE_URL = "http://localhost:10000"
TEST_EMAIL = "rathodkavya2005@gmail.com"

def run_test():
    print(f"--- Starting test for {TEST_EMAIL} ---")

    # 1. Clean up any existing test recruiter
    col.delete_many({"email": TEST_EMAIL})
    print("🧹 Cleaned up existing test data")

    # 2. Add the recruiter
    res = requests.post(f"{BASE_URL}/recruiters", json={
        "email": TEST_EMAIL,
        "name": "kavya",
        "company": "kavya"
    })
    print("➕ Added recruiter:", res.json())

    # Ensure this is the ONLY 'new' recruiter for the test or manually change state
    col.update_many({"email": {"$ne": TEST_EMAIL}, "status": "new"}, {"$set": {"status": "paused_for_test"}})

    # 3. Send initial email
    res = requests.post(f"{BASE_URL}/send-one")
    print("📤 Sent initial email:", res.json())
    
    # Check if sent
    doc = col.find_one({"email": TEST_EMAIL})
    if doc.get("status") != "sent":
        print("❌ Initial email failed to send or target correct recruiter.")
        return

    # 4. Simulate time passing for Stage 1 Followup (Set sentAt to 5 days ago)
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    col.update_one(
        {"email": TEST_EMAIL},
        {"$set": {"sentAt": now - timedelta(days=5)}}
    )
    print("⏳ Simulated 5 days passing...")

    # 5. Send Stage 1 Followup
    res = requests.post(f"{BASE_URL}/send-followup")
    print("📤 Sent Stage 1 Followup:", res.json())

    # 6. Simulate time passing for Stage 2 Followup (Set followupAt to 7 days ago)
    # We must reset current time since logic checks against db date
    now = datetime.now(timezone.utc)
    col.update_one(
        {"email": TEST_EMAIL},
        {"$set": {"followupAt": now - timedelta(days=7)}}
    )
    print("⏳ Simulated 7 more days passing...")

    # 7. Send Stage 2 Breakup Email
    res = requests.post(f"{BASE_URL}/send-followup")
    print("📤 Sent Stage 2 Breakup:", res.json())

    # 8. Test Open Tracking
    print("👁️ Simulating email open...")
    res = requests.get(f"{BASE_URL}/track/open/{TEST_EMAIL}")
    print("   Open tracking status:", res.status_code)

    # 9. Test Click Tracking
    print("🖱️ Simulating link click...")
    res = requests.get(f"{BASE_URL}/track/click/{TEST_EMAIL}?url=https://google.com")
    print("   Click tracking status:", res.status_code)

    # Restore paused recruiters
    col.update_many({"status": "paused_for_test"}, {"$set": {"status": "new"}})

    # 10. Verify final state in DB
    final_doc = col.find_one({"email": TEST_EMAIL})
    print("\n✅ Final Database State:")
    print(f"Status: {final_doc.get('status')}")
    print(f"Followup Stage: {final_doc.get('followupStage')}")
    print(f"Opened: {final_doc.get('opened')}")
    print(f"Clicked: {final_doc.get('clicked')}")

if __name__ == "__main__":
    run_test()
