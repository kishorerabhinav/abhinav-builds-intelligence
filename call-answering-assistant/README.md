# Call Answering Assistant

An AI receptionist for your iPhone. When you don't pick up, an assistant powered by Claude
answers the call, finds out who it is and why they're calling, takes a message, and sends a
summary to an iPhone app where you can read the transcript and call back with one tap.

```
Caller ──► your iPhone number ──(not answered / declined)──► carrier forwards
                                                                  │
                                                                  ▼
                              Twilio number ──webhooks──► backend (FastAPI + Claude)
                                                                  │
                                         push notification + JSON API
                                                                  ▼
                                                         Call Assistant iPhone app
```

## Why it works this way

iOS (including iOS 27) doesn't let any third-party app pick up or listen to normal cellular
calls. Only Apple's own Live Voicemail and Call Screening can. So the assistant answers on a
cloud phone number instead, and your carrier's *conditional call forwarding* sends the calls
you miss or decline there. Your iPhone still rings first.

## What's here

| Folder | What it is |
|---|---|
| `backend/` | Python server: Twilio voice webhooks, the Claude conversation, call summaries, push notifications, and the API the app reads |
| `ios/` | SwiftUI iPhone app (iOS 17+, runs on iOS 27.2): call list, transcripts, call back / text back, assistant settings, forwarding setup guide |

## Setup

You need: a Twilio account with a phone number (voice-capable), an Anthropic API key, a Mac
with Xcode to install the app, and somewhere to run the backend with a public HTTPS address.

### 1. Run the backend

```bash
cd backend
cp .env.example .env          # fill in the values
pip install -r requirements.txt
set -a; source .env; set +a
uvicorn app.main:build_app --factory --host 0.0.0.0 --port 8000
```

Or with Docker: `docker build -t call-assistant backend && docker run --env-file backend/.env -p 8000:8000 -v call-data:/data call-assistant`.

It needs a public HTTPS URL. For a quick test, `ngrok http 8000` and set `PUBLIC_BASE_URL` to
the ngrok address. For everyday use, deploy the Docker image to any host (Fly.io, Render,
Railway, a VPS) with a persistent volume at `/data`.

Generate `APP_API_TOKEN` with something like `openssl rand -hex 32`.

### 2. Point Twilio at it

In the Twilio console, open your phone number's **Voice configuration**:

- **A call comes in** → Webhook, `https://YOUR-SERVER/twilio/voice`, HTTP POST
- **Call status changes** → `https://YOUR-SERVER/twilio/status`, HTTP POST

Every webhook is checked against your `TWILIO_AUTH_TOKEN` signature, so `PUBLIC_BASE_URL` must
match exactly what you paste into Twilio.

### 3. Install the iPhone app

```bash
brew install xcodegen
cd ios && xcodegen generate && open CallAssistant.xcodeproj
```

In Xcode, pick your team under Signing & Capabilities, change the bundle ID from
`com.example.CallAssistant` to your own, plug in your iPhone, and Run. Then in the app's
**Settings** tab enter your server URL and `APP_API_TOKEN`, and tap Connect.

Push notifications (optional): create an APNs key in your Apple Developer account
(Certificates, Identifiers & Profiles → Keys), and set `APNS_KEY_PATH`, `APNS_KEY_ID`,
`APNS_TEAM_ID` and `APNS_BUNDLE_ID` on the server. Keep `APNS_USE_SANDBOX=true` for builds
installed from Xcode. Without push, the app still shows new calls whenever you open it.

### 4. Turn on call forwarding

Open the app's **Set Up** tab, type your Twilio number, and it builds the carrier codes for you
to copy into the Phone keypad:

| When | GSM carriers (AT&T, T-Mobile, most non-US) | Verizon |
|---|---|---|
| Not answered after 20s | `**61*+1NUMBER**20#` | `*71NUMBER` (busy + no answer) |
| Declined / busy | `**67*+1NUMBER#` | |
| Phone off / no signal | `**62*+1NUMBER#` | |
| Turn it all off | `##002#` | `*73` |

Codes vary by carrier and country. If one doesn't work, your carrier's site will list the right
one. Then call your iPhone from another phone and let it ring.

## Teaching the assistant

In the app's Settings tab:

- **Your name** — used in the greeting ("you've reached Abhinav's assistant").
- **Custom greeting** — replaces the default opening line.
- **What the assistant should know** — plain-English instructions, e.g. "I'm at work until 6.
  Calls from the school are always urgent. Deliveries can go to the front door."

The assistant never shares personal details, agrees to payments, or reads out codes, and it
politely ends spam and scam calls (they're hidden from the list unless you turn on "Show spam").
Urgent calls arrive as time-sensitive notifications.

## How a call runs

1. `/twilio/voice` saves the call and speaks the greeting, then listens with Twilio speech
   recognition.
2. Each thing the caller says goes to `/twilio/turn`, which sends the transcript so far to
   Claude (`claude-opus-5-5` at low effort, to keep pauses short) and speaks the reply. Claude
   ends the call by appending `[END_CALL]`; silence twice, or 12 caller turns, also ends it.
3. When the call ends, `/twilio/status` has Claude write a structured summary (name, callback
   number, reason, urgency, summary) and sends the push notification.

Requests use the API's server-side refusal fallback (`fallbacks: "default"`), so if the model
declines a turn the API retries it on a fallback model instead of leaving the caller hanging.
Set `CLAUDE_MODEL` to change the model.

## Costs

You pay Twilio for the number and per-minute voice and speech recognition, Anthropic for API
usage, plus whatever your carrier charges for forwarded minutes.

## Tests

```bash
cd backend && pip install -r requirements.txt && python -m pytest -q
```

The tests drive a whole call through the webhooks with a fake assistant, and check signature
validation, API auth, and the Claude request handling.
