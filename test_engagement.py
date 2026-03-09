import os
import sys
from datetime import datetime, timezone

# Add current directory to path so we can import app
sys.path.append(os.getcwd())

from app import build_email, build_followup_email

def test_engagement_features():
    print("🚀 Starting Engagement Feature Verification\n")

    # Mock Recruiter with Tech Stack
    recruiter = {
        "email": "test@example.com",
        "name": "Alex",
        "company": "TechCorp",
        "techStack": "Python/React",
        "clicked": False,
        "opened": False
    }

    # 1. Test Initial Email with CTA Buttons
    print("--- Testing Initial Email (CTA Buttons) ---")
    os.environ["EMAIL_TEMPLATE_HTML"] = "<p>Hi {name}, I'm interested in {company}. Are you open to a quick chat?</p>"
    os.environ["EMAIL_SUBJECT"] = "Internship @ {company}"
    
    email_data = build_email(recruiter)
    html = email_data["HTMLPart"]
    
    if "mailto:rathodkavya2005@gmail.com" in html:
        print("✅ Mailto buttons working")
    else:
        print("❌ Mailto buttons FAILED")

    # 2. Test Behavioral Follow-up (Only Opened)
    print("\n--- Testing Follow-up (Opened, Not Clicked) ---")
    recruiter["opened"] = True
    followup_data = build_followup_email(recruiter, stage=1)
    
    if "I noticed you opened it" in followup_data["HTMLPart"]:
        print("✅ Opened-behavior template working")
    else:
        print("❌ Opened-behavior template FAILED")

    # 3. Test Behavioral Follow-up (Clicked)
    print("\n--- Testing Follow-up (Clicked) ---")
    recruiter["clicked"] = True
    followup_data_clicked = build_followup_email(recruiter, stage=1)
    
    if "you took a look at my resume" in followup_data_clicked["HTMLPart"]:
        print("✅ Clicked-behavior template working")
    else:
        print("❌ Clicked-behavior template FAILED")

    print("\n✅ Verification Complete!")

if __name__ == "__main__":
    test_engagement_features()
