# AI Personalization Engine ΓÇö Technical Documentation

## Table of Contents

1. [Overview](#1-overview)
2. [System Architecture](#2-system-architecture)
3. [Lead Enrichment Pipeline](#3-lead-enrichment-pipeline)
4. [Hugging Face AI Integration](#4-hugging-face-ai-integration)
5. [AI Content Generation Functions](#5-ai-content-generation-functions)
6. [Email Rendering with AI Content](#6-email-rendering-with-ai-content)
7. [Subject Line A/B Testing](#7-subject-line-ab-testing)
8. [Engagement Tracking (Cold / Warm / Hot)](#8-engagement-tracking-cold--warm--hot)
9. [Behavioral Follow-up Automation](#9-behavioral-follow-up-automation)
10. [In-Memory Caching Strategy](#10-in-memory-caching-strategy)
11. [Environment Variables](#11-environment-variables)
12. [End-to-End Example](#12-end-to-end-example)

---

## 1. Overview

The Personalization Engine sits **between lead ingestion and email sending**. Its job is to take raw lead data (an email address + company name) and produce a fully personalized email that feels hand-crafted ΓÇö not templated.

**Core Pipeline:**

```
Lead Added ΓåÆ Enrichment ΓåÆ AI Generation ΓåÆ Template Rendering ΓåÆ Email Sent ΓåÆ Tracking ΓåÆ Follow-up
```

Everything runs inside `app.py` (Python/FastAPI). There is **no separate microservice** ΓÇö the AI calls go directly to the Hugging Face free Inference API over HTTPS.

---

## 2. System Architecture

```
ΓöîΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÉ
Γöé                        app.py (FastAPI)                         Γöé
Γö£ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöñ
Γöé                                                                 Γöé
Γöé  ΓöîΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÉ    ΓöîΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÉ    ΓöîΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÉ  Γöé
Γöé  Γöé Lead IngestionΓöéΓöÇΓöÇΓöÇΓû╕Γöé Lead Enrichment   ΓöéΓöÇΓöÇΓöÇΓû╕Γöé MongoDB Save Γöé  Γöé
Γöé  Γöé (POST /recr.) Γöé    Γöé extract_first_nameΓöé    Γöé              Γöé  Γöé
Γöé  Γöé               Γöé    Γöé normalize_company Γöé    Γöé              Γöé  Γöé
Γöé  ΓööΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÿ    ΓööΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÿ    ΓööΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÿ  Γöé
Γöé                                                                 Γöé
Γöé  ΓöîΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÉ    ΓöîΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÉ    ΓöîΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÉ  Γöé
Γöé  Γöé Send Email   ΓöéΓöÇΓöÇΓöÇΓû╕Γöé AI PersonalizationΓöéΓöÇΓöÇΓöÇΓû╕Γöé build_email  Γöé  Γöé
Γöé  Γöé (POST /send) Γöé    Γöé _hf_generate()    Γöé    Γöé HTML render  Γöé  Γöé
Γöé  Γöé              Γöé    Γöé company_sentence   Γöé    Γöé              Γöé  Γöé
Γöé  Γöé              Γöé    Γöé opening_line       Γöé    Γöé              Γöé  Γöé
Γöé  Γöé              Γöé    Γöé subject_lines      Γöé    Γöé              Γöé  Γöé
Γöé  ΓööΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÿ    ΓööΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÿ    ΓööΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÿ  Γöé
Γöé           Γöé                    Γöé                                 Γöé
Γöé           Γöé           ΓöîΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓö┤ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÉ                        Γöé
Γöé           Γöé           Γöé Hugging Face   Γöé                        Γöé
Γöé           Γöé           Γöé Free API       Γöé                        Γöé
Γöé           Γöé           Γöé (Qwen 32B)     Γöé                        Γöé
Γöé           Γöé           ΓööΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÿ                        Γöé
Γöé           Γû╝                                                     Γöé
Γöé  ΓöîΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÉ   Γöé
Γöé  Γöé Tracking: open pixel + click redirect + reply checker    Γöé   Γöé
Γöé  Γöé Engagement: Cold ΓåÆ Warm ΓåÆ Hot                            Γöé   Γöé
Γöé  Γöé Follow-up: Behavioral branching based on signals         Γöé   Γöé
Γöé  ΓööΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÿ   Γöé
ΓööΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÿ
```

---

## 3. Lead Enrichment Pipeline

When a lead enters the system (via `POST /recruiters`, CSV import, or text import), it goes through two enrichment steps **before** being saved to the database.

### 3.1 First Name Extraction ΓÇö `extract_first_name(email)`

**Purpose:** Derive a human first name from an email address so the greeting says "Hi John" instead of "Hi there".

**Algorithm (step by step):**

```python
def extract_first_name(email_addr: str) -> str:
```

| Step | Action | Example |
|------|--------|---------|
| 1 | Validate: check for `@` symbol | `john.smith@stripe.com` ΓåÆ valid |
| 2 | Extract local part (before `@`) | `john.smith` |
| 3 | Replace `.` `_` `-` with spaces | `john smith` |
| 4 | Split into tokens | `["john", "smith"]` |
| 5 | Take the first token | `john` |
| 6 | Capitalize | `John` |

**Edge Cases:**

| Scenario | Input | Logic | Output |
|----------|-------|-------|--------|
| Normal email | `john.smith@stripe.com` | Split on `.`, take first | `John` |
| Underscore separator | `jane_doe@google.com` | Split on `_`, take first | `Jane` |
| Dash separator | `bob-jones@meta.com` | Split on `-`, take first | `Bob` |
| No separator, long | `johndoe12@company.com` | No separator detected, token length > 7, take first 5 chars | `Johnd` |
| Short, no separator | `hi@x.com` | Single short token, capitalize | `Hi` |
| Empty/invalid | `""` or no `@` | Fallback | `there` |

**Why first 5 characters for no-separator emails?**
If the email is `alexandersmith@company.com`, there's no separator to split on. Taking the first 5 characters (`Alexa`) gives a reasonable approximation. The user specified "4ΓÇô6 characters" ΓÇö 5 is the middle ground.

### 3.2 Company Normalization ΓÇö `normalize_company(name)`

**Purpose:** Ensure consistent company names regardless of input formatting.

```python
def normalize_company(company_name: str) -> str:
    if not company_name:
        return ""
    return company_name.strip().title()
```

| Input | Output | Transformation |
|-------|--------|---------------|
| `"stripe"` | `"Stripe"` | Capitalize first letter |
| `"  google  "` | `"Google"` | Strip whitespace + capitalize |
| `"META"` | `"Meta"` | `.title()` lowercases then capitalizes first letter |
| `""` | `""` | Empty passthrough |

### 3.3 Where Enrichment Runs

Enrichment is applied in **three places** ΓÇö every entry point for leads:

1. **`POST /recruiters`** ΓÇö single recruiter add
2. **`POST /recruiters/import-csv`** ΓÇö file upload
3. **`POST /recruiters/import-text`** ΓÇö pasted CSV text

In each case:
```python
# If no name was provided in the CSV/form, derive it from email
name = norm_row.get("name", "")
if not name:
    name = extract_first_name(email_addr)

# Always normalize company
company = normalize_company(norm_row.get("company", ""))
```

---

## 4. Hugging Face AI Integration

### 4.1 Why Hugging Face?

- **Free tier** ΓÇö no credit card required
- **No separate server** ΓÇö just an HTTPS API call
- **Good models** ΓÇö `Qwen/Qwen2.5-Coder-32B-Instruct` is a 32-billion parameter model

### 4.2 API Configuration

```python
HF_API_KEY = os.getenv("HF_API_KEY", "")
HF_MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct"
HF_API_URL = "https://router.huggingface.co/v1/chat/completions"
```

- **`HF_API_KEY`** ΓÇö your free Hugging Face token (get it from https://huggingface.co/settings/tokens)
- **`HF_MODEL`** ΓÇö the model to use (Qwen 32B is free and capable)
- **`HF_API_URL`** ΓÇö the OpenAI-compatible chat/completions endpoint hosted by Hugging Face

### 4.3 The Core Generation Function ΓÇö `_hf_generate(prompt, max_tokens)`

This is the single function that all AI features call:

```python
def _hf_generate(prompt: str, max_tokens: int = 60) -> str:
    resp = requests.post(
        HF_API_URL,
        headers={
            "Authorization": f"Bearer {HF_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": HF_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.7
        },
        timeout=20
    )
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()
```

**How it works:**

| Parameter | Value | Why |
|-----------|-------|-----|
| `model` | `Qwen/Qwen2.5-Coder-32B-Instruct` | Instruction-tuned, follows prompts well |
| `messages` | `[{"role": "user", "content": prompt}]` | OpenAI-compatible chat format |
| `max_tokens` | 60 (default) | Keeps output short (1-2 sentences) |
| `temperature` | 0.7 | Adds slight creativity without being random |
| `timeout` | 20s | Prevents hanging if HF is slow |

**Error Handling:**
- If `HF_API_KEY` is empty ΓåÆ returns `""` (skips AI, email still sends)
- If API returns non-200 ΓåÆ logs warning, returns `""` (graceful degradation)
- If request times out ΓåÆ logs error, returns `""` (email sends without AI content)

**Key Design Decision:** The system **never blocks email sending** if AI fails. All AI content is optional enhancement.

---

## 5. AI Content Generation Functions

### 5.1 Company Sentence ΓÇö `generate_company_sentence(company)`

**Purpose:** Generate one engineering-focused sentence about the company.

**Prompt Engineering:**
```
Write one sentence (under 20 words) about {company} that is specific and
engineering-focused. Mention the company name. Reference engineering,
technology, scale, or product impact. Avoid generic phrases like
"great company". Output only the sentence.
```

**Why this prompt works:**
- `"under 20 words"` ΓÇö constrains length
- `"engineering-focused"` ΓÇö matches the candidate profile
- `"Avoid generic phrases"` ΓÇö prevents bland output
- `"Output only the sentence"` ΓÇö prevents preamble like "Here's a sentence..."

**Example Output:**
```
Stripe processes billions of transactions annually, powering global commerce infrastructure at massive scale.
```

### 5.2 Opening Line ΓÇö `generate_opening_line(company)`

**Purpose:** Create a personalized first sentence that connects the candidate to the company.

**Prompt Engineering:**
```
Write one short opening line (max 20 words) for a cold email to a recruiter
at {company}. I am a backend engineer interested in scalable systems and AI.
Reference {company}'s engineering scale or backend challenges. Natural,
professional tone. Output only the sentence.
```

**Why this prompt works:**
- Provides **candidate context** (backend, scalable systems, AI)
- Asks for **company-specific** reference
- `"Natural, professional tone"` ΓÇö avoids marketing speak
- `"max 20 words"` ΓÇö keeps it punchy

**Example Output:**
```
I'd love to explore potential opportunities at Google and contribute to backend challenges at scale.
```

### 5.3 Subject Lines ΓÇö `generate_subject_lines(company)`

**Purpose:** Generate 5 subject line options for A/B testing.

**Prompt Engineering:**
```
Generate exactly 5 short email subject lines for a Summer 2026 Backend
Intern application at {company}. Rules: max 6 words each, professional,
curiosity-driven. Output only the 5 lines, one per line, no numbering,
no extra text.
```

**Post-processing Logic:**
```python
raw = _hf_generate(prompt, max_tokens=120)
lines = [l.strip().lstrip("0123456789.-*) ") for l in raw.split("\n") if l.strip()]
lines = [l for l in lines if 0 < len(l) < 80][:5]
```

| Step | Logic | Why |
|------|-------|-----|
| Split by newline | `raw.split("\n")` | Each subject on its own line |
| Strip numbering | `lstrip("0123456789.-*) ")` | Models sometimes add `1.` or `- ` |
| Filter empty/long | `0 < len(l) < 80` | Remove blanks and overly long lines |
| Take first 5 | `[:5]` | Cap at 5 subjects |

**Fallback Mechanism:**
```python
if len(lines) < 3:
    return [
        "Summer 2026 Backend Intern",
        f"Backend Intern ΓÇö {company}",
        "Quick Question About Internships",
        f"Engineer Interested in {company}",
        "Internship Opportunity Inquiry",
    ]
```

If the AI returns garbled output (fewer than 3 usable lines), the system falls back to static, proven subject lines. **This ensures emails always have valid subjects.**

---

## 6. Email Rendering with AI Content

### How `build_email()` Uses AI Content

```python
company_sentence = generate_company_sentence(company)  # cached
opening_line = generate_opening_line(company)           # fresh each time

html_body = html_template.format(
    name=name,
    company=company,
    company_sentence=company_sentence,
    opening_line=opening_line,
    resume_url=resume_url,
    resume_link=resume_html
)
```

### Template Placeholders

Your email templates can use these variables:

| Placeholder | Source | Example |
|-------------|--------|---------|
| `{name}` | `extract_first_name()` or CSV | `John` |
| `{company}` | `normalize_company()` | `Stripe` |
| `{company_sentence}` | AI generated | `Stripe processes billions...` |
| `{opening_line}` | AI generated | `I'd love to contribute...` |
| `{resume_link}` | Clickable HTML link | `<a href="...">Resume</a>` |
| `{resume_url}` | Raw URL | `https://drive.google.com/...` |

### Fallback Rendering

If the template uses a placeholder that doesn't exist, the system uses string replacement as a fallback:

```python
except KeyError as e:
    # Fallback: simple string replace instead of format()
    html_body = html_template.replace("{name}", name)
                             .replace("{company}", company)
                             .replace("{company_sentence}", company_sentence)
                             .replace("{opening_line}", opening_line)
```

---

## 7. Subject Line A/B Testing

### How Rotation Works

In `send_one_email()`:

```python
ai_subjects = generate_subject_lines(company)  # ["Subject A", "Subject B", ...]

total_sent_company = recruiters_col.count_documents({"company": company, "status": "sent"})
chosen_subject = ai_subjects[total_sent_company % len(ai_subjects)]
email_data["Subject"] = chosen_subject
```

**Logic:**
1. Generate 5 subject lines for the company
2. Count how many emails have already been sent to this company
3. Use modulo (`%`) to rotate through the subjects

**Example for Google:**

| Email # | Calculation | Subject Used |
|---------|-------------|-------------|
| 1st | `0 % 5 = 0` | `Summer 2026 Backend Intern` |
| 2nd | `1 % 5 = 1` | `Backend Intern ΓÇö Google` |
| 3rd | `2 % 5 = 2` | `Quick Question About Internships` |
| 4th | `3 % 5 = 3` | `Engineer Interested in Google` |
| 5th | `4 % 5 = 4` | `Internship Opportunity Inquiry` |
| 6th | `5 % 5 = 0` | (cycles back to first) |

The `subjectUsed` field is saved in MongoDB so you can track which subjects get the most opens/replies.

---

## 8. Engagement Tracking (Cold / Warm / Hot)

### Three Engagement States

| State | Condition | Meaning |
|-------|-----------|---------|
| **Cold** | `opened: false` | Email sent but never opened |
| **Warm** | `opened: true, clicked: false` | Opened but didn't click resume |
| **Hot** | `clicked: true` | Clicked the resume link |

### How Tracking Works

**Open Tracking** ΓÇö invisible 1├ù1 pixel image:
```html
<img src="https://yourserver.com/track/open/john@stripe.com" width="1" height="1" />
```
When the email client loads images, it requests this URL ΓåÆ the server marks `opened: true`.

**Click Tracking** ΓÇö redirect URL:
```
Original: https://drive.google.com/resume
Tracked:  https://yourserver.com/track/click/john@stripe.com?url=https%3A%2F%2Fdrive.google.com%2Fresume
```
When clicked, the server marks `clicked: true` then redirects to the actual resume.

**Reply Tracking** ΓÇö IMAP inbox check:
The `/check-replies` endpoint connects to Gmail via IMAP, reads unread emails, and matches sender addresses against the database.

---

## 9. Behavioral Follow-up Automation

### Scenario-Based Triggers

The follow-up system checks `send_followup_if_due()` and uses different **timing** and **tone** based on engagement:

```python
query = {
    "status": "sent",
    "replied": False,
    "$or": [
        {   # HOT: Resume clicked but no reply ΓåÆ follow up in 36 hours
            "clicked": True,
            "followupStage": {"$in": [0, None]},
            "sentAt": {"$lte": now - timedelta(hours=36)}
        },
        {   # WARM: Opened but no click ΓåÆ follow up in 3 days
            "opened": True, "clicked": False,
            "followupStage": {"$in": [0, None]},
            "sentAt": {"$lte": now - timedelta(days=3)}
        },
        {   # COLD: Not opened ΓåÆ resend with new subject in 4 days
            "opened": False,
            "followupStage": {"$in": [0, None]},
            "sentAt": {"$lte": now - timedelta(days=4)}
        },
        {   # BREAKUP: Stage 1 follow-up sent, 6 days later send breakup
            "followupStage": 1,
            "followupAt": {"$lte": now - timedelta(days=6)}
        }
    ]
}
```

### Follow-up Content by Scenario

| Scenario | Trigger | Subject | Tone |
|----------|---------|---------|------|
| **Hot** (clicked) | 36 hours | `Glad you saw my resume \| Kavya @ {company}` | Direct ΓÇö "I noticed you viewed my resume" |
| **Warm** (opened) | 3 days | `Quick question about {company} internship` | Light ΓÇö "Just checking in..." |
| **Cold** (not opened) | 4 days | `Quick question about internships` | Resend with **new subject line** |
| **Breakup** (stage 2) | 6 days after follow-up | `Wrapping up \| Summer '26 Intern @{company}` | Final ΓÇö "I won't reach out again" |

### Why Different Timing?

- **Clicked (Hot):** They showed strong interest by viewing your resume. Strike while the iron is hot ΓÇö 24-48 hours (we use 36 as the midpoint).
- **Opened (Warm):** They read your email but weren't convinced enough to click. Give them 3 days before a gentle nudge.
- **Not Opened (Cold):** They likely missed it or the subject didn't catch attention. Wait 4 days and **resend with a completely different subject line** (essentially a fresh attempt).

---

## 10. In-Memory Caching Strategy

```python
_company_sentence_cache: dict = {}

def generate_company_sentence(company: str) -> str:
    if company in _company_sentence_cache:
        return _company_sentence_cache[company]   # cache HIT
    
    result = _hf_generate(prompt)                  # API call
    
    if result:
        _company_sentence_cache[company] = result  # save for reuse
    return result
```

**Why cache company sentences?**
- If you're emailing 10 recruiters at Google, the sentence about Google's engineering is the same for all 10.
- Without caching: 10 API calls ├ù ~2 seconds = 20 seconds wasted.
- With caching: 1 API call + 9 instant lookups.

**Why NOT cache opening lines?**
- Opening lines can vary slightly per recruiter even at the same company (adds natural variation).

**Why in-memory (dict) instead of Redis/Database?**
- Free ΓÇö no infrastructure cost.
- Fast ΓÇö Python dict lookup is O(1).
- Good enough ΓÇö the cache persists as long as the server runs. If the server restarts, sentences are regenerated (which is fine, costs nothing on the free tier).

---

## 11. Environment Variables

Add these to your `.env` file:

```bash
# Required for AI personalization
HF_API_KEY=hf_xxxxxxxxxxxxxxxxxxxxxxxx   # Free from huggingface.co/settings/tokens

# Already existing (not new)
RESUME_LINK=https://drive.google.com/...
EMAIL_SUBJECT="{company} Summer '26 Intern | Knight & CF Expert"
EMAIL_TEMPLATE_HTML="<p>Hi {name},</p><p>{opening_line}</p>..."
TRACKING_BASE_URL=http://127.0.0.1:10000
GOOGLE_SCRIPT_URL=https://script.google.com/...
```

---

## 12. End-to-End Example

### Input
```
email: john.smith@stripe.com
company: stripe
```

### Step 1 ΓÇö Enrichment
```
first_name: John         (extracted from email)
company:    Stripe        (normalized from "stripe")
```

### Step 2 ΓÇö AI Generation (3 API calls)
```
company_sentence: "Stripe powers global financial infrastructure, processing
                   billions of transactions with cutting-edge engineering."

opening_line:     "I'd love to contribute to Stripe's backend systems
                   operating at massive financial scale."

subject_lines:    [
  "Summer 2026 Backend Intern",
  "Backend Intern ΓÇö Stripe",
  "Quick Question About Internships",
  "Engineer Interested in Stripe",
  "Internship Opportunity Inquiry"
]
```

### Step 3 ΓÇö Subject Selection (A/B)
```
Previous Stripe emails sent: 0
Chosen subject: "Summer 2026 Backend Intern"     (index 0 % 5 = 0)
```

### Step 4 ΓÇö Email Rendered
```
Subject: Summer 2026 Backend Intern

Hi John,

I'd love to contribute to Stripe's backend systems operating at massive
financial scale.

I'm Kavya Rathod, a Software Intern at Discvr.ai (IIIT Gwalior '27).
I'm seeking a Summer 2026 Internship at Stripe.

ΓÇó 10k Daily Traffic: Led a team of 5 to build a high-traffic system.
ΓÇó Production AI: Developed RAG systems and CMS Microservices.
ΓÇó LeetCode Knight (1800+) | CF Expert (1700+)

[View Resume]

Best,
Kavya Rathod
```

### Step 5 ΓÇö Tracking Injected
```html
<!-- Open tracking pixel (invisible) -->
<img src="https://yourserver.com/track/open/john.smith@stripe.com" width="1" height="1" />

<!-- Resume link wrapped with click tracker -->
<a href="https://yourserver.com/track/click/john.smith@stripe.com?url=...">Resume</a>
```

### Step 6 ΓÇö Follow-up Scenarios
```
Day 1: Email sent
Day 2: John opens email ΓåÆ status: Warm
Day 4: No reply ΓåÆ Follow-up sent ("Just checking in...")
Day 10: No reply ΓåÆ Breakup email sent ("I won't reach out again")
```

---

## Summary

| Component | Technology | Cost |
|-----------|-----------|------|
| Backend | Python + FastAPI | Free |
| AI Model | Qwen 32B via Hugging Face | **Free** |
| Database | MongoDB Atlas | Free tier |
| Email Sending | Google Apps Script | Free |
| Tracking | Self-hosted pixel + redirect | Free |
| Caching | In-memory Python dict | Free |

**Total cost: $0/month**
