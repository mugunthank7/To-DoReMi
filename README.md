# To-Do-Re-Mi 🎵

A to-do list that plays your day in rhythm.

WhatsApp message → tasks (Claude extracts title/deadline/duration/importance) → priority ranking → time blocks around your Outlook meetings (optionally written back to Outlook).

## Run
    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
    cp .env.example .env        # fill in what you have; everything is optional
    .venv/bin/uvicorn app.main:app --port 8000     # UI at http://localhost:8000
    .venv/bin/python -m pytest

## LLM (free)
Get a free key from console.groq.com and one from Google AI Studio (aistudio.google.com), put them in `.env`. Order: Groq → Gemini → keyword rules.

### Budget safety
- Create both keys **without adding a payment method**. A free-tier key with no billing attached can't charge you; it just rate-limits.
- Don't upgrade Groq to a paid tier, and don't link a billing account to the Google Cloud project behind the Gemini key.
- The app also stops calling models after `LLM_DAILY_CAP` calls a day (default 150) and falls back to keyword rules.

## Outlook
1. Azure portal → App registrations → New → "Accounts in any org directory + personal", enable *Allow public client flows*, add delegated permission `Calendars.ReadWrite`.
2. Put the Application (client) ID in `MS_CLIENT_ID`. (A university tenant may require admin consent — if blocked, use a personal Outlook account or ask IT.)
3. `python -m app.outlook` once to sign in (device code). Blocks are tagged with category `ToDoReMi` and replaced on each replan.

## WhatsApp (Twilio sandbox)
1. Twilio Console → Messaging → Try WhatsApp; join the sandbox from your phone.
2. `ngrok http 8000`, set `PUBLIC_URL` to the ngrok URL and the sandbox webhook to `PUBLIC_URL/webhook/whatsapp` (POST).
3. Set `TWILIO_AUTH_TOKEN` and `ALLOWED_WHATSAPP=whatsapp:+1…` (your number) so only you can write to it.

Messages: free text adds tasks. Commands: `list`, `done 3`, `delete 3`, `replan`.

## Notes
- No auth on the web UI/API: run it locally only.
- Scheduler: weekdays, `WORK_START`–`WORK_END`, 15-min grid, 10-min buffer, first-fit by priority; tasks that can't meet their deadline are left unscheduled.
