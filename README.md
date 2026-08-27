# AI Meeting Generator

An AI-powered meeting assistant that records or ingests meeting audio, transcribes it
locally with **Whisper**, generates structured notes (summary, action items, key
highlights, decisions) with an LLM via **OpenRouter**, tracks speaker analytics, and
exports notes as PDF / DOCX / TXT or emails them directly.

![stack](https://img.shields.io/badge/backend-Flask-informational)
![stack](https://img.shields.io/badge/stt-Whisper-informational)
![stack](https://img.shields.io/badge/llm-OpenRouter-informational)

---

## ✨ Features

- 🎙️ Record live meeting audio in the browser (MediaRecorder + Web Audio API waveform)
- 📤 Upload existing audio/video meeting files (mp3, wav, m4a, mp4, mov, etc.)
- 📝 Local, offline speech-to-text using OpenAI's open-source **Whisper**
- 🗣️ Lightweight speaker labelling + speaking-time analytics
- 🤖 AI-generated meeting notes (summary, action items, highlights, decisions) via
  **OpenRouter** — swap models freely (GPT, Claude, Llama, etc.) with one env variable
- ✅ Editable, checkable action items stored in SQLite
- 📄 Export to PDF, DOCX, or TXT — and send the notes by email (SMTP)
- 📱 Responsive dashboard UI (desktop, tablet, mobile)

---

## 🧱 Tech Stack

| Layer     | Tech |
|-----------|------|
| Frontend  | HTML5, CSS3, Vanilla JS, Web Audio API, MediaRecorder API, Fetch API |
| Backend   | Python 3.11+, Flask, SQLite |
| Speech-to-text | OpenAI Whisper (runs locally, no API key needed) |
| AI notes  | OpenRouter (OpenAI-compatible LLM API) |
| Audio     | FFmpeg |
| Export    | ReportLab (PDF), python-docx (DOCX) |

---

## 📁 Project Structure

```
AI-Meeting-Generator/
├── app.py                     # Flask app entrypoint
├── requirements.txt
├── .env.example                # Copy to .env and fill in your keys
├── .gitignore
│
├── database/                   # SQLite database file lives here
├── models/
│   └── database.py             # All SQL access (no ORM)
│
├── services/
│   ├── whisper_service.py      # Local Whisper transcription
│   ├── ai_service.py           # OpenRouter LLM calls for notes
│   ├── speaker_service.py      # Speaking-time analytics
│   ├── audio_service.py        # Upload validation + FFmpeg conversion
│   └── export_service.py       # PDF / DOCX / TXT generation
│
├── routes/
│   ├── meeting_routes.py       # CRUD for meetings + action items
│   ├── transcription_routes.py # record/upload/transcribe/analyze/generate-notes
│   └── export_routes.py        # export/email endpoints
│
├── uploads/                    # Uploaded & recorded audio (gitignored)
├── exports/                    # Generated PDF/DOCX/TXT files (gitignored)
│
├── templates/
│   └── index.html
│
└── static/
    ├── css/ (style.css, dashboard.css, responsive.css)
    └── js/  (ui.js, recorder.js, transcription.js, notes.js, export.js, app.js)
```

---

## 🚀 Getting Started

### 1. Prerequisites

- **Python 3.11+**
- **FFmpeg** installed and available on your `PATH` (required for audio conversion
  and for Whisper to read most file formats).
  - Windows: `winget install ffmpeg` or download from https://ffmpeg.org/download.html
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`
- An **OpenRouter** API key (free to create) — https://openrouter.ai/keys

### 2. Clone & install

```bash
cd AI-Meeting-Generator
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

> The first run will download the Whisper model (`base` by default, ~150MB) the first
> time you transcribe a meeting — this requires an internet connection once.

### 3. Configure environment variables

Copy `.env.example` to `.env` and fill in your own values:

```bash
cp .env.example .env      # macOS/Linux
copy .env.example .env    # Windows
```

Required for AI note generation:

```
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=openai/gpt-4o-mini
```

Optional (only needed for "Send via Email"):

```
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password_here
```

**Never commit your real `.env` file** — it's already listed in `.gitignore`.

### 4. Run the app

```bash
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST   | `/api/record` | Save a recorded audio blob as a new meeting |
| POST   | `/api/upload` | Upload an audio/video meeting file |
| POST   | `/api/transcribe` | Run Whisper transcription on a meeting's audio |
| POST   | `/api/analyze` | Refresh word-count / speaker analytics |
| POST   | `/api/generate-notes` | Generate AI notes via OpenRouter |
| GET    | `/api/meetings` | List all meetings |
| GET    | `/api/meetings/<id>` | Get full meeting detail |
| PATCH  | `/api/meetings/<id>` | Update meeting title/date |
| DELETE | `/api/meetings/<id>` | Delete a meeting |
| PATCH  | `/api/action-items/<id>` | Edit / complete an action item |
| GET    | `/api/export/pdf/<id>` | Download meeting notes as PDF |
| GET    | `/api/export/docx/<id>` | Download meeting notes as DOCX |
| GET    | `/api/export/txt/<id>` | Download meeting notes as TXT |
| POST   | `/api/email` | Email the notes (PDF attached) to a recipient |

---

## 🔐 Security Notes

- No API keys are hardcoded — everything is read from environment variables via `.env`.
- `.env` is gitignored; only `.env.example` (with placeholder values) is committed.
- Uploaded files are validated by extension and size before being saved.
- SMTP credentials are only used server-side and never exposed to the browser.

---

## 🛠️ Troubleshooting

| Problem | Fix |
|---|---|
| "FFmpeg is not installed or not on PATH" | Install FFmpeg and confirm `ffmpeg -version` works in your terminal |
| "OPENROUTER_API_KEY is not set" | Add your key to `.env` and restart the server |
| Microphone permission denied | Allow mic access in your browser's site settings and reload |
| Slow first transcription | The Whisper model downloads once on first use — subsequent runs are fast |
| Email fails to send | Check `MAIL_SERVER`/`MAIL_USERNAME`/`MAIL_PASSWORD`; for Gmail use an **App Password**, not your normal password |

---

## 📄 License

This project is provided as-is for personal and educational use.
