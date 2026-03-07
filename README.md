# Email Automation Backend - Template & Logic Documentation

This document explains how the dynamic email template system works, how it interacts with MongoDB, and how it combines with Environment Variables for a seamless outreach experience.

## 1. Template Storage (MongoDB)

Templates are stored in the `templates` collection in MongoDB. Each template consists of:
- **Name**: A descriptive name (e.g., "SDE Intern Intro").
- **Subject**: The email subject line.
- **HTML Body**: The raw HTML content of the email.
- **Type**: Defines the stage of the outreach (`initial`, `followup1`, or `breakup`).

## 2. Dynamic Placeholders

The system uses standard Python string formatting (`.format()`). You can use the following placeholders in your **Subject** or **HTML Body**:

| Placeholder | Description | Example Output |
| :--- | :--- | :--- |
| `{name}` | Recruiter's first name (falls back to 'there') | "Hi Kavya," |
| `{company}` | Recruiter's company (falls back to 'your company') | "at Google" |
| `{resume_link}` | **Recommended.** A styled, clickable HTML link to your resume. | `<a href="...">Resume</a>` |
| `{resume_url}` | The raw URL to your resume (useful for manual `<a>` tags). | `https://drive.google.com/...` |

> [!NOTE]
> The `{resume_url}` and `{resume_link}` are automatically powered by the `RESUME_LINK` variable in your `.env` file.

## 3. Fallback Logic: DB vs .env

The system follows a "DB-First" approach to give you maximum flexibility.

### Initial Emails (`/send-one`)
1. **With Template ID**: If you select a specific template in the Tester UI, that template is used.
2. **Without Template ID**: If no ID is provided, the system falls back to the legacy `.env` variables:
   - `EMAIL_SUBJECT`
   - `EMAIL_TEMPLATE_HTML`

### Automated Follow-ups (`/send-followup`)
The background automation logic (Stage 1 and 2) automatically checks the database:
1. **Search by Type**: It looks for the latest template marked as `followup1` (for Stage 1) or `breakup` (for Stage 2).
2. **Fallback to .env**: If no template of that type exists in the database, it falls back to the `.env` variables:
   - `FOLLOWUP_SUBJECT` / `FOLLOWUP_TEMPLATE_HTML`
   - `BREAKUP_SUBJECT` / `BREAKUP_TEMPLATE_HTML`

## 4. Analytics & Tracking

When an email is sent:
- The `templateId` and `templateName` are saved to the Recruiter's document.
- Tracking pixels and link redirects are automatically injected.
- Engagement (Opens, Clicks, Replies) is aggregated by Template Name in the **Analytics** dashboard.

## 5. Development Tips

- **Raw HTML**: You can paste full HTML layouts into the Template Manager.
- **Testing**: Use the **Tester** tab to send a live email to yourself. Select different templates from the dropdown to verify formatting.
- **Simulations**: Use the **Simulate Open/Click** buttons to verify that the tracking hooks are updating your dashboard correctly.
