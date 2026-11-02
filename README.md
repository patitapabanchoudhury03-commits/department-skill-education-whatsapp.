# Department of Skill Education WhatsApp Survey Agent — starter

This is a backend starter for a bilingual WhatsApp survey. It includes:
- webhook verification and inbound WhatsApp message handling
- language selection (English/Hindi)
- five-question survey
- SQLite response storage
- GET `/responses` for a simple response export/API
- GET `/health` health check

**This is not yet a deployed service and does not send any real messages until configured with Meta credentials and a public HTTPS webhook.** No student invitations have been sent.

## Run locally
1. Install Python 3.10+.
2. `python -m venv .venv`
3. Activate the environment.
4. `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and fill in credentials.
6. `uvicorn app:app --reload --port 8000`

The local webhook URL is `http://localhost:8000/webhook`; Meta requires a public HTTPS URL for webhook registration. For local testing, use a secure tunnel such as a development tunnel you control.

## Meta configuration
In Meta for Developers, open your app > WhatsApp > Configuration:
- Callback URL: your public HTTPS `/webhook`
- Verify token: same value as `WHATSAPP_VERIFY_TOKEN`
- Subscribe to the `messages` webhook field

Keep access tokens on the server only. Do not commit `.env` or share the token in chat. Start with Meta's test recipient number. Production outbound survey invitations require an approved WhatsApp message template and appropriate recipient opt-in.

## Important production work
Before real deployment, add authentication for the response endpoint, privacy notice/consent records, rate limits, logging and retention rules, robust validation, secure hosting, and approved invitation templates. SQLite is suitable only for a small prototype; use PostgreSQL for the full campaign. The included job-alert preference records consent; only send job postings to students who explicitly selected Yes.
