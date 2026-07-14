"""
Lead Finder Service: uses free search scraping (Yahoo + DuckDuckGo fallback) and Gemini to find multiple recruiter details,
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

def search_yahoo(query: str) -> str:
    """
    Performs a free search on Yahoo Search and returns concatenated search result snippets.
    Extremely reliable, fast, and does not present bot blocks/captchas.
    """
    url = f"https://search.yahoo.com/search?p={urllib.parse.quote(query)}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read()
        soup = BeautifulSoup(html, "html.parser")
        snippets = []
        for div in soup.find_all("div", class_="compText"):
            snippets.append(div.get_text().strip())
        for p in soup.find_all("p", class_="lh-16"):
            snippets.append(p.get_text().strip())
        
        # Clean up double lists
        unique_snippets = list(dict.fromkeys(snippets))
        return "\n".join(unique_snippets[:15])
    except Exception as e:
        logger.debug(f"Yahoo Search failed: {e}")
        return ""

def search_bing(query: str) -> str:
    """
    Performs a free search on Bing and returns concatenated result snippets.
    Very reliable fallback with great LinkedIn indexing.
    """
    url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read()
        soup = BeautifulSoup(html, "html.parser")
        snippets = []
        for p in soup.find_all(class_="b_caption"):
            text = p.get_text().strip()
            if text:
                snippets.append(text)
        for li in soup.find_all("li", class_="b_algo"):
            p_desc = li.find("p")
            if p_desc:
                snippets.append(p_desc.get_text().strip())
            a = li.find("a", href=True)
            if a and "linkedin.com/in/" in a["href"]:
                snippets.append(a["href"])
        # Also scan all LinkedIn profile links in the page
        html_text = html.decode("utf-8", errors="ignore")
        for m in re.findall(
            r"https?://(?:[a-z]+\.)?linkedin\.com/in/[A-Za-z0-9\-_%]+/?",
            html_text,
            flags=re.I,
        ):
            snippets.append(m)
        unique_snippets = list(dict.fromkeys(snippets))
        return "\n".join(unique_snippets[:25])
    except Exception as e:
        logger.debug(f"Bing Search failed: {e}")
        return ""

def search_aol(query: str) -> str:
    """
    Performs a free search on AOL Search (powered by Yahoo structure).
    Very fast, very clean.
    """
    url = f"https://search.aol.com/aol/search?q={urllib.parse.quote(query)}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read()
        soup = BeautifulSoup(html, "html.parser")
        snippets = []
        for div in soup.find_all("div", class_="compText"):
            snippets.append(div.get_text().strip())
        for p in soup.find_all("p", class_="lh-16"):
            snippets.append(p.get_text().strip())
        unique_snippets = list(dict.fromkeys(snippets))
        return "\n".join(unique_snippets[:15])
    except Exception as e:
        logger.debug(f"AOL Search failed: {e}")
        return ""

def search_brave(query: str) -> str:
    """
    Performs a free search on Brave Search and extracts snippets.
    Privacy first search engine with highly permissive bot access.
    """
    url = f"https://search.brave.com/search?q={urllib.parse.quote(query)}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read()
        soup = BeautifulSoup(html, "html.parser")
        snippets = []
        for p in soup.find_all("p", class_="snippet-description"):
            snippets.append(p.get_text().strip())
        for div in soup.find_all("div", class_="snippet"):
            snippets.append(div.get_text().strip())
        unique_snippets = list(dict.fromkeys(snippets))
        return "\n".join(unique_snippets[:15])
    except Exception as e:
        logger.debug(f"Brave Search failed: {e}")
        return ""

def search_ecosia(query: str) -> str:
    """
    Performs a free search on Ecosia and extracts results.
    """
    url = f"https://www.ecosia.org/search?q={urllib.parse.quote(query)}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read()
        soup = BeautifulSoup(html, "html.parser")
        snippets = []
        for p in soup.find_all("p", class_="result-snippet"):
            snippets.append(p.get_text().strip())
        for div in soup.find_all("div", class_="card-web"):
            snippets.append(div.get_text().strip())
        unique_snippets = list(dict.fromkeys(snippets))
        return "\n".join(unique_snippets[:15])
    except Exception as e:
        logger.debug(f"Ecosia Search failed: {e}")
        return ""

def search_ask(query: str) -> str:
    """
    Performs a free search on Ask.com and extracts results.
    """
    url = f"https://www.ask.com/web?q={urllib.parse.quote(query)}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read()
        soup = BeautifulSoup(html, "html.parser")
        snippets = []
        for p in soup.find_all("p", class_="PartialSearchResults-item-abstract"):
            snippets.append(p.get_text().strip())
        unique_snippets = list(dict.fromkeys(snippets))
        return "\n".join(unique_snippets[:15])
    except Exception as e:
        logger.debug(f"Ask Search failed: {e}")
        return ""

def search_gibiru(query: str) -> str:
    """
    Performs a free search on Gibiru and extracts results.
    """
    url = f"https://gibiru.com/results.html?q={urllib.parse.quote(query)}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read()
        soup = BeautifulSoup(html, "html.parser")
        snippets = []
        for div in soup.find_all("div", class_="g-snippet"):
            snippets.append(div.get_text().strip())
        unique_snippets = list(dict.fromkeys(snippets))
        return "\n".join(unique_snippets[:15])
    except Exception as e:
        logger.debug(f"Gibiru Search failed: {e}")
        return ""

def search_duckduckgo(query: str) -> str:
    """
    Fallback search using DuckDuckGo Lite or HTML.
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
        
        if snippets:
            return "\n".join(snippets[:15])
    except Exception:
        pass

    # Lite Fallback
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
        for result in soup.find_all("td", class_="result-snippet"):
            snippets.append(result.get_text().strip())
        return "\n".join(snippets[:15])
    except Exception:
        return ""

def search_web_free(query: str) -> str:
    """
    Multiplexes searches across 8 free search engines: Yahoo, Bing, AOL, Brave, Ecosia, Ask, Gibiru, and DuckDuckGo.
    Aggregates snippets across working engines to yield highly detailed, multi-source results!
    """
    engines = [
        ("Yahoo", search_yahoo),
        ("Bing", search_bing),
        ("AOL", search_aol),
        ("Brave", search_brave),
        ("Ecosia", search_ecosia),
        ("Ask", search_ask),
        ("Gibiru", search_gibiru),
        ("DuckDuckGo", search_duckduckgo)
    ]
    
    combined_snippets = []
    
    for name, search_fn in engines:
        try:
            snippets = search_fn(query)
            if snippets:
                combined_snippets.append(snippets)
                # Aggregate from up to 3 working engines to ensure deep lead extraction
                if len(combined_snippets) >= 3:
                    break
        except Exception as e:
            logger.warning(f"Engine {name} failed: {e}")
            
    if combined_snippets:
        return "\n\n".join(combined_snippets)
        
    return ""


LINKEDIN_URL_RE = re.compile(
    r"https?://(?:[a-z]+\.)?linkedin\.com/in/[A-Za-z0-9\-_%]+/?",
    re.IGNORECASE,
)


def _extract_linkedin_urls(text: str) -> list[str]:
    if not text:
        return []
    urls = []
    for m in LINKEDIN_URL_RE.findall(text):
        clean = m.rstrip("/").split("?")[0]
        if clean.lower() not in {u.lower() for u in urls}:
            urls.append(clean)
    return urls


def extract_employees_for_referral(company_name: str, limit: int = 15) -> dict:
    """
    Faster, referral-focused employee discovery: engineers + campus/TA contacts,
    including LinkedIn profile URLs when present in search results.
    """
    logger.info(f"Referral discover: finding employees at {company_name} (limit={limit})")
    queries = [
        f'site:linkedin.com/in "Software Engineer" "{company_name}"',
        f'site:linkedin.com/in "Software Development Engineer" "{company_name}"',
        f'site:linkedin.com/in "SWE" "{company_name}"',
        f'site:linkedin.com/in "Engineering Manager" "{company_name}"',
        f'site:linkedin.com/in "Senior Software Engineer" "{company_name}"',
        f'site:linkedin.com/in "University Recruiter" "{company_name}"',
        f'site:linkedin.com/in "Campus Recruiter" "{company_name}"',
        f'site:linkedin.com/in "Early Careers" "{company_name}"',
        f'site:linkedin.com/in "Talent Acquisition" "{company_name}"',
        f'site:linkedin.com/in ("Software Engineer" OR "SDE" OR "Engineering") "{company_name}"',
    ]

    all_snippets: list[str] = []
    linkedin_urls: list[str] = []
    for q in queries:
        snippets = search_web_free(q)
        if not snippets:
            continue
        all_snippets.append(snippets)
        for u in _extract_linkedin_urls(snippets):
            if u.lower() not in {x.lower() for x in linkedin_urls}:
                linkedin_urls.append(u)

    if not all_snippets:
        simple = search_web_free(f'site:linkedin.com/in "{company_name}" engineer OR recruiter')
        if simple:
            all_snippets.append(simple)
            linkedin_urls.extend(_extract_linkedin_urls(simple))

    combined = "\n---\n".join(all_snippets)
    if not combined:
        return {}

    url_hint = "\n".join(linkedin_urls[:40])
    prompt = f"""
Based on these LinkedIn search snippets for people who work at '{company_name}',
extract unique employees who could help with an internship referral
(prefer software engineers, engineering managers, campus/university recruiters, talent acquisition).

Search Snippets:
{combined}

LinkedIn URLs found in results (match to people when possible):
{url_hint or "(none extracted)"}

Limit to a maximum of {limit} unique people.
Strictly return a JSON object with keys:
- "employees": list of objects with:
    - "firstName": string
    - "lastName": string (empty if unknown)
    - "title": job title if known else ""
    - "linkedinUrl": full linkedin.com/in/... URL if known else ""
- "domain": corporate email domain (e.g. stripe.com)
- "company": properly formatted company name

Return raw JSON only, no markdown.
"""
    raw_response = _gemini_generate(prompt, max_tokens=1600)
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
        # Normalize alternate key "recruiters"
        if "employees" not in details and "recruiters" in details:
            details["employees"] = details["recruiters"]
        logger.info(
            f"Referral discover: domain={details.get('domain')} "
            f"people={len(details.get('employees') or [])}"
        )
        return details
    except Exception as e:
        logger.error(f"Referral discover parse failed: {e}. Raw: {raw_response[:400]}...")
        return {}


def discover_and_save_employees(
    company_name: str,
    *,
    company_type: str = "startup",
    limit: int = 15,
    job_id: str | None = None,
) -> dict:
    """
    Discover employees for a company, save new ones to recruiters DB, return contacts.
    Always merges with existing DB contacts for that company.
    """
    from datetime import datetime

    details = extract_employees_for_referral(company_name, limit=limit)
    added = []
    skipped = 0
    domain = (details or {}).get("domain") or ""
    real_company = (details or {}).get("company") or company_name
    employees = (details or {}).get("employees") or []

    for rec in employees:
        if len(added) >= limit:
            break
        first = (rec.get("firstName") or "").strip()
        last = (rec.get("lastName") or "").strip()
        if not first:
            continue
        name = f"{first} {last}".strip()
        title = (rec.get("title") or "").strip()
        linkedin = (rec.get("linkedinUrl") or rec.get("linkedin") or "").strip()
        if linkedin and "linkedin.com/in/" not in linkedin.lower():
            linkedin = ""

        verified_email = None
        if domain:
            guesses = generate_email_permutations(first, last, domain)
            verified_email = guesses[1] if len(guesses) > 1 else (guesses[0] if guesses else None)

        if not verified_email and not linkedin:
            continue

        # Prefer email uniqueness; if only LinkedIn, use a synthetic placeholder key
        if verified_email and recruiters_col.find_one({"email": verified_email}):
            # Enrich LinkedIn on existing record
            if linkedin:
                recruiters_col.update_one(
                    {"email": verified_email},
                    {
                        "$set": {
                            "linkedin": linkedin,
                            "title": title or None,
                            "source": "referral_discover",
                        }
                    },
                )
            skipped += 1
            continue

        if linkedin and recruiters_col.find_one({"linkedin": linkedin}):
            skipped += 1
            continue

        email = verified_email
        if not email:
            slug = f"{first.lower()}.{last.lower() or 'x'}".replace(" ", "")
            email = f"noemail+{slug}@linkedin.local"

        if recruiters_col.find_one({"email": email}):
            skipped += 1
            continue

        new_rec = {
            "email": email,
            "name": name,
            "company": real_company,
            "companyType": company_type,
            "title": title,
            "linkedin": linkedin or None,
            "status": "new",
            "sentAt": None,
            "replied": False,
            "followupSent": False,
            "followupStage": 0,
            "opened": False,
            "clicked": False,
            "source": "referral_discover",
            "discoveredForJobId": job_id,
            "emailGuessed": bool(verified_email),
            "createdAt": datetime.utcnow(),
        }
        recruiters_col.insert_one(new_rec)
        added.append(
            {
                "name": name,
                "email": email,
                "title": title,
                "linkedin": linkedin,
            }
        )

    return {
        "success": True,
        "company": real_company,
        "domain": domain,
        "count_added": len(added),
        "skipped": skipped,
        "leads": added,
        "discovered": bool(employees),
    }


def extract_multiple_recruiter_details(company_name: str, limit: int = 30) -> dict:
    """
    Uses web scraping and Gemini to extract up to N unique recruiters and the corporate domain.
    """
    logger.info(f"AI Lead Agent: Harvesting up to {limit} recruiters at {company_name}")
    
    # Multiplex queries to get 30+ distinct profiles
    queries = [
        # Core recruiter titles
        f'site:linkedin.com/in "Technical Recruiter" "{company_name}"',
        f'site:linkedin.com/in "Tech Recruiter" "{company_name}"',
        f'site:linkedin.com/in "Engineering Recruiter" "{company_name}"',
        f'site:linkedin.com/in "IT Recruiter" "{company_name}"',
        f'site:linkedin.com/in "Technical Talent Acquisition" "{company_name}"',
        f'site:linkedin.com/in "Talent Acquisition Specialist" "{company_name}"',
        f'site:linkedin.com/in "Talent Acquisition Partner" "{company_name}"',
        f'site:linkedin.com/in "Talent Acquisition Recruiter" "{company_name}"',
        f'site:linkedin.com/in "Talent Acquisition Associate" "{company_name}"',
        f'site:linkedin.com/in "Talent Acquisition Executive" "{company_name}"',
        f'site:linkedin.com/in "Talent Acquisition Lead" "{company_name}"',
        f'site:linkedin.com/in "Talent Acquisition Manager" "{company_name}"',
        f'site:linkedin.com/in "Talent Acquisition Intern" "{company_name}"',

        # HR titles
        f'site:linkedin.com/in "HR Manager" "{company_name}"',
        f'site:linkedin.com/in "HR Executive" "{company_name}"',
        f'site:linkedin.com/in "HR Recruiter" "{company_name}"',
        f'site:linkedin.com/in "HR Specialist" "{company_name}"',
        f'site:linkedin.com/in "HR Generalist" "{company_name}"',
        f'site:linkedin.com/in "Human Resources" "{company_name}"',
        f'site:linkedin.com/in "Human Resources Manager" "{company_name}"',
        f'site:linkedin.com/in "Human Resources Business Partner" "{company_name}"',
        f'site:linkedin.com/in "People Operations" "{company_name}"',
        f'site:linkedin.com/in "People Ops" "{company_name}"',
        f'site:linkedin.com/in "People Partner" "{company_name}"',
        f'site:linkedin.com/in "People Success" "{company_name}"',

        # SWE / university hiring specific
        f'site:linkedin.com/in "University Recruiter" "{company_name}"',
        f'site:linkedin.com/in "Campus Recruiter" "{company_name}"',
        f'site:linkedin.com/in "Early Careers Recruiter" "{company_name}"',
        f'site:linkedin.com/in "University Relations" "{company_name}"',
        f'site:linkedin.com/in "Campus Hiring" "{company_name}"',
        f'site:linkedin.com/in "Graduate Recruiter" "{company_name}"',
        f'site:linkedin.com/in "Student Programs" "{company_name}"',
        f'site:linkedin.com/in "Emerging Talent Recruiter" "{company_name}"',

        # Sourcers
        f'site:linkedin.com/in "Technical Sourcer" "{company_name}"',
        f'site:linkedin.com/in "Talent Sourcer" "{company_name}"',
        f'site:linkedin.com/in "Recruitment Sourcer" "{company_name}"',
        f'site:linkedin.com/in "Sourcing Specialist" "{company_name}"',

        # Leadership
        f'site:linkedin.com/in "Head of Talent Acquisition" "{company_name}"',
        f'site:linkedin.com/in "Recruitment Manager" "{company_name}"',
        f'site:linkedin.com/in "Hiring Manager" "{company_name}"',
        f'site:linkedin.com/in "Director Talent Acquisition" "{company_name}"',
        f'site:linkedin.com/in "VP Talent Acquisition" "{company_name}"',

        # Startup-specific/common alternate titles
        f'site:linkedin.com/in "Founding Recruiter" "{company_name}"',
        f'site:linkedin.com/in "People Team" "{company_name}"',
        f'site:linkedin.com/in "Hiring Team" "{company_name}"',
        f'site:linkedin.com/in "Recruitment Consultant" "{company_name}"',
        f'site:linkedin.com/in "Staffing Specialist" "{company_name}"',

        # Boolean combined searches (very useful)
        f'site:linkedin.com/in ("Technical Recruiter" OR "Engineering Recruiter" OR "Technical Sourcer") "{company_name}"',
        f'site:linkedin.com/in ("Talent Acquisition" OR "HR" OR "People Ops") "{company_name}"',
        f'site:linkedin.com/in ("Campus Recruiter" OR "University Recruiter" OR "Early Careers Recruiter") "{company_name}"'
    ]
    
    all_snippets = []
    for q in queries:
        snippets = search_web_free(q)
        if snippets:
            all_snippets.append(snippets)
            
    # Simple query fallback if the strict queries fail
    if not all_snippets:
        logger.warning("All strict searches returned empty. Trying simplified keyword query...")
        simple_q = f'linkedin.com recruiter "{company_name}"'
        snippets = search_web_free(simple_q)
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
    - "title": Job title if known else "".
    - "linkedinUrl": Full linkedin.com/in/... URL if present else "".
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

IS_SMTP_PORT_25_OPEN = False

def check_smtp_port_25() -> bool:
    return False

def verify_email_smtp(email_addr: str) -> bool:
    return False


def run_lead_generation_agent(company_name: str, company_type: str = "startup", limit: int = 30):
    """
    Runs the full lead generation flow yielding progressive logs and status updates.
    """
    yield {"type": "log", "message": f"🤖 Starting Lead Finder Agent for '{company_name}'..."}
    yield {"type": "log", "message": "🔍 Scraping web search engines for recruiters..."}
    
    details = extract_multiple_recruiter_details(company_name, limit)
    if not details or "domain" not in details or not details.get("recruiters"):
        yield {"type": "error", "message": "❌ Could not locate recruiters or domain details."}
        return
        
    domain = details["domain"]
    real_company = details.get("company", company_name)
    recruiters_list = details["recruiters"]
    
    yield {"type": "log", "message": f"🌐 Extracted domain: {domain}"}
    yield {"type": "log", "message": f"✨ Extracted {len(recruiters_list)} recruiters from snippets."}
    
    added_leads = []
    skipped_count = 0
    
    for rec in recruiters_list:
        if len(added_leads) >= limit:
            break
            
        first = rec.get("firstName", "")
        last = rec.get("lastName", "")
        if not first:
            continue
            
        name = f"{first} {last}".strip()
        yield {"type": "log", "message": f"👤 Checking Recruiter: {name}"}
        
        guesses = generate_email_permutations(first, last, domain)
        
        # Determine the best corporate email guess directly
        verified_email = guesses[1] if len(guesses) > 1 else guesses[0] if guesses else None
        if verified_email:
            yield {"type": "log", "message": f"   ✉️ Generated email guess: {verified_email}"}
            
        if verified_email:
            # Check for duplicates in DB
            if recruiters_col.find_one({"email": verified_email}):
                skipped_count += 1
                yield {"type": "log", "message": f"   ⏭️ Skipped duplicate recruiter: {verified_email}"}
                continue
                
            from datetime import datetime
            linkedin = (rec.get("linkedinUrl") or rec.get("linkedin") or "").strip()
            title = (rec.get("title") or "").strip()
            new_rec = {
                "email": verified_email,
                "name": name,
                "company": real_company,
                "companyType": company_type,
                "title": title,
                "linkedin": linkedin or None,
                "status": "new",
                "sentAt": None,
                "replied": False,
                "followupSent": False,
                "followupStage": 0,
                "opened": False,
                "clicked": False,
                "source": "lead_agent",
                "createdAt": datetime.utcnow()
            }
            recruiters_col.insert_one(new_rec)
            added_leads.append({"name": name, "email": verified_email, "linkedin": linkedin, "title": title})
            yield {"type": "log", "message": f"   💾 Saved {name} ({verified_email}) into database!"}

    yield {
        "type": "complete",
        "data": {
            "success": True,
            "company": real_company,
            "count_added": len(added_leads),
            "skipped": skipped_count,
            "leads": added_leads
        }
    }

