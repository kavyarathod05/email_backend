from dotenv import load_dotenv

load_dotenv()

from config import recruiters_col
from routes.recruiters import get_top_tier_companies, normalize_company

def run_update():
    print("Loading top tier companies list...")
    top_tier = get_top_tier_companies()
    print(f"Loaded {len(top_tier)} top tier companies.")
    
    print("Fetching recruiters without companyType...")
    # Find all or just those missing companyType. Let's do all to be safe.
    recruiters = list(recruiters_col.find({}))
    
    updated_top_tier = 0
    updated_startup = 0
    total_processed = 0
    
    for r in recruiters:
        total_processed += 1
        company = normalize_company(r.get("company", ""))
        c_type = "top_tier" if company in top_tier else "startup"
        
        print(f"[{total_processed}/{len(recruiters)}] Processing {r.get('email', 'Unknown')} -> {c_type}")
        
        # Only update if it's missing or different
        if r.get("companyType") != c_type:
            recruiters_col.update_one(
                {"_id": r["_id"]},
                {"$set": {"companyType": c_type}}
            )
            if c_type == "top_tier":
                updated_top_tier += 1
            else:
                updated_startup += 1
                
    print(f"Update complete. Tagged {updated_top_tier} as Top Tier, {updated_startup} as Startup.")

if __name__ == "__main__":
    run_update()
