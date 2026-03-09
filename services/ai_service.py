"""
AI Personalization Service: handles LLM completions via Hugging Face Inference API.
"""

import os
import requests
import logging

from config import logger

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
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.7,
            },
            timeout=20,
        )
        if resp.status_code == 200:
            data = resp.json()
            result = data["choices"][0]["message"]["content"].strip()
            logger.info(f"AI Generation Successful: {result[:50]}...")
            return result
        else:
            logger.warning(f"HF API returned {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.error(f"HF API error: {e}")
    return ""


def generate_company_sentence(company: str) -> str:
    """Generates a one-sentence engineering-focused description of a company."""
    if not company or company == "your team":
        return ""

    if company in _company_sentence_cache:
        logger.info(f"Company sentence Cache HIT: {company}")
        return _company_sentence_cache[company]

    prompt = (
        f"You are writing a cold email for an engineering internship.\n"
        f"Write ONE natural sentence (12-18 words) about {company}.\n\n"
        f"Requirements:\n"
        f"- Mention {company}\n"
        f"- Reference backend systems, engineering scale, infrastructure, or product impact\n"
        f"- Sound like a genuine observation from an engineer\n"
        f"- Avoid marketing words like 'leading', 'great', 'innovative'\n"
        f"- Make it specific and thoughtful\n\n"
        f"Return ONLY the sentence."
    )
    logger.info(f"Generating new company sentence for: {company}")
    result = _hf_generate(prompt)
    if result:
        _company_sentence_cache[company] = result
    return result


def generate_opening_line(company: str) -> str:
    """Generates a short opening line for a cold email to a recruiter."""
    if not company or company == "your team":
        return ""

    prompt = (
        f"You are writing the FIRST line of a cold email to a recruiter at {company}.\n"
        f"The goal is to sound genuine, curious, and not automated.\n\n"
        f"Context:\n"
        f"- I am a backend engineering student\n"
        f"- Interested in distributed systems, scalable infrastructure, and AI systems\n\n"
        f"Write ONE short natural sentence (10-16 words).\n"
        f"Reference {company}'s engineering or product scale.\n"
        f"Tone: friendly, thoughtful, human.\n"
        f"Avoid sounding like marketing or a template.\n\n"
        f"Return ONLY the sentence."
    )
    logger.info(f"Generating opening line for: {company}")
    return _hf_generate(prompt)


def generate_subject_lines(company: str) -> list:
    """Generates 5 short email subject lines for an internship application."""
    if not company or company == "your team":
        return []

    prompt = (
        f"You are writing subject lines for a cold email to a recruiter at {company}.\n\n"
        f"Goal: maximize open and reply rate for an engineering internship email.\n\n"
        f"Rules:\n"
        f"- Exactly 5 subject lines\n"
        f"- Maximum 5 words each\n"
        f"- Natural and human\n"
        f"- Avoid spam words like 'Opportunity', 'Apply', 'Request'\n"
        f"- Create curiosity\n"
        f"- Mention engineering or backend when possible\n\n"
        f"Output ONLY the 5 lines."
    )
    raw = _hf_generate(prompt, max_tokens=120)
    if raw:
        lines = [
            l.strip().lstrip("0123456789.-*) ") for l in raw.split("\n") if l.strip()
        ]
        lines = [l for l in lines if 0 < len(l) < 80][:5]
        if len(lines) >= 3:
            return lines
    return []
