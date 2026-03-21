import os
from dotenv import load_dotenv
from pymongo import MongoClient

def delete_fake_emails():
    # Load environment variables
    load_dotenv()
    
    MONGO_URI = os.getenv("MONGO_URI")
    MONGO_DB = os.getenv("MONGO_DB")
    
    if not MONGO_URI or not MONGO_DB:
        print("❌ Missing MongoDB environment variables (MONGO_URI or MONGO_DB).")
        return
        
    try:
        print("Connecting to MongoDB...")
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB]
        collection = db["temp"] # As per existing configuration, temp is the active collection
        
        # Count fake emails before deleting
        fake_query = {"is_fake": True}
        count_fake = collection.count_documents(fake_query)
        
        if count_fake == 0:
            print("No fake emails found to delete.")
            return
            
        print(f"Found {count_fake} fake emails. Proceeding to delete...")
        
        # Delete fake emails
        result = collection.delete_many(fake_query)
        
        print(f"✅ Successfully deleted {result.deleted_count} fake emails.")
        
    except Exception as e:
        print(f"❌ Error during deletion: {e}")
    finally:
        if 'client' in locals():
            client.close()
            print("MongoDB connection closed.")

if __name__ == "__main__":
    delete_fake_emails()
