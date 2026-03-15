import requests
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://localhost:10000/api/webhooks"
SECRET = os.getenv("BOUNCE_WEBHOOK_SECRET", "super_secret_key_123")

def test_webhook():
    print("Starting Webhook Verification...")

    payload = {
        "email": "test@example.com",
        "is_fake": True,
        "bounce_reason": "Hard bounce: User does not exist"
    }

    # 1. Test No Auth
    print("\n1. Testing No Authorization Header...")
    resp = requests.post(f"{BASE_URL}/bounce", json=payload)
    print(f"Status: {resp.status_code}")
    assert resp.status_code == 401

    # 2. Test Invalid Token
    print("\n2. Testing Invalid Token...")
    resp = requests.post(
        f"{BASE_URL}/bounce", 
        json=payload,
        headers={"Authorization": "Bearer wrong_token"}
    )
    print(f"Status: {resp.status_code}")
    assert resp.status_code == 401

    # 3. Test Valid Token (but missing record)
    print("\n3. Testing Valid Token (Expecting 404 for missing email)...")
    resp = requests.post(
        f"{BASE_URL}/bounce", 
        json=payload,
        headers={"Authorization": f"Bearer {SECRET}"}
    )
    print(f"Status: {resp.status_code}")
    # Note: This might return 404 if "test@example.com" isn't in DB
    if resp.status_code == 404:
        print("Success: Received 404 for non-existent email as expected.")
    elif resp.status_code == 200:
        print("Success: Received 200 (Email existed in DB).")
    else:
        print(f"Unexpected status: {resp.status_code}")

    print("\nVerification Script Completed.")

if __name__ == "__main__":
    test_webhook()
