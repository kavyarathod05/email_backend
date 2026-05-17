"""
Lead Finder Service: uses free search scraping and Gemini to find recruiter details,
guesses their corporate emails, and verifies them via SMTP MX handshakes (detecting catch-alls).
"""
import socket
import smtplib
import urllib.request
import urllib.parse
import re
import json
import os
from bs4 import BeautifulSoup
import dns.resolver
from config import logger, recruiters_col
from services.ai_service import _gemini_generate

def search_duckduckgo(query: str) -> str:
    """
    Performs a free search on DuckDuckGo HTML and returns concatenated search result snippets.
    """
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read()
        soup = BeautifulSoup(html, "html.parser")
        snippets = []
        for result in soup.find_all("a", class_="result__snippet"):
            snippets.append(result.get_text().strip())
        
        return "\n".join(snippets[:10])
    except Exception as e:
        logger.error(f"DuckDuckGo search failed: {e}")
        return ""

def extract_recruiter_details(company_name: str) -> dict:
    """
    Uses DuckDuckGo and Gemini to find a recruiter's name and domain for a company.
    """
    logger.info(f"AI Lead Agent: Searching for recruiters at {company_name}")
    
    # 1. Search DDG
    query = f'site:linkedin.com/in "Technical Recruiter" OR "Talent Acquisition" "{company_name}"'
    snippets = search_duckduckgo(query)
    
    if not snippets:
        logger.warning(f"No search results found for {company_name}")
        return {}

    # 2. Query Gemini
    prompt = f"""
Based on these LinkedIn search snippets for recruiters at the company '{company_name}', extract a recruiter's name and the company's domain.

Search Snippets:
{snippets}

Strictly return a JSON object with these keys:
- "firstName": Clean first name of the recruiter (e.g. John). If not found, guess a highly probable name or use "Recruiter".
- "lastName": Clean last name of the recruiter (e.g. Doe). If not found, use "".
- "domain": The corporate email domain of the company (e.g. stripe.com or companyname.com).
- "company": Properly formatted company name.

Do not add any explanations, just return the raw JSON object.
"""
    raw_response = _gemini_generate(prompt, max_tokens=150)
    
    # Extract JSON safely
    try:
        clean_json = raw_response.strip()
        if "```json" in clean_json:
            clean_json = clean_json.split("```json")[-1].split("```")[0].strip()
        elif "```" in clean_json:
            clean_json = clean_json.split("```")[-1].split("```")[0].strip()
            
        start = clean_json.find("{")
        end = clean_json.rfind("}")
        if start != -1 and end != -1:
            clean_json = clean_json[start : end + 1]
            
        details = json.loads(clean_json)
        logger.info(f"AI Lead Agent: Extracted details: {details}")
        return details
    except Exception as e:
        logger.error(f"Failed to parse Gemini recruiter extraction: {e}. Raw response: {raw_response}")
        return {}

def generate_email_permutations(first: str, last: str, domain: str) -> list:
    """Generates the most common corporate email address patterns."""
    first = re.sub(r"[^a-zA-Z]", "", first.lower().strip())
    last = re.sub(r"[^a-zA-Z]", "", last.lower().strip())
    domain = domain.lower().strip()
    
    if not first or not domain:
        return []
        
    guesses = []
    
    # Standard patterns
    guesses.append(f"{first}@{domain}")
    if last:
        guesses.append(f"{first}.{last}@{domain}")
        guesses.append(f"{first}{last[0]}@{domain}")
        guesses.append(f"{first[0]}{last}@{domain}")
        guesses.append(f"{first[0]}.{last}@{domain}")
        guesses.append(f"{first}{last}@{domain}")
        guesses.append(f"{first}_{last}@{domain}")
    
    # Remove duplicates
    return list(dict.fromkeys(guesses))

def verify_email_smtp(email_addr: str) -> bool:
    """
    Connects to the domain's MX server to verify if the email address exists.
    Includes catch-all detection for reliable checks.
    """
    domain = email_addr.split("@")[1]
    
    # 1. Resolve MX record
    try:
        mx_records = dns.resolver.resolve(domain, "MX")
        mx_host = str(sorted(mx_records, key=lambda r: r.preference)[0].exchange).rstrip(".")
    except Exception as e:
        logger.warning(f"SMTP Verification: No MX record for {domain}: {e}")
        return False
        
    # 2. Check for catch-all (does a fake email also work?)
    catchall_test_email = f"gibberish_check_12345@{domain}"
    
    def check_recipient(recipient: str) -> bool:
        try:
            # We connect via port 25 (standard SMTP mail exchange port)
            server = smtplib.SMTP(mx_host, 25, timeout=5)
            server.helo()
            server.mail("outreach_check@gmail.com")
            code, message = server.rcpt(recipient)
            server.quit()
            # 250 means recipient exists
            return code == 250
        except Exception:
            return False

    # First, test if the server is a Catch-All
    is_catch_all = check_recipient(catchall_test_email)
    if is_catch_all:
        logger.warning(f"SMTP Verification: {domain} is a Catch-All server. Skipping SMTP checks (unsafe).")
        # If it's a catch-all, we fallback to first.last or first as a default guess
        return False
        
    # Standard check for the actual email
    return check_recipient(email_addr)

def run_lead_generation_agent(company_name: str, company_type: str = "startup") -> dict:
    """
    Runs the full lead generation flow:
    Finds recruiter -> Guesses emails -> Verifies -> Saves to DB
    """
    details = extract_recruiter_details(company_name)
    if not details or "domain" not in details or not details.get("firstName"):
        return {"success": False, "error": "Could not locate recruiter or domain details."}
        
    first = details["firstName"]
    last = details.get("lastName", "")
    domain = details["domain"]
    real_company = details.get("company", company_name)
    
    guesses = generate_email_permutations(first, last, domain)
    verified_email = None
    
    logger.info(f"AI Lead Agent: Permuted {len(guesses)} emails for {first} {last} @ {domain}")
    
    # Try verifying each email guess
    for guess in guesses:
        logger.info(f"AI Lead Agent: Checking {guess}...")
        if verify_email_smtp(guess):
            verified_email = guess
            logger.info(f"AI Lead Agent: SUCCESS! Verified email: {verified_email}")
            break
            
    # Fallback to standard first.last@company.com if SMTP failed/catchall blocked it
    if not verified_email and guesses:
        verified_email = guesses[1] if len(guesses) > 1 else guesses[0]
        logger.info(f"AI Lead Agent: Fallback to default guess: {verified_email}")
        
    # Save the new recruiter into your database
    if verified_email:
        # Check if already exists
        if recruiters_col.find_one({"email": verified_email}):
            return {"success": False, "error": f"Recruiter {verified_email} already exists in database."}
            
        from datetime import datetime
        new_recruiter = {
            "email": verified_email,
            "name": f"{first} {last}".strip(),
            "company": real_company,
            "companyType": company_type,
            "status": "new",
            "sentAt": None,
            "replied": False,
            "followupSent": False,
            "followupStage": 0,
            "opened": False,
            "clicked": False,
            "createdAt": datetime.utcnow()
        }
        recruiters_col.insert_one(new_recruiter)
        return {
            "success": True,
            "email": verified_email,
            "name": new_recruiter["name"],
            "company": real_company,
            "companyType": company_type
        }
        
    return {"success": False, "error": "Failed to determine email address."}
