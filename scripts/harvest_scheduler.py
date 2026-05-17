"""
Batch Lead Harvester Scheduler
Reads top_tier_companies.txt, deduplicates, and harvests recruiter leads for 5 new companies at a time.
Bypasses all SMTP checks to run at lightning speed, adding 3-4 leads per company with natural time spacing.
"""
import os
import sys
import time
from datetime import datetime

# Add root folder to python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import recruiters_col, logger
import services.lead_finder as lf

def run_batch_harvest(batch_size: int = 5, leads_per_company: int = 4):
    logger.info("=" * 60)
    logger.info("           STARTING BATCH LEAD HARVEST SCHEDULER           ")
    logger.info("=" * 60)
    
    # 1. Enforce SMTP socket bypass completely as requested
    lf.IS_SMTP_PORT_25_OPEN = False
    logger.info("ℹ️ SMTP active handshakes are FORCED OFF to run at maximum speed.")

    # 2. Read companies list from top_tier_companies.txt
    company_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "top_tier_companies.txt")
    if not os.path.exists(company_file):
        logger.error(f"❌ Companies file not found at: {company_file}")
        return
        
    with open(company_file, "r", encoding="utf-8") as f:
        raw_companies = [line.strip() for line in f if line.strip()]
        
    # Deduplicate companies while preserving order
    seen = set()
    companies = []
    for c in raw_companies:
        c_lower = c.lower()
        if c_lower not in seen:
            seen.add(c_lower)
            companies.append(c)
            
    logger.info(f"Loaded {len(companies)} unique companies from top_tier_companies.txt.")
    
    # 3. Find companies already harvested in DB
    existing_companies = set(c.lower() for c in recruiters_col.distinct("company"))
    logger.info(f"Found {len(existing_companies)} companies already stored in MongoDB.")
    
    # Filter out already harvested companies
    pending_companies = [c for c in companies if c.lower() not in existing_companies]
    logger.info(f"Remaining pending companies for harvesting: {len(pending_companies)}")
    
    if not pending_companies:
        logger.info("🎉 All companies in list have already been harvested!")
        return
        
    # Get the next batch of 5 companies
    target_batch = pending_companies[:batch_size]
    logger.info(f"👉 Target batch for this run (size={batch_size}): {', '.join(target_batch)}")
    
    for idx, company in enumerate(target_batch):
        logger.info("-" * 50)
        logger.info(f"[{idx+1}/{batch_size}] Harvesting recruiters for: {company}...")
        
        try:
            # Run the generator to completion
            generator = lf.run_lead_generation_agent(company, company_type="top_tier", limit=leads_per_company)
            added_count = 0
            
            for step in generator:
                if step["type"] == "log":
                    logger.info(f"   {step['message']}")
                elif step["type"] == "error":
                    logger.error(f"   ❌ {step['message']}")
                elif step["type"] == "complete":
                    added_count = step["data"]["count_added"]
                    logger.info(f"   🏁 Completed: Added {added_count} recruiters for {company}.")
                    
        except Exception as e:
            logger.error(f"   💥 Failed harvesting {company}: {e}")
            
        # Apply timing difference (natural spacing) to prevent search bot blocking
        if idx < len(target_batch) - 1:
            delay = 20
            logger.info(f"⏳ Sleeping for {delay} seconds to space out queries naturally...")
            time.sleep(delay)
            
    logger.info("=" * 60)
    logger.info("           BATCH LEAD HARVEST SCHEDULER COMPLETED          ")
    logger.info("=" * 60)

if __name__ == "__main__":
    run_batch_harvest()
