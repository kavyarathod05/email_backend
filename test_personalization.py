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
SYSTEM_PROMPT = """
You are writing highly effective cold emails for engineering internship outreach.

Your emails must follow these principles:
1. Personalization – reference something specific about the company or engineering challenges.
2. Short and readable – optimized for mobile reading.
3. Human tone – natural and conversational, never corporate or sales-like.
4. Show relevance – connect the sender's backend engineering interest with the company.
5. Avoid generic phrases like: "I hope you're doing well", "great company", "exciting opportunity".
6. Each email should feel like it was written individually.
7. Sentences must be short and clear.
8. The goal is to start a conversation, not ask for a job directly.
9. Avoid AI-like patterns and overly structured sentences. Vary sentence length naturally. Use conversational language.

Output must always look like a real human wrote it.
"""

HF_API_KEY = os.getenv("HF_API_KEY", "")
HF_MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct"
HF_API_URL = "https://router.huggingface.co/v1/chat/completions"


def _hf_generate(prompt: str, max_tokens: int = 60) -> str:
    if not HF_API_KEY:
        return "[NO HF_API_KEY SET]"
    try:
        resp = requests.post(
            HF_API_URL,
            headers={
                "Authorization": f"Bearer {HF_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": HF_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": max_tokens,
                "temperature": 0.7,
            },
            timeout=20,
        )
        if resp.status_code == 200:
            data = resp.json()
            return (
                data["choices"][0]["message"]["content"].strip().strip('"').strip("'")
            )
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
print("TEST 3: V2 Company Sentence")
print("=" * 55)
prompt = (
    f"You are writing the first personalized sentence of a cold email.\n\n"
    f"Company: Shopify\n\n"
    f"Write ONE thoughtful sentence showing you understand the company's engineering or product.\n\n"
    f"Rules: 10 to 16 words. Return ONLY the sentence."
)
result = _hf_generate(prompt)
print(f"  Response: {result}")
is_ok = not result.startswith("[") and len(result.split()) > 5
print(f"  >> {'PASS' if is_ok else 'ISSUE'}\n")

print("=" * 55)
print("TEST 4: V2 Opening Line")
print("=" * 55)
prompt2 = (
    f"You are writing the opening line of a cold email to a recruiter at Shopify.\n\n"
    f"Context: backend engineering student interested in scalable systems.\n"
    f"Rules: 10 to 15 words. Sound curious and genuine. Return ONLY the sentence."
)
result2 = _hf_generate(prompt2)
print(f"  Response: {result2}")
is_ok2 = not result2.startswith("[") and len(result2.split()) > 5
print(f"  >> {'PASS' if is_ok2 else 'ISSUE'}\n")

print("=" * 55)
print("TEST 5: Research Line")
print("=" * 55)
prompt_res = (
    f"Write one short sentence showing genuine curiosity about Shopify tech.\n\n"
    f"Rules: 10 to 15 words. No marketing tone. Return ONLY the sentence."
)
result_res = _hf_generate(prompt_res)
print(f"  Response: {result_res}")
is_ok_res = not result_res.startswith("[") and len(result_res.split()) > 5
print(f"  >> {'PASS' if is_ok_res else 'ISSUE'}\n")

print("=" * 55)
print("TEST 6: Proof Line")
print("=" * 55)
prompt_proof = (
    "Write one sentence showing proof of work from a backend engineering student.\n"
    "Rules: 12 to 18 words. Return ONLY the sentence."
)
result_proof = _hf_generate(prompt_proof)
print(f"  Response: {result_proof}")
is_ok_proof = not result_proof.startswith("[") and len(result_proof.split()) > 5
print(f"  >> {'PASS' if is_ok_proof else 'ISSUE'}\n")

print("=" * 55)
print("TEST 7: V2 Subject Lines")
print("=" * 55)
prompt3 = (
    "Generate 6 cold email subject lines for Shopify backend internship.\n"
    "Rules: 1 to 4 words ONLY. Natural human tone. Output only the lines."
)
result3 = _hf_generate(prompt3, max_tokens=120)
print(f"  Response:\n{result3}")
is_ok3 = not result3.startswith("[") and len(result3.split("\n")) >= 3
print(f"  >> {'PASS' if is_ok3 else 'ISSUE'}")
