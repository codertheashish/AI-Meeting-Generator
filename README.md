# AI Meeting Notes Generator

A full-stack, mostly-free AI meeting assistant: record or upload a meeting,
get an accurate transcript from a **local** Faster-Whisper model (no per-minute
API cost), and generate a structured summary, action items, key highlights,
decisions, and follow-up points via a **free model on OpenRouter**. Export to
PDF, DOCX, or TXT, or email the notes directly.

> **No OpenAI API is used anywhere in this project.** Speech-to-text runs
> locally with Faster-Whisper, and meeting analysis/summarization uses the
> OpenRouter Chat Completions API.

## Features

- 🎙️ Record meetings live from the browser microphone (MediaRecorder API) with an animated waveform and timer
- 📁 Upload audio/video files (mp3, wav, m4a, webm, mp4, mov, etc.)
- 📝 Local, offline-capable speech-to-text via Faster-Whisper (timestamps preserved)
- 🤖 AI-generated summary, action items (with priority), key highlights, decisions, and follow-up points via OpenRouter's free models
- 👥 Optional, best-effort speaker analytics (see "Speaker Identification" below)
- ✅ Editable, checkable action items with priority tags
- ✏️ Rename any meeting — exported PDF/DOCX/TXT filenames follow the meeting's title, not a generic ID
- 📤 Export to PDF / DOCX / TXT, copy to clipboard, or send via email
- 🔐 Accounts with email/password login, plus optional one-click Google, LinkedIn, and GitHub sign-in — each user only ever sees their own meetings
- 🗂️ Persistent meeting history in SQLite
- 🔁 Retry button if AI analysis fails (free models occasionally return malformed JSON)

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, vanilla JavaScript, Web Audio API, MediaRecorder API, Font Awesome |
| Backend | Python 3.11+, Flask |
| Auth | Flask-Login (sessions) + Authlib (Google / LinkedIn / GitHub OAuth) + Werkzeug password hashing |
| Speech-to-Text | **Faster-Whisper** (runs locally on CPU, no API key, no cost) |
| AI Analysis | **OpenRouter API** (`https://openrouter.ai/api/v1/chat/completions`), defaults to a free model |
| Audio Processing | FFmpeg |
| Database | SQLite |

## Architecture / Pipeline

```
Audio/Video
   │
   ▼
 FFmpeg              (services/audio_service.py — convert to 16kHz mono WAV)
   │
   ▼
 Faster-Whisper       (services/whisper_service.py — LOCAL speech-to-text)
   │
   ▼
 Transcript (with timestamps)
   │
   ▼
 OpenRouter API        (services/ai_service.py — free LLM)
   │
   ▼
 Summary + Action Items + Highlights + Decisions + Follow-up Points
   │
   ▼
 SQLite                (models/database.py)
   │
   ▼
 Frontend Dashboard
```

Each stage is isolated in its own service module, so any piece (the STT
engine, the LLM provider, the export format) can be swapped independently.

## Prerequisites

- Python 3.11+
- [FFmpeg](https://ffmpeg.org/download.html) installed and available on your system `PATH`
  (test with `ffmpeg -version` in a terminal)
- A **free** OpenRouter API key (see below) — no OpenAI account needed
- ~1-2GB free disk space the first time Faster-Whisper downloads model weights (cached after that)

## Installation

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### Installing FFmpeg

- **Windows:** Download from [ffmpeg.org](https://ffmpeg.org/download.html), extract, and add the `bin` folder to your PATH. Or `winget install ffmpeg`.
- **macOS:** `brew install ffmpeg`
- **Linux (Debian/Ubuntu):** `sudo apt install ffmpeg`

Verify with `ffmpeg -version` and `ffprobe -version`.

### Faster-Whisper setup

Faster-Whisper is installed via `requirements.txt` (`pip install faster-whisper`)
and needs no separate setup — the first time you transcribe a meeting, it
downloads the selected model (default: `small`, ~250MB) and caches it locally.
Everything after that runs offline, entirely on your CPU (or GPU if you
configure `WHISPER_DEVICE=cuda` and have a CUDA-capable GPU with the matching
`compute_type`, e.g. `float16`).

Available model sizes (bigger = more accurate, slower, more RAM):
`tiny`, `base`, `small`, `medium`, `large-v2`, `large-v3`.

### OpenRouter API key setup

1. Create a free account at [openrouter.ai](https://openrouter.ai)
2. Generate a key at [openrouter.ai/keys](https://openrouter.ai/keys)
3. Browse [openrouter.ai/models](https://openrouter.ai/models) and filter by **Free** to find a free model slug (free models are commonly suffixed `:free`, e.g. `meta-llama/llama-3.1-8b-instruct:free`) — put whichever one you want in `OPENROUTER_MODEL`
4. Paste your key into `.env` as `OPENROUTER_API_KEY`

Free models can be rate-limited, occasionally unavailable, or slower than
paid ones — the app is built to handle this gracefully with clear errors and
a **Retry Analysis** button in the UI. Because free-tier models sometimes
return imperfect JSON, the backend does defensive extraction/parsing rather
than assuming a clean response.

### `.env` configuration

Copy the template and fill it in:

```bash
cp .env.example .env      # macOS/Linux
copy .env.example .env    # Windows
```

```
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=openrouter/free

WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8

SECRET_KEY=change_this_to_a_random_secret_string
FLASK_ENV=development
APP_URL=http://127.0.0.1:5000

MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password_here
MAIL_DEFAULT_SENDER=your_email@gmail.com
```

> **Never commit `.env`.** It's already listed in `.gitignore`. Only the
> Python backend ever reads `OPENROUTER_API_KEY` — it is never sent to, or
> accessible from, any HTML/CSS/JS served to the browser.
> For Gmail, use an [App Password](https://support.google.com/accounts/answer/185833), not your normal password.

## Login & Accounts

**Logging in is optional.** You can use the whole app — record, upload,
transcribe, generate notes, export — without ever creating an account.
Meetings made while logged out are stored in a shared "guest" area.

**If you do log in**, your meetings become private to your account — no
one else (including guest/anonymous visitors) can see them. This is useful
if multiple people share the same machine/deployment and want separate
histories.

**Email + password works immediately, no setup needed.** Go to
`/signup`, create an account, and you're in.

**Social login (Google / LinkedIn / GitHub) is optional too.** Each "Log in
with X" button only appears once you've added that provider's credentials
to `.env` — leave any of them blank to simply hide that button. Steps:

**Google**
1. [console.cloud.google.com](https://console.cloud.google.com) → APIs & Services → Credentials → **Create OAuth client ID** (type: Web application)
2. Authorized redirect URI: `http://127.0.0.1:5000/auth/google/callback`
3. Copy the Client ID/Secret into `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` in `.env`

**LinkedIn**
1. [developer.linkedin.com/apps](https://developer.linkedin.com/apps) → Create app
2. On the Auth tab, add the product **"Sign In with LinkedIn using OpenID Connect"**
3. Authorized redirect URL: `http://127.0.0.1:5000/auth/linkedin/callback`
4. Copy the Client ID/Secret into `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET` in `.env`

**GitHub**
1. [github.com/settings/developers](https://github.com/settings/developers) → OAuth Apps → **New OAuth App**
2. Authorization callback URL: `http://127.0.0.1:5000/auth/github/callback`
3. Copy the Client ID/Secret into `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` in `.env`

Restart `python app.py` after editing `.env` — social buttons appear on
`/login` and `/signup` automatically once credentials are detected.

**Forgot password** reuses the same SMTP settings (`MAIL_USERNAME` /
`MAIL_PASSWORD`) as the email-export feature — set those up once and both
work. Reset links expire after 1 hour.

If you're upgrading an existing install that predates accounts, any
meetings created before this update have no owner, so they'll show up in
the shared guest area (not lost, just not tied to any specific account).

## Running the Application

```bash
python app.py
```

Open **http://127.0.0.1:5000** in your browser — the dashboard loads right
away, no login required. Use the **Log In** button in the header if you
want a private, per-account meeting history.

The app fails gracefully (with a clear in-app error, not a crash) if
`OPENROUTER_API_KEY` is missing when you try to generate notes — the error
message tells you exactly what to add to `.env`.

## Project Structure

```
AI-Meeting-Notes/
├── app.py                     # Flask app factory & entry point
├── extensions.py               # Shared Flask-Login + Authlib instances
├── requirements.txt
├── .env.example
├── database/                  # SQLite database file lives here
├── models/
│   └── database.py            # sqlite3 data access layer (+ auto-migration)
├── services/
│   ├── auth_service.py        # Password hashing + signed reset tokens
│   ├── whisper_service.py     # Faster-Whisper transcription (LOCAL, no API)
│   ├── ai_service.py          # OpenRouter meeting analysis (ALL OpenRouter calls live here)
│   ├── speaker_service.py     # Optional, best-effort speaker labeling & analytics
│   ├── audio_service.py       # Upload validation + ffmpeg conversion
│   └── export_service.py      # PDF / DOCX / TXT generation
├── routes/
│   ├── auth_routes.py         # Signup/login/logout, forgot/reset password, OAuth
│   ├── meeting_routes.py      # CRUD for meetings & action items (per-user)
│   ├── transcription_routes.py# record/upload/transcribe/analyze
│   └── export_routes.py       # export + email
├── uploads/                   # Raw & converted audio files
├── exports/                   # Generated PDF/DOCX/TXT files
├── templates/
│   ├── index.html             # Main dashboard (requires login)
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
| POST | `/api/record` | Save a recorded audio blob as a new meeting |
| POST | `/api/upload` | Upload an audio/video file as a new meeting |
| POST | `/api/transcribe` | Transcribe a meeting's audio locally with Faster-Whisper |
| POST | `/api/analyze` / `/api/generate-notes` | Generate AI notes from the transcript via OpenRouter |
| GET | `/api/meetings` | List the logged-in user's meetings |
| GET | `/api/meetings/<id>` | Get one meeting with full details |
| PATCH | `/api/meetings/<id>` | Update meeting fields (e.g. rename via `{"title": "..."}`) |
| DELETE | `/api/meetings/<id>` | Delete a meeting |
| PATCH | `/api/action-items/<id>` | Edit task/assignee/deadline/priority, or toggle completion |
| GET | `/api/export/pdf/<id>` | Download notes as PDF (filename follows the meeting's title) |
| GET | `/api/export/docx/<id>` | Download notes as DOCX (filename follows the meeting's title) |
| GET | `/api/export/txt/<id>` | Download notes as TXT (filename follows the meeting's title) |
| POST | `/api/email` | Email the notes as an attachment |
| GET | `/api/settings` | Read-only config status (models, FFmpeg, email — never secrets) |

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
| GET | `/auth/<provider>` | Start Google/LinkedIn/GitHub OAuth login |
| GET | `/auth/<provider>/callback` | OAuth callback — creates or logs in the matching account |

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

**Faster-Whisper does not perform speaker diarization** — it only returns
timestamped text. This project labels speaker identification as
**optional and best-effort**: `services/speaker_service.py` looks for an
explicit `"Name: text"` pattern in the transcript and, if found, uses it for
per-speaker time/percentage analytics. If no such labels exist, every
segment is attributed to a single generic "Speaker" — the app never invents
fake speaker names. To add true acoustic diarization later, integrate a
library like `pyannote.audio` inside `audio_service.py`/`speaker_service.py`
(this requires extra dependencies and, for its best models, a Hugging Face
access token, which is why it isn't bundled by default).

## Error Handling

The app handles and surfaces clear, user-friendly messages for:

- Missing `OPENROUTER_API_KEY` (won't crash — tells you how to fix it)
- Invalid OpenRouter API key (401)
- OpenRouter rate limits (429)
- OpenRouter free-model unavailable (404 / bad response shape)
- Network errors / timeouts talking to OpenRouter
- Empty transcript (analysis is blocked until transcription succeeds)
- Faster-Whisper load/inference errors (e.g. invalid `WHISPER_MODEL`)
- FFmpeg missing or conversion failures
- Invalid/unsupported audio or video files
- AI responses that aren't valid JSON — safely extracted where possible;
  if parsing still fails, the raw response is logged server-side for
  debugging and the UI shows a **Retry Analysis** button instead of crashing
- Upload/export/email failures

## Troubleshooting

- **"FFmpeg is not installed"** — install FFmpeg and ensure `ffmpeg`/`ffprobe` are on your PATH.
- **"OPENROUTER_API_KEY is not set"** — check your `.env` file is present and loaded (restart the server after editing it).
- **"OpenRouter rejected the API key (401)"** — regenerate your key at openrouter.ai/keys and double-check there's no extra whitespace in `.env`.
- **"Model was not found on OpenRouter (404)"** — the free model slug in `OPENROUTER_MODEL` may have been retired; check https://openrouter.ai/models and pick a currently-available free one.
- **"The AI's response wasn't valid JSON"** — some free models occasionally misbehave; click **Retry Analysis**, or switch to a different `OPENROUTER_MODEL`.
- **Faster-Whisper is slow** — try a smaller model (`WHISPER_MODEL=base` or `tiny`), or set `WHISPER_DEVICE=cuda` with `WHISPER_COMPUTE_TYPE=float16` if you have an NVIDIA GPU.
- **Microphone permission denied** — check your browser's site settings and allow microphone access; HTTPS or `localhost` is required by browsers for `getUserMedia`.
- **Email failures (meeting notes or password reset)** — most providers require an app-specific password rather than your account password. For Gmail specifically, a `535 BadCredentials` error means you're using your normal Gmail password instead of an [App Password](https://support.google.com/accounts/answer/185833).
- **"Log in with Google/LinkedIn/GitHub" button doesn't appear** — that provider's `CLIENT_ID`/`CLIENT_SECRET` aren't set in `.env` yet (or the server wasn't restarted after adding them). See "Login & Accounts" above.
- **OAuth redirects back to the login page with an error** — double-check the redirect URI registered with the provider exactly matches `http://127.0.0.1:5000/auth/<provider>/callback` (no trailing slash, correct port), and that `APP_URL` in `.env` matches how you're accessing the app.
- **My old meetings disappeared after updating** — expected if you're upgrading from a version without accounts; see the note at the end of "Login & Accounts".
