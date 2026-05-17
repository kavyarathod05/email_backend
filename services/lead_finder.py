"""
Lead Finder Service: uses free search scraping and Gemini to find multiple recruiter details,
guesses their corporate emails, and verifies them via SMTP MX handshakes (detecting catch-alls).
Supports configurable email counts.
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
    Performs a free search on DuckDuckGo HTML and falls back to DuckDuckGo Lite if blocked.
    """
    # 1. Try HTML version first
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
        
        if snippets:
            return "\n".join(snippets[:15])
    except Exception as e:
        logger.warning(f"DuckDuckGo HTML search failed: {e}. Trying Lite fallback...")

    # 2. Fallback to DDG Lite POST request (extremely robust and lightweight)
    lite_url = "https://lite.duckduckgo.com/lite/"
    data = urllib.parse.urlencode({"q": query}).encode("utf-8")
    req_lite = urllib.request.Request(
        lite_url,
        data=data,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    )
    try:
        with urllib.request.urlopen(req_lite, timeout=10) as response:
            html = response.read()
        soup = BeautifulSoup(html, "html.parser")
        snippets = []
        
        # In DDG Lite, snippets are inside <td> elements with class "result-snippet"
        for result in soup.find_all("td", class_="result-snippet"):
            snippets.append(result.get_text().strip())
            
        if snippets:
            return "\n".join(snippets[:15])
    except Exception as e:
        logger.error(f"DuckDuckGo Lite search fallback also failed: {e}")
        
    return ""

def extract_multiple_recruiter_details(company_name: str, limit: int = 30) -> dict:
    """
    Uses DuckDuckGo multiplexed queries and Gemini to extract up to N unique recruiters and the corporate domain.
    """
    logger.info(f"AI Lead Agent: Harvesting up to {limit} recruiters at {company_name}")
    
    # Multiplex queries to get 30+ distinct profiles
    queries = [
        f'site:linkedin.com/in "Technical Recruiter" "{company_name}"',
        f'site:linkedin.com/in "Talent Acquisition" "{company_name}"',
        f'site:linkedin.com/in "Engineering Recruiter" "{company_name}"',
        f'site:linkedin.com/in "HR Manager" "{company_name}"'
    ]
    
    all_snippets = []
    for q in queries:
        snippets = search_duckduckgo(q)
        if snippets:
            all_snippets.append(snippets)
            
    # Simple query fallback if the strict queries fail
    if not all_snippets:
        logger.warning("All strict searches returned empty. Trying simplified keyword query...")
        simple_q = f'linkedin.com recruiter "{company_name}"'
        snippets = search_duckduckgo(simple_q)
        if snippets:
            all_snippets.append(snippets)
            
    combined_snippets = "\n---\n".join(all_snippets)
    if not combined_snippets:
        logger.warning(f"No search results found for {company_name}")
        return {}

    prompt = f"""
Based on these LinkedIn search snippets for employees at the company '{company_name}', extract a list of unique recruiters and the company's domain.

Search Snippets:
{combined_snippets}

Limit the response to a maximum of {limit} unique recruiters.
Strictly return a JSON object with these keys:
- "recruiters": A list of objects, each containing:
    - "firstName": Clean first name of the recruiter.
    - "lastName": Clean last name of the recruiter (empty string if not found).
- "domain": The corporate email domain of the company (e.g. stripe.com).
- "company": Properly formatted company name.

Do not add any markdown explanation, just return the raw JSON object.
"""
    raw_response = _gemini_generate(prompt, max_tokens=1000)
    
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
        logger.info(f"AI Lead Agent: Extracted domain: {details.get('domain')} and {len(details.get('recruiters', []))} recruiter names.")
        return details
    except Exception as e:
        logger.error(f"Failed to parse Gemini recruiter extraction: {e}. Raw response: {raw_response[:500]}...")
        return {}

def generate_email_permutations(first: str, last: str, domain: str) -> list:
    """Generates the most common corporate email address patterns."""
    first = re.sub(r"[^a-zA-Z]", "", first.lower().strip())
    last = re.sub(r"[^a-zA-Z]", "", last.lower().strip())
    domain = domain.lower().strip()
    
    if not first or not domain:
        return []
        
    guesses = []
    guesses.append(f"{first}@{domain}")
    if last:
        guesses.append(f"{first}.{last}@{domain}")
        guesses.append(f"{first}{last[0]}@{domain}")
        guesses.append(f"{first[0]}{last}@{domain}")
        guesses.append(f"{first[0]}.{last}@{domain}")
        guesses.append(f"{first}{last}@{domain}")
        guesses.append(f"{first}_{last}@{domain}")
    
    return list(dict.fromkeys(guesses))

def verify_email_smtp(email_addr: str) -> bool:
    """
    Connects to the domain's MX server to verify if the email address exists.
    """
    domain = email_addr.split("@")[1]
    try:
        mx_records = dns.resolver.resolve(domain, "MX")
        mx_host = str(sorted(mx_records, key=lambda r: r.preference)[0].exchange).rstrip(".")
    except Exception as e:
        logger.warning(f"SMTP Verification: No MX record for {domain}: {e}")
        return False
        
    catchall_test_email = f"gibberish_check_12345@{domain}"
    
    def check_recipient(recipient: str) -> bool:
        try:
            server = smtplib.SMTP(mx_host, 25, timeout=5)
            server.helo()
            server.mail("outreach_check@gmail.com")
            code, message = server.rcpt(recipient)
            server.quit()
            return code == 250
        except Exception:
            return False

    is_catch_all = check_recipient(catchall_test_email)
    if is_catch_all:
        logger.warning(f"SMTP Verification: {domain} is a Catch-All server. Skipping SMTP checks.")
        return False
        
    return check_recipient(email_addr)

def run_lead_generation_agent(company_name: str, company_type: str = "startup", limit: int = 30) -> dict:
    """
    Runs the full lead generation flow:
    Finds recruiters -> Guesses emails -> Verifies -> Saves to DB
    """
    details = extract_multiple_recruiter_details(company_name, limit)
    if not details or "domain" not in details or not details.get("recruiters"):
        return {"success": False, "error": "Could not harvest recruiters or domain details."}
        
    domain = details["domain"]
    real_company = details.get("company", company_name)
    recruiters_list = details["recruiters"]
    
    added_leads = []
    skipped_count = 0
    
    logger.info(f"AI Lead Agent: Processing email generation for {len(recruiters_list)} candidates...")
    
    for rec in recruiters_list:
        if len(added_leads) >= limit:
            break
            
        first = rec.get("firstName", "")
        last = rec.get("lastName", "")
        if not first:
            continue
            
        guesses = generate_email_permutations(first, last, domain)
        verified_email = None
        
        # SMTP verification
        for guess in guesses:
            if verify_email_smtp(guess):
                verified_email = guess
                break
                
        # Default fallback
        if not verified_email and guesses:
            verified_email = guesses[1] if len(guesses) > 1 else guesses[0]
            
        if verified_email:
            # Check for duplicates in DB
            if recruiters_col.find_one({"email": verified_email}):
                skipped_count += 1
                continue
                
            from datetime import datetime
            new_rec = {
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
            recruiters_col.insert_one(new_rec)
            added_leads.append({"name": new_rec["name"], "email": verified_email})
            logger.info(f"AI Lead Agent: SUCCESSFULLY added recruiter {new_rec['name']} ({verified_email})")

    return {
        "success": True,
        "company": real_company,
        "count_added": len(added_leads),
        "skipped": skipped_count,
        "leads": added_leads
    }
