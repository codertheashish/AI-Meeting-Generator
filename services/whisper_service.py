"""
Speech-to-text via a hosted Whisper API (default: Groq's OpenAI-compatible
`/audio/transcriptions` endpoint, which runs whisper-large-v3).

Faster-Whisper (the local model used in the original, non-serverless
version of this app) doesn't work on Vercel: it needs to download and hold
~250MB+ of model weights in memory and run CPU inference, which blows past
serverless functions' execution-time and memory limits, and there's
nowhere persistent to cache the weights between invocations anyway. A
hosted API sidesteps all of that - the actual model runs on the provider's
infrastructure, and this function only makes one HTTP call.

Kept as its own module - separate from ai_service.py (OpenRouter) - so the
transcription provider can be swapped later (Deepgram, AssemblyAI, etc.)
without touching the summarization logic. Any provider with an
OpenAI-compatible /audio/transcriptions endpoint works here by changing
HOSTED_WHISPER_BASE_URL, HOSTED_WHISPER_API_KEY, and HOSTED_WHISPER_MODEL.
"""
import os
import logging

import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "whisper-large-v3"
REQUEST_TIMEOUT_SECONDS = 30  # combined with the Blob download before it, stays well under Vercel's 60s function timeout (see vercel.json)


def _config():
    api_key = os.getenv("HOSTED_WHISPER_API_KEY") or os.getenv("GROQ_API_KEY")
    base_url = os.getenv("HOSTED_WHISPER_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    model = os.getenv("HOSTED_WHISPER_MODEL", DEFAULT_MODEL)
    return api_key, base_url, model


def is_configured():
    return bool(_config()[0])


def transcribe_audio(audio_bytes, filename="audio.wav"):
    """
    Transcribe audio bytes using the hosted Whisper API and return:
    {
        "text": "full transcript text",
        "segments": [ {"start": float, "end": float, "text": str}, ... ]
    }
    Timestamps are preserved per-segment for the live transcription panel.
    """
    api_key, base_url, model = _config()
    if not api_key:
        raise RuntimeError(
            "HOSTED_WHISPER_API_KEY is not set. Get a free key from "
            "https://console.groq.com/keys (or another OpenAI-compatible "
            "transcription provider) and add it to your environment variables."
        )

    try:
        response = requests.post(
            f"{base_url}/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (filename, audio_bytes)},
            data={"model": model, "response_format": "verbose_json"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.exceptions.Timeout as exc:
        raise RuntimeError("Transcription timed out. Try a shorter clip.") from exc
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError("Couldn't reach the transcription API. Check your internet connection.") from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Transcription request failed: {exc}") from exc

    if response.status_code == 401:
        raise RuntimeError("The transcription API rejected the API key (401). Check HOSTED_WHISPER_API_KEY / GROQ_API_KEY.")
    if response.status_code == 429:
        raise RuntimeError("Transcription rate limit reached. Wait a moment and try again.")
    if response.status_code == 413:
        raise RuntimeError("Audio file is too large for the transcription API. Try a shorter clip.")
    if response.status_code >= 500:
        raise RuntimeError("The transcription service is currently unavailable. Please try again shortly.")
    if response.status_code != 200:
        logger.error("Whisper API error %s: %s", response.status_code, response.text[:1000])
        raise RuntimeError(f"Transcription failed ({response.status_code}). See server logs for details.")

    try:
        body = response.json()
    except ValueError as exc:
        raise RuntimeError("Transcription API returned an unreadable response.") from exc

    text = (body.get("text") or "").strip()
    segments = [
        {"start": seg.get("start", 0.0), "end": seg.get("end", 0.0), "text": (seg.get("text") or "").strip()}
        for seg in body.get("segments", [])
    ]

    if not text:
        raise RuntimeError("Transcription returned empty text. The audio may be silent or unsupported.")

    return {"text": text, "segments": segments}
