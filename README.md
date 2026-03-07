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

## ✨ Core Features

### 1. Dynamic Multistage Outreach
- **Initial Phase**: Send personalized emails using round-robin template selection.
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
- **Round-Robin Selection**: Rotate through multiple "Initial" templates to see which subject lines or pitches perform best.
- **Placeholders**: Supports dynamic injection of `{name}`, `{company}`, `{resume_link}`, and `{resume_url}`.
- **Tester UI**: Send live tests to yourself before launching a campaign.

### 5. Data Management
- **CSV Import**: Bulk upload recruiters with automatic deduplication.
- **Filtering**: View recruiters by status (New, Sent, Replied, Opened, Clicked, Error).

---

## ⚙️ Detailed Logic

### Follow-up Engine (`app.py`)
The system follows strict timing rules to avoid spamming while staying persistent:
- **Rule 1**: If `status == "sent"` AND `replied == False` AND 4 days have passed since `sentAt` → Send **Stage 1 Followup**.
- **Rule 2**: If `followupStage == 1` AND 6 days have passed since `followupAt` → Send **Stage 2 Breakup**.

### Tracking Logic
- **`{resume_link}`**: Generates a pre-styled HTML `<a>` tag: `<a href="...">Resume</a>`.
- **`{resume_url}`**: Returns just the raw tracking string, perfect for custom buttons or footers.

### Google Bridge
To ensure maximum deliverability, emails are handed off to a Google Apps Script that sends via your authenticated Gmail account, bypassing common "Spam" flags triggered by standard SMTP libraries.

---

## 📊 Dashboard Overview

1. **Overview & Stats**: High-level funnel (Total -> Sent -> Opened -> Replied).
2. **Recruiter Database**: The "Command Center" with deep filters and engagement timestamps.
3. **Template Manager**: Create, edit, and categorize templates by stage.
4. **Import & Tests**: Clean CSV uploads and end-to-end flow testing.

---

## 🚀 Getting Started

1. **Setup MongoDB**: Create collections for `temp` (recruiters) and `templates`.
2. **Configure `.env`**:
   - `MONGO_URI`, `MONGO_DB`
   - `GOOGLE_SCRIPT_URL` (Your bridge endpoint)
   - `GMAIL_ID`, `GMAIL_APP_PASSWORD` (For IMAP)
   - `TRACKING_BASE_URL` (Your public backend URL)
   - `RESUME_LINK` (Link to your CV)
3. **Run Backend**: `uvicorn app:app --reload`
4. **Run Frontend**: `npm run dev`

---

> [!TIP]
> Use the **"Test Panel"** in the dashboard to simulate Opens and Clicks. It's the best way to verify your tracking pixel is working before you send out 100+ emails!
