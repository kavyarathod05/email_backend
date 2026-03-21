import os
from dotenv import load_dotenv

load_dotenv()

from config import recruiters_col

def export_emails():
    print("Fetching recruiters from database...")
    recruiters = list(recruiters_col.find({}, {"email": 1, "_id": 0}))
    
    count = 0
    with open("all_emails.txt", "w", encoding="utf-8") as f:
        for r in recruiters:
            email = r.get("email")
            if email:
                f.write(email + "\n")
                count += 1
                
    print(f"Successfully exported {count} emails to all_emails.txt")

if __name__ == "__main__":
    export_emails()
