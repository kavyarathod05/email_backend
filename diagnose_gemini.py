
import os
import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

def test_gemini():
    if not GEMINI_API_KEY:
        print("❌ No GEMINI_API_KEY found in .env")
        return

    print(f"Using API Key: {GEMINI_API_KEY[:5]}...{GEMINI_API_KEY[-5:]}")
    
    payload = {
        "contents": [
            {
                "parts": [{"text": "Hello, world! Respond with 'OK'."}]
            }
        ]
    }
    
    try:
        print("Sending request to Gemini API...")
        resp = requests.post(
            GEMINI_API_URL,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=20,
        )
        print(f"Status Code: {resp.status_code}")
        print("Response Body:")
        print(resp.text)
        
        if resp.status_code == 429:
            print("\n🔍 ANALYSIS: Status 429 means 'Too Many Requests' or 'Quota Exceeded'.")
            if "exhausted" in resp.text.lower():
                print("Your DAILY or MINUTELY quota is exhausted.")
            else:
                print("You might be hitting the Rate Limit (Requests Per Minute).")
        elif resp.status_code == 403:
            print("\n🔍 ANALYSIS: Status 403 usually means the API key is invalid or lacks permissions for this model.")
        elif resp.status_code == 200:
            print("\n✅ SUCCESS: API is working correctly.")
            
    except Exception as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    test_gemini()
