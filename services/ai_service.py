"""
AI Personalization Service: handles LLM completions via Gemini API.
"""

import os
import requests
import json
import time

from config import logger

SYSTEM_PROMPT = """
You are a highly efficient assistant that generates structured JSON for personalized outreach.

## Kavya Rathod's Profile
- Education: IIIT Gwalior, B.Tech IT (8.35 CGPA). LeetCode Knight, Codeforces Specialist.
- Exp: DiscvrAI (Backend, Node.js/Redis, SSR), Nani's Bilona Ghee (Fintech, Razorpay, Python).
- Projects: TBO Events (Go/Fiber, Redis, Concurrency), AI RAGBot (Next.js, LangChain).
- Skills: Go, Python, Node.js, Next.js, Redis, AWS, SQL.

## Goal
Generate a JSON object for a Summer 2026 SDE Internship outreach to the specified company.

## JSON Requirements
Strictly return a JSON object with these fields:
1. "opening_line": A hook about their product/stack that includes the [Company Name] and expresses how eager I am to work with them (max 15 words).
2. "proof_line": A domain-matched result from Kavya's profile (mention tools used, max 15 words).
3. "subject_lines": A list of 6 UNIQUE and diverse catchy strings (max 6 words each). Must include "Kavya", [Company Name], and "Summer 2026". Use varied styles: technical, curious, or direct.

Example:
{
  "opening_line": "Impressive real-time tech at [Company Name]; I'm very eager to contribute to your backend.",
  "proof_line": "Built a Go/Redis event platform for 1000+ attendees implementing 2-Phase Locking.",
  "subject_lines": [
    "Kavya | [Company Name] | SDE Intern Summer 2026",
    "Engineering @ [Company Name] | Kavya",
    "Kavya | Summer 2026 Intern @ [Company Name]",
    "Backend/Go | Kavya for [Company Name]",
    "Kavya | [Company Name] Tech & Growth",
    "Summer 2026 | Kavya Rathod x [Company Name]"
  ]
}
"""

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key={GEMINI_API_KEY}"
# --- In-memory company sentence cache (reduces API calls) ---
_company_sentence_cache: dict = {}


def generate_personalized_content(company: str) -> dict:
    """
    Generates all personalized content for an email in a single structured API call.
    Returns a dict with: opening_line, proof_line, subject_lines.
    """
    if not company or company == "your team":
        return {}

    # Check cache first
    if company in _company_sentence_cache:
        logger.info(f"AI Content Cache HIT: {company}")
        return _company_sentence_cache[company]

    prompt = (
        f"Generate personalized email content for {company} (use '{company}' where [Company Name] is requested) "
        "based on our engineering background and Summer 2026 internship goals.\n\n"
        "Return the response as a VALID JSON object."
    )

    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set. Skipping AI generation.")
        return {}

    attempts = 3
    base_delay = 2  # seconds

    for attempt in range(attempts):
        try:
            payload = {
                "contents": [
                    {
                        "parts": [{"text": prompt}]
                    }
                ],
                "system_instruction": {
                    "parts": [{"text": SYSTEM_PROMPT}]
                },
                "generationConfig": {
                    "maxOutputTokens": 400,
                    "temperature": 0.0,
                    "response_mime_type": "application/json",
                    "response_schema": {
                        "type": "object",
                        "properties": {
                            "opening_line": {"type": "string"},
                            "proof_line": {"type": "string"},
                            "subject_lines": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["opening_line", "proof_line", "subject_lines"]
                    }
                },
                "safetySettings": [
                    {
                        "category": "HARM_CATEGORY_HARASSMENT",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "threshold": "BLOCK_NONE"
                    }
                ]
            }
            resp = requests.post(
                GEMINI_API_URL,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=25,
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if "candidates" in data and len(data["candidates"]) > 0:
                    candidate = data["candidates"][0]
                    finish_reason = candidate.get("finishReason")
                    
                    # Join all text parts
                    raw_text = "".join([p.get("text", "") for p in candidate.get("content", {}).get("parts", []) if "text" in p])
                    
                    if not raw_text.strip():
                        logger.warning(f"⚠️ Empty AI response for {company}. Reason: {finish_reason}")
                        continue

                    # 1. Clean markdown
                    clean_json = raw_text.strip()
                    if "```json" in clean_json:
                        clean_json = clean_json.split("```json")[-1].split("```")[0].strip()
                    elif "```" in clean_json:
                        clean_json = clean_json.split("```")[-1].split("```")[0].strip()

                    # 2. Extract first legitimate-looking object
                    start = clean_json.find("{")
                    if start != -1:
                        # Find the matching closing brace, or just the last one if truncated
                        end = clean_json.rfind("}")
                        if end == -1 or end < start:
                            # TRUNCATED JSON REPAIR
                            logger.warning(f"🔧 Attempting repair on truncated JSON for {company}...")
                            # Basic repair: remove trailing comma, close quotes, brackets, then the object
                            repaired = clean_json[start:].strip()
                            if repaired.endswith(","):
                                repaired = repaired[:-1].strip()
                            if repaired.count('"') % 2 != 0:
                                repaired += '"'
                            if repaired.count('[') > repaired.count(']'):
                                repaired += ']'
                            if repaired.count('{') > repaired.count('}'):
                                repaired += '}'
                            clean_json = repaired
                        else:
                            clean_json = clean_json[start : end + 1]

                    try:
                        result = json.loads(clean_json)
                        logger.info(f"✅ Success! AI Personalization for {company} (Reason: {finish_reason})")
                        _company_sentence_cache[company] = result
                        return result
                    except json.JSONDecodeError:
                        # Log meaningful diagnostics
                        logger.error(f"❌ JSON Parse Error for {company}. Reason: {finish_reason}")
                        logger.error(f"PROCESSED JSON: {clean_json[:500]}...")
                        # One last ditch effort: if it's truncated at an array, try closing it
                        continue
            elif resp.status_code == 429:
                delay = base_delay * (2 ** attempt) + (0.5 * attempt)
                logger.warning(f"❌ Error 429: Quota Exceeded. Retrying in {delay}s... (Attempt {attempt + 1}/{attempts})")
                time.sleep(delay)
                continue
            elif resp.status_code == 400:
                logger.error(f"❌ Error 400: Bad Request. Check payload. Response: {resp.text}")
                break
            else:
                logger.warning(f"❌ API Error {resp.status_code}: {resp.text[:200]}")
                break
                
        except Exception as e:
            logger.error(f"❌ A network or system error occurred during AI generation: {e}")
            break

    return {}


def _gemini_generate(prompt: str, max_tokens: int = 60) -> str:
    """Legacy helper for single-value generation (deprecated)."""
    # This is kept for absolute fallback but should be phased out.
    if not GEMINI_API_KEY:
        return ""
    try:
        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.8}
        }
        resp = requests.post(GEMINI_API_URL, headers={"Content-Type": "application/json"}, json=payload, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            if "candidates" in data and len(data["candidates"]) > 0:
                return data["candidates"][0]["content"]["parts"][0]["text"].strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


def generate_company_sentence(company: str) -> str:
    """DEPRECATED: No longer used."""
    return ""


def generate_opening_line(company: str) -> str:
    """Wrapper to get opening line from full structured call."""
    return generate_personalized_content(company).get("opening_line", "")


def generate_proof_line(company: str = "") -> str:
    """Wrapper to get proof line (company is optional/ignored for now but kept for consistency)."""
    # If no company provided, we might need a fallback or just use a dummy one for the cache key
    # But proof line is likely the same for all. For now, just use global call.
    content = generate_personalized_content(company) if company else {}
    return content.get("proof_line", "I built scalable backend systems handling 10k daily traffic as a student.")


def generate_subject_lines(company: str) -> list:
    """Wrapper to get subject lines from full structured call."""
    return generate_personalized_content(company).get("subject_lines", [])
