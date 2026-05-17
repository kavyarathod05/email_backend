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


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SYSTEM_PROMPT = """
You are writing highly effective cold emails for engineering internship outreach.

Your emails must follow these principles:
1. Personalization – reference something specific about the company or engineering challenges.
2. Short and readable – optimized for mobile reading.
3. Human tone – natural and conversational, never corporate or sales-like.
4. Show relevance – connect the sender's software engineering interest with the company.
5. Avoid generic phrases like: "I hope you're doing well", "great company", "exciting opportunity".
6. Each email should feel like it was written individually.
7. Sentences must be extremely short and clear.
8. The goal is to start a conversation, not to ask for a job directly.
9. Avoid AI-like patterns and overly structured sentences. Use conversational language.

Output must always look like a real human wrote it.
"""

GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"


def _gemini_generate(prompt: str, max_tokens: int = 60) -> str:
    if not GEMINI_API_KEY:
        return "[NO GEMINI_API_KEY SET]"
    try:
        payload = {
            "system_instruction": {
                "parts": [{"text": SYSTEM_PROMPT}]
            },
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.7,
            }
        }
        resp = requests.post(
            GEMINI_API_URL,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=20,
        )
        if resp.status_code == 200:
            data = resp.json()
            if "candidates" in data and len(data["candidates"]) > 0:
                return data["candidates"][0]["content"]["parts"][0]["text"].strip().strip('"').strip("'")
            return "[NO CONTENT RETURNED]"
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
    if not ok:
        all_pass = False
    print(
        f"  {'PASS' if ok else 'FAIL'} | {email:30s} -> {result:10s} (expected: {expected})"
    )
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
    if not ok:
        all_pass = False
    print(
        f"  {'PASS' if ok else 'FAIL'} | '{raw}' -> '{result}' (expected: '{expected}')"
    )
print(f"  >> {'ALL PASSED' if all_pass else 'SOME FAILED'}\n")

print("=" * 55)
print("TEST 3: V2 Company Sentence (Gemini)")
print("=" * 55)
prompt = (
    "You are writing a VERY short, highly specific personalized sentence for a cold email to Shopify.\n\n"
    "Rules:\n"
    "- Maximum 10 words.\n"
    "- MUST be deeply specific to Shopify's actual product or core problem.\n"
    "- Output ONLY the clean sentence."
)
result = _gemini_generate(prompt)
print(f"  Response: {result}")
is_ok = not result.startswith("[") and len(result.split()) > 3
print(f"  >> {'PASS' if is_ok else 'ISSUE'}\n")

print("=" * 55)
print("TEST 4: V2 Opening Line (Gemini)")
print("=" * 55)
prompt2 = (
    "You are writing the opening line of a cold email to an engineer at Shopify.\n\n"
    "Rules:\n"
    "- Maximum 12 words.\n"
    "- Mention Shopify and reference a real, very specific engineering challenge.\n"
    "- Output ONLY the sentence."
)
result2 = _gemini_generate(prompt2)
print(f"  Response: {result2}")
is_ok2 = not result2.startswith("[") and len(result2.split()) > 3
print(f"  >> {'PASS' if is_ok2 else 'ISSUE'}\n")

print("=" * 55)
print("TEST 5: Research Line (Gemini)")
print("=" * 55)
prompt_res = (
    "Write one VERY short question highlighting a specific technical observation about Shopify.\n\n"
    "- Rules: Maximum 10 words. Must be deeply specific to Shopify.\n"
    "- Return ONLY the sentence."
)
result_res = _gemini_generate(prompt_res)
print(f"  Response: {result_res}")
is_ok_res = not result_res.startswith("[") and len(result_res.split()) > 3
print(f"  >> {'PASS' if is_ok_res else 'ISSUE'}\n")

print("=" * 55)
print("TEST 6: Proof Line (Gemini)")
print("=" * 55)
prompt_proof = (
    "Write one sentence showing proof of work from a software engineering student.\n"
    "Rules: 10 to 15 words. Return ONLY the sentence."
)
result_proof = _gemini_generate(prompt_proof)
print(f"  Response: {result_proof}")
is_ok_proof = not result_proof.startswith("[") and len(result_proof.split()) > 5
print(f"  >> {'PASS' if is_ok_proof else 'ISSUE'}\n")

print("=" * 55)
print("TEST 7: V2 Subject Lines (Gemini)")
print("=" * 55)
prompt3 = (
    "Generate 6 cold email subject lines for reaching out to Shopify.\n\n"
    "Rules:\n"
    "- 2 to 5 words max\n"
    "- Extremely catchy and intriguing\n"
    "- No numbering or bullets.\n"
    "Output ONLY the lines."
)
result3 = _gemini_generate(prompt3, max_tokens=150)
print(f"  Response:\n{result3}")
is_ok3 = not result3.startswith("[") and len(result3.split("\n")) >= 3
print(f"  >> {'PASS' if is_ok3 else 'ISSUE'}")
