"""
=================================================================
  PERSONALIZATION ENGINE — STEP-BY-STEP DEMO
  Run this to see exactly what happens at each stage
  for a sample recruiter email.
=================================================================
Usage:
    python test_pipeline_demo.py
    python test_pipeline_demo.py --email jane.doe@google.com --company google
"""
import re
import os
import sys
import json
import requests
import argparse
from dotenv import load_dotenv

load_dotenv()

# ─── Colors for terminal ───
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
DIM    = "\033[2m"

def header(step_num, title):
    print(f"\n{'='*60}")
    print(f"  {BOLD}STEP {step_num}: {title}{RESET}")
    print(f"{'='*60}")

def label(text, value):
    print(f"  {CYAN}{text:25s}{RESET} {BOLD}{value}{RESET}")

def sublabel(text, value):
    print(f"  {DIM}{text:25s}{RESET} {value}")

# ─── Functions copied from app.py ───

def extract_first_name(email_addr: str) -> str:
    if not email_addr or "@" not in email_addr:
        return "there"
    local_part = email_addr.split("@")[0]
    name_cleaned = re.sub(r"[\._\-]", " ", local_part)
    tokens = name_cleaned.split()
    if tokens:
        first_token = tokens[0]
        if len(tokens) == 1 and len(first_token) > 7:
            return first_token[:5].capitalize()
        return first_token.capitalize()
    return "there"

def normalize_company(company_name: str) -> str:
    if not company_name:
        return ""
    return company_name.strip().title()

HF_API_KEY = os.getenv("HF_API_KEY", "")
HF_MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct"
HF_API_URL = "https://router.huggingface.co/v1/chat/completions"

def _hf_generate(prompt: str, max_tokens: int = 60) -> str:
    if not HF_API_KEY:
        return "[NO HF_API_KEY]"
    try:
        resp = requests.post(
            HF_API_URL,
            headers={"Authorization": f"Bearer {HF_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": HF_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.7
            },
            timeout=30
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        else:
            return f"[HTTP {resp.status_code}]"
    except Exception as e:
        return f"[ERROR: {e}]"

# ─── MAIN DEMO ───

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default="john.smith@stripe.com", help="Recruiter email")
    parser.add_argument("--company", default="stripe", help="Company name (raw)")
    args = parser.parse_args()

    raw_email = args.email
    raw_company = args.company

    print(f"\n{BOLD}{'*'*60}")
    print(f"  PERSONALIZATION ENGINE — LIVE DEMO")
    print(f"{'*'*60}{RESET}")
    label("Input Email:", raw_email)
    label("Input Company:", raw_company)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    header(1, "LEAD ENRICHMENT")
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # 1a. First name extraction
    local_part = raw_email.split("@")[0] if "@" in raw_email else raw_email
    cleaned = re.sub(r"[\._\-]", " ", local_part)
    tokens = cleaned.split()
    first_name = extract_first_name(raw_email)

    print(f"\n  {YELLOW}First Name Extraction:{RESET}")
    sublabel("  Raw email:", raw_email)
    sublabel("  Local part:", local_part)
    sublabel("  After replacing . _ -:", cleaned)
    sublabel("  Tokens:", str(tokens))
    sublabel("  First token:", tokens[0] if tokens else "none")
    label("  → Extracted Name:", first_name)

    # 1b. Company normalization
    company = normalize_company(raw_company)
    print(f"\n  {YELLOW}Company Normalization:{RESET}")
    sublabel("  Raw input:", f'"{raw_company}"')
    sublabel("  After .strip():", f'"{raw_company.strip()}"')
    sublabel("  After .title():", f'"{raw_company.strip().title()}"')
    label("  → Normalized:", company)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    header(2, "AI — COMPANY SENTENCE")
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    cs_prompt = (
        f"Write one sentence (under 20 words) about {company} that is specific and engineering-focused. "
        f"Mention the company name. Reference engineering, technology, scale, or product impact. "
        f'Avoid generic phrases like "great company". Output only the sentence.'
    )
    print(f"\n  {YELLOW}Prompt sent to AI:{RESET}")
    for line in cs_prompt.split(". "):
        print(f"  {DIM}  {line.strip()}.{RESET}")

    print(f"\n  {YELLOW}Calling Hugging Face API...{RESET}")
    print(f"  {DIM}  Model: {HF_MODEL}{RESET}")
    print(f"  {DIM}  max_tokens: 60, temperature: 0.7{RESET}")

    company_sentence = _hf_generate(cs_prompt)
    label("  → Company Sentence:", company_sentence)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    header(3, "AI — OPENING LINE")
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    ol_prompt = (
        f"Write one short opening line (max 20 words) for a cold email to a recruiter at {company}. "
        f"I am a backend engineer interested in scalable systems and AI. "
        f"Reference {company}'s engineering scale or backend challenges. Natural, professional tone. Output only the sentence."
    )
    print(f"\n  {YELLOW}Prompt sent to AI:{RESET}")
    for line in ol_prompt.split(". "):
        print(f"  {DIM}  {line.strip()}.{RESET}")

    print(f"\n  {YELLOW}Calling Hugging Face API...{RESET}")
    opening_line = _hf_generate(ol_prompt)
    label("  → Opening Line:", opening_line)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    header(4, "AI — SUBJECT LINES (5 options)")
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    sl_prompt = (
        f"Generate exactly 5 short email subject lines for a Summer 2026 Backend Intern application at {company}. "
        f"Rules: max 6 words each, professional, curiosity-driven. "
        f"Output only the 5 lines, one per line, no numbering, no extra text."
    )
    print(f"\n  {YELLOW}Prompt sent to AI:{RESET}")
    for line in sl_prompt.split(". "):
        print(f"  {DIM}  {line.strip()}.{RESET}")

    print(f"\n  {YELLOW}Calling Hugging Face API...{RESET}")
    raw_subjects = _hf_generate(sl_prompt, max_tokens=120)

    # Post-processing
    lines = [l.strip().lstrip("0123456789.-*) ") for l in raw_subjects.split("\n") if l.strip()]
    lines = [l for l in lines if 0 < len(l) < 80][:5]

    print(f"\n  {YELLOW}Raw AI output:{RESET}")
    print(f"  {DIM}{raw_subjects}{RESET}")

    print(f"\n  {YELLOW}After post-processing (strip numbering, filter):{RESET}")
    if len(lines) >= 3:
        for i, subj in enumerate(lines):
            print(f"    {GREEN}[{i+1}]{RESET} {subj}")
        subject_lines = lines
    else:
        subject_lines = [
            f"Summer 2026 Backend Intern",
            f"Backend Intern — {company}",
            f"Quick Question About Internships",
            f"Engineer Interested in {company}",
            f"Internship Opportunity Inquiry",
        ]
        print(f"  {YELLOW}⚠ Less than 3 usable lines → using fallback subjects{RESET}")
        for i, subj in enumerate(subject_lines):
            print(f"    {GREEN}[{i+1}]{RESET} {subj}")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    header(5, "SUBJECT LINE A/B ROTATION")
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    print(f"\n  {YELLOW}Rotation simulation (modulo-based):{RESET}")
    for i in range(min(6, len(subject_lines) + 1)):
        chosen = subject_lines[i % len(subject_lines)]
        marker = " ← WOULD BE USED NOW" if i == 0 else ""
        print(f"    Email #{i+1}: index {i} % {len(subject_lines)} = {i % len(subject_lines)}  →  \"{chosen}\"{GREEN}{marker}{RESET}")

    chosen_subject = subject_lines[0]

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    header(6, "FINAL EMAIL PREVIEW")
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    print(f"\n  {YELLOW}Subject:{RESET} {BOLD}{chosen_subject}{RESET}")
    print(f"\n  {YELLOW}Body:{RESET}")
    print(f"  ┌────────────────────────────────────────────────────┐")
    print(f"  │ Hi {first_name},                                   ")
    print(f"  │                                                    ")
    if opening_line and not opening_line.startswith("["):
        print(f"  │ {opening_line}                                     ")
        print(f"  │                                                    ")
    print(f"  │ I'm Kavya Rathod, a Software Intern at Discvr.ai  ")
    print(f"  │ (IIIT Gwalior '27). I'm seeking a Summer 2026     ")
    print(f"  │ Internship at {company}.                           ")
    print(f"  │                                                    ")
    if company_sentence and not company_sentence.startswith("["):
        print(f"  │ {company_sentence[:55]}  ")
        if len(company_sentence) > 55:
            print(f"  │ {company_sentence[55:]}  ")
        print(f"  │                                                    ")
    print(f"  │ Engineering & Scale:                                ")
    print(f"  │ • 10k Daily Traffic: Led a team of 5               ")
    print(f"  │ • Production AI: Built RAG systems                 ")
    print(f"  │ • LeetCode Knight (1800+) | CF Expert (1700+)      ")
    print(f"  │                                                    ")
    print(f"  │ 🔗 View Full Resume                                ")
    print(f"  │                                                    ")
    print(f"  │ Best,                                              ")
    print(f"  │ Kavya Rathod                                       ")
    print(f"  └────────────────────────────────────────────────────┘")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    header(7, "TRACKING (would be injected)")
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    tracking_base = os.getenv("TRACKING_BASE_URL", "http://127.0.0.1:10000")
    print(f"\n  {YELLOW}Open Pixel:{RESET}")
    print(f"  {DIM}  <img src=\"{tracking_base}/track/open/{raw_email}\" width=\"1\" height=\"1\" />{RESET}")
    print(f"\n  {YELLOW}Click-tracked Resume Link:{RESET}")
    resume = os.getenv("RESUME_LINK", "https://drive.google.com/your-resume")
    print(f"  {DIM}  {tracking_base}/track/click/{raw_email}?url={resume[:50]}...{RESET}")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    header(8, "FOLLOW-UP SCENARIOS")
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    print(f"\n  {YELLOW}After sending, the system monitors engagement:{RESET}")
    print(f"""
    ┌────────┬────────────────────┬────────────────────────────────┐
    │ Signal │ Timing             │ Action                         │
    ├────────┼────────────────────┼────────────────────────────────┤
    │ {GREEN}HOT{RESET}    │ Clicked → +36 hrs  │ "I noticed you viewed my       │
    │        │                    │  resume..." (direct tone)      │
    ├────────┼────────────────────┼────────────────────────────────┤
    │ {YELLOW}WARM{RESET}   │ Opened  → +3 days  │ "Just checking in..."          │
    │        │                    │  (light reminder)              │
    ├────────┼────────────────────┼────────────────────────────────┤
    │ {DIM}COLD{RESET}   │ Nothing → +4 days  │ Resend email with NEW subject  │
    │        │                    │  line from the rotation pool   │
    ├────────┼────────────────────┼────────────────────────────────┤
    │ 💀     │ Stage 1  → +6 days │ Breakup email: "I won't reach  │
    │        │                    │  out again"                    │
    └────────┴────────────────────┴────────────────────────────────┘""")

    print(f"\n{BOLD}{'='*60}")
    print(f"  DEMO COMPLETE ✅")
    print(f"{'='*60}{RESET}\n")

if __name__ == "__main__":
    main()
