# 🚀 Advanced Email Outreach Automation

A professional-grade system designed to automate, track, and optimize recruiter outreach for internships and full-time roles. This platform combines a FastAPI backend with a React dashboard to manage the entire lifecycle of an application—from initial contact to final breakup emails.

---

## 🛠️ System Architecture

- **Backend**: FastAPI (Python 3.10+)
- **Database**: MongoDB (NoSQL for flexible recruiter and template data)
- **Delivery**: Google Apps Script Bridge (Gmail API bypass for high deliverability)
- **Inbound**: IMAP (Automatic reply detection)
- **Frontend**: React (Vite) with a polished, data-driven dashboard

---

## 📁 Project Structure

```
email_automation/
├── app.py                        # Slim entrypoint — mounts routers, starts server
├── config.py                     # Environment variables, MongoDB, logging, CORS
├── models.py                     # Pydantic request models
├── requirements.txt
│
├── routes/                       # API route handlers
│   ├── health.py                 # GET /
│   ├── templates.py              # CRUD /templates
│   ├── recruiters.py             # CRUD /recruiters, CSV/text import
│   ├── tracking.py               # Open/click tracking, test webhooks
│   ├── email.py                  # /send-one, /test-email, /check-replies, /send-followup
│   └── dashboard.py              # /dashboard/analytics, /dashboard/stats, /dashboard/recruiters
│
├── services/                     # Business logic
│   ├── email_builder.py          # build_email(), build_followup_email() with template resolution
│   ├── email_sender.py           # Google Apps Script Bridge delivery
│   ├── reply_checker.py          # IMAP-based reply detection
│   └── followup.py               # Follow-up engine with timing rules
│
├── test_flow.py                  # End-to-end pipeline test script
├── clean_and_send.py             # DB cleanup + single send test
└── .env                          # Environment configuration
```

---

## ✨ Core Features

### 1. Dynamic Multistage Outreach
- **Initial Phase**: Send personalized emails using round-robin template selection from the database.
- **Stage 1 Follow-up**: Automatically nudges recruiters 4 days after the initial send if no reply is detected.
- **Stage 2 "Breakup"**: A final, high-impact email sent 6 days after the follow-up to close the loop.

### 2. Intelligent Engagement Tracking
- **Open Tracking**: Invisible 1x1 pixel tracking injected into every email.
- **Click Tracking**: Every link to your resume is wrapped in a redirect tracker.
- **Real-time Analytics**: Dashboard shows exactly when an email was opened or a link was clicked, down to the second.

### 3. Automated Reply Detection
- Connects to your Gmail via IMAP to scan for "UNSEEN" messages.
- Scans sender addresses and automatically marks recruiters as `replied` in the database.
- Captures subject lines and snippets of the reply for quick viewing in the dashboard.

### 4. Template & A/B Management
- **Round-Robin Selection**: Rotate through multiple templates for **all stages** (initial, followup1, breakup) to see which subject lines or pitches perform best.
- **DB Template Priority**: Templates stored in MongoDB take priority over `.env` defaults. If no DB templates exist for a stage, the system falls back to behavioural branching (follow-up 1) or `.env` defaults.
- **Behavioral Follow-up 1**: When no DB template exists for follow-up 1, the system adapts based on recruiter engagement:
  - **Clicked resume** → personalized "glad you checked it out" message
  - **Opened email** → highlights a specific achievement
  - **No engagement** → uses the `.env` fallback template
- **Tester UI**: Send live tests to yourself for **any stage** (initial, follow-up 1, breakup) using any DB template before launching a campaign.

### 5. Template Placeholders

Templates support these dynamic placeholders:

| Placeholder      | Resolves To                                          | Example Usage             |
|------------------|------------------------------------------------------|---------------------------|
| `{name}`         | Recruiter's name (or "there")                        | `Hi {name},`              |
| `{company}`      | Recruiter's company (or "your team")                 | `at {company}`            |
| `{resume_link}`  | Bold, clickable `<a>` tag with click-tracking        | `View my {resume_link}`   |

**Example template:**
```html
<p>Hi {name},</p>
<p>I'd love to join {company}.</p>
<p>🔗 <b>View my {resume_link}</b></p>
```

### 6. Data Management
- **CSV Import**: Bulk upload recruiters with automatic deduplication.
- **Text Import**: Paste CSV text directly into the dashboard without file uploads.
- **Filtering**: View recruiters by status (New, Sent, Replied, Opened, Clicked, Error).

---

## ⚙️ Detailed Logic

### Follow-up Engine (`services/followup.py`)
The system follows strict timing rules to avoid spamming while staying persistent:
- **Rule 1**: If `status == "sent"` AND `replied == False` AND 4 days have passed since `sentAt` → Send **Stage 1 Followup**.
- **Rule 2**: If `followupStage == 1` AND 6 days have passed since `followupAt` → Send **Stage 2 Breakup**.

### Email Builder (`services/email_builder.py`)
Handles all template resolution for every email stage:
- Supports DB templates (round-robin per stage) with `.env` fallback
- Injects open-tracking pixel and click-tracking wrapper automatically

### Tracking Logic
- **`{resume_link}`**: Generates a pre-styled HTML `<a>` tag: `<a href="...">Resume</a>`.
- **`{resume_url}`**: Returns just the raw tracking URL, perfect for custom buttons or footers.

### Google Bridge
To ensure maximum deliverability, emails are handed off to a Google Apps Script that sends via your authenticated Gmail account, bypassing common "Spam" flags triggered by standard SMTP libraries.

---

## 📊 Dashboard Overview

1. **Overview & Stats**: High-level funnel (Total -> Sent -> Opened -> Replied).
2. **Recruiter Database**: The "Command Center" with deep filters and engagement timestamps.
3. **Template Manager**: Create, edit, and categorize templates by stage (initial, followup1, breakup).
4. **Import & Tests**: Clean CSV uploads, text paste imports, and end-to-end flow testing for all email stages.

---

## 🚀 Getting Started

1. **Setup MongoDB**: Create collections for `temp` (recruiters) and `templates`.
2. **Configure `.env`**:
   - `MONGO_URI`, `MONGO_DB`
   - `GOOGLE_SCRIPT_URL` (Your bridge endpoint)
   - `GMAIL_ID`, `GMAIL_APP_PASSWORD` (For IMAP)
   - `TRACKING_BASE_URL` (Your public backend URL)
   - `RESUME_LINK` (Link to your CV)
   - `EMAIL_SUBJECT`, `EMAIL_TEMPLATE_HTML` (Default initial template)
   - `FOLLOWUP_SUBJECT`, `FOLLOWUP_TEMPLATE_HTML` (Default follow-up template)
   - `BREAKUP_SUBJECT`, `BREAKUP_TEMPLATE_HTML` (Default breakup template)
3. **Install dependencies**: `pip install -r requirements.txt`
4. **Run Backend**: `uvicorn app:app --reload --port 10000`
5. **Run Frontend**: `cd recruiter-dashboard && npm run dev`

---

## 🔌 API Endpoints

| Method   | Path                        | Description                           |
|----------|-----------------------------|---------------------------------------|
| `GET`    | `/`                         | Health check                          |
| `GET`    | `/templates`                | List all templates                    |
| `POST`   | `/templates`                | Create a template                     |
| `PUT`    | `/templates/{id}`           | Update a template                     |
| `DELETE` | `/templates/{id}`           | Delete a template                     |
| `POST`   | `/recruiters`               | Add a recruiter                       |
| `GET`    | `/recruiters`               | List recruiters (with optional `?status=` filter) |
| `PATCH`  | `/recruiters/{email}`       | Update recruiter status               |
| `POST`   | `/recruiters/import-csv`    | Import recruiters from CSV file       |
| `POST`   | `/recruiters/import-text`   | Import recruiters from pasted CSV text|
| `POST`   | `/send-one`                 | Send one initial email (picks next "new" recruiter) |
| `POST`   | `/send-followup`            | Send one follow-up/breakup if due     |
| `POST`   | `/test-email`               | Test any template (initial/followup1/breakup) |
| `POST`   | `/check-replies`            | Scan inbox for replies                |
| `GET`    | `/track/open/{email}`       | Open tracking pixel                   |
| `GET`    | `/track/click/{email}`      | Click tracking redirect               |
| `POST`   | `/test/open/{email}`        | Simulate open event                   |
| `POST`   | `/test/click/{email}`       | Simulate click event                  |
| `GET`    | `/dashboard/analytics`      | Sent-per-day and template metrics     |
| `GET`    | `/dashboard/stats`          | Aggregate counts                      |
| `GET`    | `/dashboard/recruiters`     | Recruiter list for dashboard          |

---

> [!TIP]
> Use the **"Test Panel"** in the dashboard to send Initial, Follow-up 1, and Breakup test emails. Select a DB template from the dropdown to verify placeholder resolution and formatting before launching a campaign.
