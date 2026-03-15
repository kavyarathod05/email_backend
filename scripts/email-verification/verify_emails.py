import os
import re
import time
import argparse
import requests
from pymongo import MongoClient
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load environment variables
load_dotenv()

# Configuration
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB") # Or hardcode if preferred
DISPOSABLE_LIST_URL = "https://raw.githubusercontent.com/disposable-email-domains/disposable-email-domains/master/disposable_email_blocklist.conf"
DOH_API_URL = "https://dns.google/resolve"

# Dummy emails for testing
DUMMY_EMAILS = [
    {"email": "rathodkavya2005@gmail.com"},  # Good
    {"email": "shivam.singhal@amantyatech.com"},  # Good

    
]

DISPOSABLE_DOMAINS = set()

def fetch_disposable_blocklist():
    """Fetches the live disposable domain blocklist from GitHub."""
    global DISPOSABLE_DOMAINS
    print("Fetching disposable domain blocklist...")
    try:
        response = requests.get(DISPOSABLE_LIST_URL, timeout=10)
        response.raise_for_status()
        domains = {line.strip() for line in response.text.splitlines() if line.strip()}
        DISPOSABLE_DOMAINS = domains
        print(f"Loaded {len(DISPOSABLE_DOMAINS)} disposable domains.")
    except Exception as e:
        print(f"Error fetching disposable blocklist: {e}")

def is_valid_syntax(email):
    """Checks email syntax using regex."""
    pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    return bool(re.match(pattern, email))

def is_role_based(email):
    """Checks if the email prefix is a generic role."""
    prefix = email.split('@')[0].lower()
    roles = {'hr', 'info', 'admin', 'support', 'sales', 'contact', 'webmaster', 'jobs', 'marketing', 'no-reply'}
    return prefix in roles

def has_mx_records(domain):
    """Checks for MX records using Google DoH API."""
    try:
        # 50-100ms delay to avoid rate limiting
        time.sleep(0.05 + (0.05 * (time.time() % 1)))
        
        params = {"name": domain, "type": "MX"}
        response = requests.get(DOH_API_URL, params=params, timeout=10)
        data = response.json()
        
        if data.get("Status") == 3: # NXDOMAIN
            return False
        
        if not data.get("Answer"):
            return False
            
        return True
    except Exception as e:
        print(f"Error checking MX for {domain}: {e}")
        return False

def verify_email(record, collection=None):
    """Pipeline to verify a single email."""
    email = record.get("email", "")
    result = {"is_fake": False, "is_risky": False, "is_verified": True, "reason": "Passed"}
    
    if not is_valid_syntax(email):
        result = {"is_fake": True, "is_risky": False, "is_verified": False, "reason": "Invalid Syntax"}
    elif is_role_based(email):
        result = {"is_fake": False, "is_risky": True, "is_verified": True, "reason": "Role-Based Prefix"}
    else:
        domain = email.split('@')[1]
        if domain in DISPOSABLE_DOMAINS:
            result = {"is_fake": True, "is_risky": False, "is_verified": False, "reason": "Disposable Domain"}
        elif not has_mx_records(domain):
            result = {"is_fake": True, "is_risky": False, "is_verified": False, "reason": "Dead Domain (No MX)"}
            
    print(f"[Result] {email} -> {result['reason']}")
    
    if collection is not None and "_id" in record:
        try:
            collection.update_one(
                {"_id": record["_id"]},
                {"$set": {
                    "is_fake": result["is_fake"], 
                    "is_risky": result["is_risky"],
                    "is_verified": result["is_verified"]
                }}
            )
        except Exception as e:
            print(f"DB Update failed for {email}: {e}")
            
    return result

def main():
    parser = argparse.ArgumentParser(description="Efficient Email Verification Pipeline")
    parser.add_argument("--mode", choices=["db", "dummy"], default="dummy", help="Execution mode")
    parser.add_argument("--batch", type=int, default=1000, help="Batch size for DB mode")
    args = parser.parse_args()
    
    fetch_disposable_blocklist()
    
    if args.mode == "dummy":
        print("\n--- Running in DUMMY Mode ---")
        with ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(verify_email, DUMMY_EMAILS)
        print("\n✅ Dummy Mode Complete. Check results above.")
        
    elif args.mode == "db":
        print("\n--- Running in DB Mode ---")
        if not MONGO_URI:
            print("❌ MONGO_URI not found in environment variables.")
            return

        client = MongoClient(MONGO_URI)
        try:
            db = client[MONGO_DB]
            collection = db["temp"]
            
            total_processed = 0
            while True:
                # Fetch unverified records
                query = {
                    "$or": [
                        {"is_verified": {"$exists": False}},
                        {"is_verified": False},
                        {"is_verified": None}
                    ]
                }
                records = list(collection.find(query).limit(args.batch))
                
                if not records:
                    print("No more unverified records found.")
                    break
                
                print(f"\nProcessing batch of {len(records)}...")
                with ThreadPoolExecutor(max_workers=10) as executor:
                    futures = [executor.submit(verify_email, record, collection) for record in records]
                    for future in as_completed(futures):
                        future.result()
                        
                total_processed += len(records)
                print(f"Batch complete. Total processed: {total_processed}")
                
                if len(records) < args.batch:
                    break
                    
            print("\n✅ DB Mode Complete.")
        except Exception as e:
            print(f"❌ MongoDB Error: {e}")
        finally:
            client.close()

if __name__ == "__main__":
    main()
