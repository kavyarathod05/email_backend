"""
AI Personalization Service: handles LLM completions via Hugging Face Inference API.
"""

import os
import requests

from config import logger

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

# --- In-memory company sentence cache (reduces API calls) ---
_company_sentence_cache: dict = {}


def _hf_generate(prompt: str, max_tokens: int = 60) -> str:
    """Call Hugging Face Inference API using chat/completions format."""
    if not HF_API_KEY:
        logger.warning("HF_API_KEY not set. Skipping AI generation.")
        return ""
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
            result = data["choices"][0]["message"]["content"].strip()
            # Clean up potential quotes or accidental leading/trailing punctuation
            result = result.strip('"').strip("'")
            logger.info(f"AI Generation Successful: {result[:50]}...")
            return result
        else:
            logger.warning(f"HF API returned {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.error(f"HF API error: {e}")
    return ""


def generate_company_sentence(company: str) -> str:
    """Generates a one-sentence engineering-focused description of a company (V2)."""
    if not company or company == "your team":
        return ""

    if company in _company_sentence_cache:
        logger.info(f"Company sentence Cache HIT: {company}")
        return _company_sentence_cache[company]

    prompt = (
        f"You are writing the first personalized sentence of a cold email.\n\n"
        f"Company: {company}\n\n"
        f"Write ONE thoughtful sentence showing you understand the company's engineering or product.\n\n"
        f"Rules:\n"
        f"- 10 to 16 words\n"
        f"- Mention {company}\n"
        f"- Refer to engineering scale, backend systems, infrastructure, or product impact\n"
        f"- Sound like an observation from an engineer\n"
        f"- Avoid generic praise\n"
        f"- Must feel researched and personal\n\n"
        f"Output only the sentence."
    )
    logger.info(f"Generating V2 company sentence for: {company}")
    result = _hf_generate(prompt)
    if result:
        _company_sentence_cache[company] = result
    return result


def generate_opening_line(company: str) -> str:
    """Generates a short, personal opening line for cold outreach (V2)."""
    if not company or company == "your team":
        return ""

    prompt = (
        f"You are writing the opening line of a cold email to a recruiter or engineer at {company}.\n\n"
        f"The line must feel personal and thoughtful, not automated.\n\n"
        f"Context:\n"
        f"- Sender: backend engineering student\n"
        f"- Interests: scalable systems, distributed systems, AI infrastructure\n\n"
        f"Rules:\n"
        f"- 10 to 15 words\n"
        f"- Mention {company}\n"
        f"- Reference a real engineering challenge or product scale\n"
        f"- Sound curious and genuine\n"
        f"- No generic phrases\n"
        f"- Must feel like a human wrote it after researching the company\n\n"
        f"Return ONLY the sentence."
    )
    logger.info(f"Generating V2 opening line for: {company}")
    return _hf_generate(prompt)


def generate_research_line(company: str) -> str:
    """Generates a sentence showing deep research/curiosity about the company."""
    if not company or company == "your team":
        return ""

    prompt = (
        f"Write one short, personalized sentence highlighting a specific technical observation or genuine curiosity about {company}'s engineering.\n\n"
        f"Rules: 10 to 15 words. Use a thoughtful statement or a question. No marketing fluff. Return ONLY the sentence."
    )
    logger.info(f"Generating research line for: {company}")
    return _hf_generate(prompt, max_tokens=40)


def generate_proof_line() -> str:
    """Writes one sentence showing proof of work from a backend engineering student."""
    prompt = (
        "Write one sentence showing proof of work from a backend engineering student.\n\n"
        "Examples of proof:\n"
        "- built scalable backend projects\n"
        "- worked on distributed systems\n"
        "- built automation tools\n\n"
        "Rules:\n"
        "- 12 to 18 words\n"
        "- confident but not arrogant\n"
        "- natural tone\n\n"
        "Output only the sentence."
    )
    logger.info("Generating proof of work line")
    return _hf_generate(prompt)


def generate_subject_lines(company: str) -> list:
    """Generates 6 short email subject lines for an internship application (V2)."""
    if not company or company == "your team":
        return []

    prompt = (
        f"Generate 6 cold email subject lines for reaching out to {company} about a backend engineering internship.\n\n"
        f"Rules:\n"
        f"- 1 to 4 words only\n"
        f"- Natural human tone\n"
        f"- Avoid application language\n"
        f"- Avoid spam words like opportunity, apply, hiring\n"
        f"- Create curiosity\n\n"
        f"Examples of good style:\n"
        f"- quick question\n"
        f"- backend question\n"
        f"- engineering curiosity\n"
        f"- small ask\n\n"
        f"Output only the lines."
    )
    raw = _hf_generate(prompt, max_tokens=120)
    if raw:
        lines = [
            line.strip().lstrip("0123456789.-*) ").strip('"').strip("'")
            for line in raw.split("\n")
            if line.strip()
        ]
        # Filter for length and take up to 6
        final_lines = [line for line in lines if 0 < len(line.split()) <= 5][:6]
        if len(final_lines) >= 3:
            return final_lines
    return []
