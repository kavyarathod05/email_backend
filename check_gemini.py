import os
import requests
from dotenv import load_dotenv

# Load API key from .env
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Error: GEMINI_API_KEY not found in .env file.")
    exit(1)

# The standard REST endpoint for Gemini
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={api_key}"

payload = {
    "contents": [{
        "parts": [{"text": "Say 'Hello World, your API key is active!' if you can read this."}]
    }]
}
headers = {"Content-Type": "application/json"}

print("Pinging Gemini API endpoint...")
try:
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    
    if response.status_code == 200:
        data = response.json()
        result = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        print("\n✅ Success! Gemini says:")
        print(result)
    elif response.status_code == 429:
        print("\n❌ Error 429: Quota Exceeded. Check your billing or free tier limits in Google AI Studio.")
    elif response.status_code == 400:
        print("\n❌ Error 400: API Key not valid. Double check your .env file.")
    else:
        print(f"\n❌ API Error {response.status_code}: {response.text}")
        
except Exception as e:
    print(f"\n❌ A network or system error occurred: {e}")