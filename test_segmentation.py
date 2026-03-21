import os
from dotenv import load_dotenv

load_dotenv()

from services.email_builder import build_email
from routes.recruiters import get_top_tier_companies, normalize_company

def run_tests():
    print("--- Testing Company Normalization & Top Tier Lookup ---")
    companies = get_top_tier_companies()
    print(f"Loaded {len(companies)} top tier companies.")
    assert "Google" in companies, "Google should be in top tier"
    
    test_cases = [" Google ", "google", "GOOGLE "]
    for tc in test_cases:
        norm = normalize_company(tc)
        print(f"Normalized '{tc}' -> '{norm}'")
        assert norm in companies, f"Failed: {norm} not in top tier list"
    
    print("\n--- Testing Email Builder Conditional AI ---")
    
    # Mock template doc
    template_doc = {
        "htmlBody": "Hi {name},\n{opening_line}\nI love {company}.\n{proof_line}\n{resume_link}",
        "subject": "Hello {name} at {company}"
    }

    # Test Startup (should not have AI opening/proof)
    startup_recruiter = {
        "email": "test@startup.com",
        "name": "Bob",
        "company": "Some Startup",
        "companyType": "startup"
    }
    
    print("Building generic startup email...")
    email_data_startup = build_email(startup_recruiter, template_doc)
    print("Startup HTML:")
    print(email_data_startup["HTMLPart"])
    assert "Hi Bob," in email_data_startup["HTMLPart"]
    
    # Test Top Tier (should trigger logger info for AI and have AI lines if AI service responds)
    top_tier_recruiter = {
        "email": "test@google.com",
        "name": "Alice",
        "company": "Google",
        "companyType": "top_tier"
    }

    print("\nBuilding top tier personalized email...")
    email_data_top = build_email(top_tier_recruiter, template_doc)
    print("Top Tier HTML Preview:")
    print(email_data_top["HTMLPart"][:200])
    
    print("\nTests completed.")

if __name__ == "__main__":
    run_tests()
