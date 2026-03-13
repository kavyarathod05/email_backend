import os
import argparse
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB")

def fetch_emails_in_batches(batch_number=None, batch_size=1000, output_file="emails.txt"):
    """Fetches recruiter emails from the database in batches and saves to a file."""
    try:
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB]
        col = db["temp"]

        total_records = col.count_documents({})
        print(f"Total records in collection: {total_records}")

        if batch_number is not None:
            # Fetch only the specific batch
            skip = (batch_number - 1) * batch_size
            if skip >= total_records:
                print(f"❌ Batch {batch_number} is out of range. Only {total_records} records found.")
                return

            print(f"\n--- Fetching Batch {batch_number} (Skip: {skip}, Limit: {batch_size}) ---")
            cursor = col.find({}, {"email": 1, "_id": 0}).skip(skip).limit(batch_size)
            records = list(cursor)

            with open(output_file, "w", encoding="utf-8") as f:
                for doc in records:
                    email = doc.get("email")
                    if email:
                        f.write(f"{email}\n")
            
            print(f"Fetched and saved {len(records)} emails to {output_file}.")
        else:
            # Fetch all batches sequentially (existing behavior)
            skip = 0
            batch_count = 1
            with open(output_file, "w", encoding="utf-8") as f:
                while skip < total_records:
                    print(f"\n--- Fetching Batch {batch_count} (Skip: {skip}, Limit: {batch_size}) ---")
                    cursor = col.find({}, {"email": 1, "_id": 0}).skip(skip).limit(batch_size)
                    records = list(cursor)
                    if not records:
                        break
                    for doc in records:
                        email = doc.get("email")
                        if email:
                            f.write(f"{email}\n")
                    print(f"Fetched and saved {len(records)} emails.")
                    skip += batch_size
                    batch_count += 1

        client.close()
        print(f"\n✅ Done. Output saved to {output_file}.")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch emails from MongoDB in batches.")
    parser.add_argument("--batch", type=int, help="Specify which batch to fetch (1, 2, 3...)")
    parser.add_argument("--size", type=int, default=1000, help="Batch size (default: 1000)")
    parser.add_argument("--out", type=str, default="emails.txt", help="Output file (default: emails.txt)")
    
    args = parser.parse_args()
    fetch_emails_in_batches(batch_number=args.batch, batch_size=args.size, output_file=args.out)
