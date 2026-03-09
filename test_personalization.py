"""Standalone tests for the Personalization Engine functions."""
import re
import os
import requests
from dotenv import load_dotenv

load_dotenv()

# ---- Functions from app.py (isolated for testing) ----

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
        return "[NO HF_API_KEY SET]"
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
            timeout=20
        )
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        else:
            return f"[HTTP {resp.status_code}]: {resp.text[:200]}"
    except Exception as e:
        return f"[ERROR]: {e}"

# ---- TESTS ----

print("=" * 55)
print("TEST 1: First Name Extraction")
print("=" * 55)
tests = [
    ("john.smith@stripe.com", "John"),
    ("jane_doe@google.com", "Jane"),
    ("bob-jones@meta.com", "Bob"),
    ("johndoe12@company.com", "Johnd"),
    ("hi@x.com", "Hi"),
    ("", "there"),
]
all_pass = True
for email, expected in tests:
    result = extract_first_name(email)
    ok = result == expected
    if not ok: all_pass = False
    print(f"  {'PASS' if ok else 'FAIL'} | {email:30s} -> {result:10s} (expected: {expected})")
print(f"  >> {'ALL PASSED' if all_pass else 'SOME FAILED'}\n")

print("=" * 55)
print("TEST 2: Company Normalization")
print("=" * 55)
company_tests = [
    ("stripe", "Stripe"),
    ("  google  ", "Google"),
    ("META", "Meta"),
    ("", ""),
]
all_pass = True
for raw, expected in company_tests:
    result = normalize_company(raw)
    ok = result == expected
    if not ok: all_pass = False
    print(f"  {'PASS' if ok else 'FAIL'} | '{raw}' -> '{result}' (expected: '{expected}')")
print(f"  >> {'ALL PASSED' if all_pass else 'SOME FAILED'}\n")

print("=" * 55)
print("TEST 3: HF API - Company Sentence")
print("=" * 55)
prompt = 'Write one sentence (under 20 words) about Stripe that is specific and engineering-focused. Mention the company name. Output only the sentence.'
result = _hf_generate(prompt)
print(f"  Response: {result}")
is_ok = not result.startswith("[")
print(f"  >> {'PASS' if is_ok else 'ISSUE'}\n")

print("=" * 55)
print("TEST 4: HF API - Opening Line")
print("=" * 55)
prompt2 = 'Write one short opening line (max 20 words) for a cold email to a recruiter at Google. I am a backend engineer. Natural tone. Output only the sentence.'
result2 = _hf_generate(prompt2)
print(f"  Response: {result2}")
is_ok2 = not result2.startswith("[")
print(f"  >> {'PASS' if is_ok2 else 'ISSUE'}\n")

print("=" * 55)
print("TEST 5: HF API - Subject Lines")
print("=" * 55)
prompt3 = 'Generate exactly 5 short email subject lines for a Summer 2026 Backend Intern application at Google. Max 6 words each. Output only the 5 lines.'
result3 = _hf_generate(prompt3, max_tokens=120)
print(f"  Response: {result3}")
is_ok3 = not result3.startswith("[")
print(f"  >> {'PASS' if is_ok3 else 'ISSUE'}")
