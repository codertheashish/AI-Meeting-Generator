# AI Meeting Notes Generator

An AI meeting assistant built to run on **Vercel's serverless platform**:
record or upload a meeting, get an accurate transcript from a hosted
Whisper API, and generate a structured summary, action items, key
highlights, decisions, and follow-up points via a free model on
OpenRouter. Export to PDF, DOCX, or TXT, or email the notes directly.

> **This is the Vercel-ready version.** It's a rewrite of an earlier
> version that used local SQLite, local FFmpeg, and a local Faster-Whisper
> model - none of which work on serverless functions (read-only ephemeral
> filesystem, strict execution-time limits, no way to cache a large model
> between invocations). Every storage/compute-heavy piece now runs as an
> external service instead. See "Architecture" below for exactly what
> changed and why.

## Features

- 🎙️ Record meetings live from the browser microphone (MediaRecorder API) with an animated waveform and timer
- 📁 Upload audio/video files (mp3, wav, m4a, webm, mp4, mov, etc.)
- 📝 Speech-to-text via a hosted Whisper API (timestamps preserved)
- 🤖 AI-generated summary, action items (with priority), key highlights, decisions, and follow-up points via OpenRouter's free models
- 👥 Optional, best-effort speaker analytics (see "Speaker Identification" below)
- ✅ Editable, checkable action items with priority tags
- ✏️ Rename any meeting — exported PDF/DOCX/TXT filenames follow the meeting's title, not a generic ID
- 📤 Export to PDF / DOCX / TXT (generated in-memory, nothing touches disk), copy to clipboard, or send via email
- 🔐 Login is optional — the whole app works for anonymous visitors (shared "guest" area); logging in with email/password gives you a private meeting history
- 🗂️ Persistent meeting history in Postgres
- 🔁 Retry button if AI analysis fails (free models occasionally return malformed JSON)

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, vanilla JavaScript, Web Audio API, MediaRecorder API, Font Awesome |
| Backend | Python 3.12, Flask, deployed as a Vercel serverless function |
| Auth | Flask-Login (sessions) + Werkzeug password hashing — email/password only, no OAuth |
| Database | **Postgres** (Vercel Postgres/Neon, Supabase, Railway - any works) |
| Audio Storage | **Vercel Blob** (bridges the upload request and the later transcribe request) |
| Speech-to-Text | **Hosted Whisper API** (default: Groq's free `whisper-large-v3`) |
| AI Analysis | **OpenRouter API**, defaults to a free model |
| Document Export | `python-docx` / `fpdf2`, generated fully in memory |

## Architecture

```
Audio/Video (browser)
   │
   ▼
 Vercel Blob            (services/storage_service.py — persists audio between requests)
   │
   ▼
 Hosted Whisper API      (services/whisper_service.py — no local model, no FFmpeg needed)
   │
   ▼
 Transcript (with timestamps)
   │
   ▼
 OpenRouter API           (services/ai_service.py — free LLM)
   │
   ▼
 Summary + Action Items + Highlights + Decisions + Follow-up Points
   │
   ▼
 Postgres                 (models/database.py)
   │
   ▼
 Frontend Dashboard
```

### What changed from a "normal" local Flask app, and why

| Piece | Local version | This (Vercel) version | Why |
|---|---|---|---|
| Database | SQLite file on disk | Postgres (external) | Vercel's filesystem is read-only outside `/tmp`, and `/tmp` is wiped between invocations - a `.db` file can't persist. |
| Uploaded audio | Saved to a local `uploads/` folder | Uploaded to Vercel Blob, referenced by URL | The `/api/upload` and `/api/transcribe` requests can even run on different physical machines - nothing local survives between them. |
| Audio format conversion | FFmpeg subprocess call | Removed entirely | FFmpeg isn't reliably available in Vercel's Python runtime, and turned out to be unnecessary - the hosted Whisper API accepts the original upload formats directly. |
| Speech-to-text | Local Faster-Whisper model (250MB+ weights, CPU inference) | Hosted Whisper API (one HTTP call) | Loading and running a large model exceeds serverless memory/time limits, and there's nowhere to cache the weights between cold starts. |
| PDF/DOCX/TXT export | Written to a local `exports/` folder, served via `send_file(path)` | Generated as an in-memory buffer, streamed directly via `send_file(buffer)` | No local folder to write to - and it turns out to be simpler this way regardless. |

Each of these lives in its own module (`services/storage_service.py`,
`services/whisper_service.py`, `services/ai_service.py`,
`services/export_service.py`), so any one of them could be swapped for a
different provider later without touching the others.

## Prerequisites

You'll need free accounts/keys for 3 external services before deploying
(all have generous free tiers):

1. **A Postgres database** — via Vercel's Storage tab (Neon-backed), or Supabase/Neon/Railway directly
2. **A Vercel Blob store** — via Vercel's Storage tab, same project
3. **A Groq API key** (or another OpenAI-compatible transcription provider) — free at [console.groq.com/keys](https://console.groq.com/keys)
4. **An OpenRouter API key** — free at [openrouter.ai/keys](https://openrouter.ai/keys)

Optional: SMTP credentials for email (meeting-notes emails and password-reset links).

## Deploying to Vercel

1. **Push this project to a GitHub repo** (or GitLab/Bitbucket), then import it in the Vercel dashboard: **Add New → Project**.
2. **Connect a Postgres database:** in your new Vercel project, go to **Storage → Create Database → Postgres**, connect it to the project. `DATABASE_URL` is added to your project's environment variables automatically.
3. **Connect a Blob store:** **Storage → Create Database → Blob**, connect it to the same project. `BLOB_READ_WRITE_TOKEN` is added automatically.
4. **Set the remaining environment variables** under **Settings → Environment Variables** (see `.env.example` for the full list — at minimum you need `HOSTED_WHISPER_API_KEY`, `OPENROUTER_API_KEY`, and `SECRET_KEY`).
5. **Redeploy** (Vercel does this automatically on push, or trigger a manual redeploy so the new env vars take effect).
6. Open your `https://<your-app>.vercel.app` URL — the dashboard loads directly, no login required, but sign up if you want a private history.

`vercel.json` and `api/index.py` are already set up to route all traffic to the Flask app (`api/index.py` just re-exports the `app` object from the root `app.py`), and `.python-version` pins Python 3.12.

### Known limits on Vercel

- **Function timeout:** `vercel.json` sets `maxDuration: 60`. On the free Hobby plan, Vercel may cap this lower depending on your plan tier — check your dashboard. All internal HTTP timeouts (OpenRouter, Whisper, Blob) are tuned to fail with a clear in-app error well before that ceiling, rather than getting killed by the platform with a generic error.
- **Request body size:** Vercel serverless functions commonly cap request bodies around 4.5MB (varies by plan/config). `audio_service.MAX_FILE_SIZE_MB` is set to 25MB to match a reasonable meeting-clip size, but very large recordings may get rejected by Vercel's edge layer before reaching the app at all. For long recordings, either upgrade your Vercel plan's limits or switch to client-side direct-to-Blob uploads (not implemented here - see Vercel's docs on "client uploads" if you need this).
- **Cold starts:** the first request after a period of inactivity will be slower while the function spins up; this is normal for serverless.

## Local Development

Local dev now also talks to the same external services (Postgres, Blob,
Groq, OpenRouter) - there's no more local-SQLite/local-FFmpeg fallback,
since the whole point of this version is to match what runs on Vercel.

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in the same values you'd set on
Vercel (Postgres `DATABASE_URL`, `BLOB_READ_WRITE_TOKEN`, `HOSTED_WHISPER_API_KEY`,
`OPENROUTER_API_KEY`, etc. — a local Postgres instance works fine too, just
point `DATABASE_URL` at it).

```bash
python app.py
```

Open **http://127.0.0.1:5000**.

## Login & Accounts

**Logging in is optional.** You can use the whole app — record, upload,
transcribe, generate notes, export — without ever creating an account.
Meetings made while logged out are stored in a shared "guest" area.

**If you do log in**, your meetings become private to your account — no
one else (including guest/anonymous visitors) can see them.

**Email + password only** — no OAuth/social login, so there's nothing to
register with a third-party provider. Go to `/signup`, create an account,
and you're in.

**Forgot password** reuses the same SMTP settings (`MAIL_USERNAME` /
`MAIL_PASSWORD`) as the email-export feature. Reset links expire after 1 hour.

## Project Structure

```
AI-Meeting-Notes/
├── app.py                     # Flask app factory (also used for local dev)
├── api/
│   └── index.py               # Vercel entrypoint - re-exports app.py's `app`
├── vercel.json                # Routes all traffic to api/index.py, sets maxDuration
├── .python-version            # Pins Python 3.12 for Vercel's runtime
├── .vercelignore
├── requirements.txt
├── .env.example
├── extensions.py              # Shared Flask-Login + Authlib instances
├── models/
│   └── database.py            # Postgres data access layer (psycopg2) + auto-migration
├── services/
│   ├── auth_service.py        # Password hashing + signed reset tokens
│   ├── storage_service.py     # Vercel Blob upload/download (REST API via requests)
│   ├── whisper_service.py     # Hosted Whisper API transcription (no local model)
│   ├── ai_service.py          # OpenRouter meeting analysis (ALL OpenRouter calls live here)
│   ├── speaker_service.py     # Optional, best-effort speaker labeling & analytics
│   ├── audio_service.py       # Upload validation, hands off to storage_service
│   └── export_service.py      # PDF / DOCX / TXT generation, entirely in-memory
├── routes/
│   ├── auth_routes.py         # Signup/login/logout, forgot/reset password (email/password only)
│   ├── meeting_routes.py      # CRUD for meetings & action items (per-user)
│   ├── transcription_routes.py# record/upload/transcribe/analyze
│   └── export_routes.py       # export + email
├── templates/
│   ├── index.html             # Main dashboard (works logged in or anonymous)
│   ├── login.html
│   ├── signup.html
│   ├── forgot_password.html
│   └── reset_password.html
└── static/
    ├── css/ (style, dashboard, responsive, auth)
    └── js/ (app, recorder, transcription, notes, export, ui, settings, auth)
```

## API Reference

### Meetings & notes

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/record` | Save a recorded audio blob (uploads to Vercel Blob) as a new meeting |
| POST | `/api/upload` | Upload an audio/video file (uploads to Vercel Blob) as a new meeting |
| POST | `/api/transcribe` | Download the meeting's audio from Blob and transcribe it via the hosted Whisper API |
| POST | `/api/analyze` / `/api/generate-notes` | Generate AI notes from the transcript via OpenRouter |
| GET | `/api/meetings` | List the logged-in user's meetings (or the shared guest list, if anonymous) |
| GET | `/api/meetings/<id>` | Get one meeting with full details |
| PATCH | `/api/meetings/<id>` | Update meeting fields (e.g. rename via `{"title": "..."}`) |
| DELETE | `/api/meetings/<id>` | Delete a meeting |
| PATCH | `/api/action-items/<id>` | Edit task/assignee/deadline/priority, or toggle completion |
| GET | `/api/export/pdf/<id>` | Download notes as PDF (in-memory, filename follows the meeting's title) |
| GET | `/api/export/docx/<id>` | Download notes as DOCX (in-memory) |
| GET | `/api/export/txt/<id>` | Download notes as TXT (in-memory) |
| POST | `/api/email` | Email the notes as an attachment |
| GET | `/api/settings` | Read-only config status (DB/Blob/Whisper/OpenRouter/email — never secrets) |

Login is optional for all of the above. If you're logged in, they operate on your private meetings; if not, they operate on the shared guest bucket (`user_id` is `NULL`). No endpoint returns a 401 for being logged out.

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| GET | `/login`, `/signup`, `/forgot-password` | Render the respective auth pages |
| POST | `/api/auth/signup` | Create an account with email + password |
| POST | `/api/auth/login` | Log in with email + password |
| GET | `/logout` | End the session |
| POST | `/api/auth/forgot-password` | Email a password-reset link (expires in 1 hour) |
| GET | `/reset-password/<token>` | Render the reset-password form (or an "expired" message) |
| POST | `/api/auth/reset-password` | Set a new password using a valid reset token |

### AI note JSON shape

`ai_service.generate_meeting_notes()` asks the model to return exactly:

```json
{
    "summary": "",
    "action_items": [
        { "task": "", "assigned_to": "", "deadline": "", "priority": "High/Medium/Low" }
    ],
    "key_highlights": [],
    "decisions": [],
    "follow_up_points": []
}
```

The prompt explicitly instructs the model not to invent people, deadlines,
or decisions that aren't in the transcript — if something isn't stated, it
comes back as an empty string/array rather than a guess.

## Speaker Identification

The hosted Whisper API returns timestamped text but does **not** perform
speaker diarization. This project labels speaker identification as
**optional and best-effort**: `services/speaker_service.py` looks for an
explicit `"Name: text"` pattern in the transcript and, if found, uses it
for per-speaker time/percentage analytics. If no such labels exist, every
segment is attributed to a single generic "Speaker" — the app never
invents fake speaker names. True acoustic diarization (e.g. via
`pyannote.audio`) isn't included here since it needs extra dependencies
and typically a separate model-hosting token, which doesn't fit well in a
serverless function anyway.

## Error Handling

The app handles and surfaces clear, user-friendly messages for:

- Missing `DATABASE_URL`, `BLOB_READ_WRITE_TOKEN`, `HOSTED_WHISPER_API_KEY`, or `OPENROUTER_API_KEY` (each logged clearly at startup, and fails gracefully rather than crashing when actually used)
- Invalid/expired API keys (401s) from the Whisper API or OpenRouter
- Rate limits (429s) from either provider
- Network errors / timeouts talking to Blob, the Whisper API, or OpenRouter
- Empty transcript (analysis is blocked until transcription succeeds)
- Unsupported/invalid audio or video files, or files over the size limit
- AI responses that aren't valid JSON — safely extracted where possible; if parsing still fails, the raw response is logged server-side and the UI shows a **Retry Analysis** button instead of crashing
- Gmail-specific SMTP auth failures get a pointed message about needing an App Password
- Upload/export/email failures generally

## Troubleshooting

- **500 `FUNCTION_INVOCATION_FAILED` on Vercel** — almost always a missing environment variable. Check **Settings → Environment Variables** against `.env.example`, and check **Deployments → [latest] → Functions → Logs** for the actual Python traceback.
- **"DATABASE_URL is not set"** — connect a Postgres database under the Storage tab, or set it manually if using an external provider (Neon/Supabase/Railway).
- **"BLOB_READ_WRITE_TOKEN is not set"** — connect a Vercel Blob store under the Storage tab.
- **"HOSTED_WHISPER_API_KEY is not set"** — get a free key from [console.groq.com/keys](https://console.groq.com/keys).
- **"OPENROUTER_API_KEY is not set"** — get a free key from [openrouter.ai/keys](https://openrouter.ai/keys).
- **"Model was not found on OpenRouter (404)"** — the free model slug in `OPENROUTER_MODEL` may have been retired; check [openrouter.ai/models](https://openrouter.ai/models) and pick a currently-available free one.
- **413 / upload rejected** — the file exceeds `MAX_CONTENT_LENGTH` (25MB) or Vercel's own request-size limit (commonly ~4.5MB) — try a shorter clip.
- **Email failures (meeting notes or password reset)** — for Gmail specifically, a `535 BadCredentials` error means you're using your normal Gmail password instead of an [App Password](https://support.google.com/accounts/answer/185833).
- **My old meetings disappeared after this update** — if you're migrating from the local-SQLite version, meeting data does not automatically transfer to Postgres; this is a fresh database.
