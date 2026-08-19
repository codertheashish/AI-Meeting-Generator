"""
LLM-powered meeting analysis via the OpenRouter Chat Completions API:
summary, action items, key highlights, decisions, and follow-up points.

Isolated behind generate_meeting_notes() so the rest of the app never talks
to OpenRouter directly, and so the provider/model can be swapped later by
changing OPENROUTER_MODEL (or even the base URL) in .env.

This module intentionally uses plain `requests` instead of the OpenAI SDK -
no `from openai import OpenAI` and no calls to api.openai.com anywhere here.
"""
import os
import json
import re
import logging

import requests

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openrouter/free"
REQUEST_TIMEOUT_SECONDS = 45  # stay under Vercel's function timeout (see vercel.json's maxDuration) so a slow provider fails with our own clear error instead of a generic platform timeout

SYSTEM_PROMPT = (
    "You are an expert meeting-minutes assistant. Analyze the following meeting "
    "transcript and return ONLY valid JSON (no markdown fences, no commentary, "
    "no explanation before or after) in exactly this shape:\n"
    "{\n"
    '  "summary": "a concise 3-5 sentence summary of the meeting",\n'
    '  "action_items": [ {"task": "", "assigned_to": "", "deadline": "", "priority": "High/Medium/Low"} ],\n'
    '  "key_highlights": ["short bullet points of important topics discussed"],\n'
    '  "decisions": ["short bullet points of decisions that were made"],\n'
    '  "follow_up_points": ["open questions or items that need follow-up but were not resolved"]\n'
    "}\n"
    "Do not invent information that is not present in the transcript. "
    "If a person, deadline, or decision is not stated in the transcript, use an "
    "empty string (or omit the item) instead of guessing. Only assign a priority "
    "when it's reasonably inferable from urgency language in the transcript; "
    "otherwise use \"Medium\"."
)


def _get_config():
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)
    return api_key, model


def _extract_json(raw_text):
    """
    Free/small LLMs frequently wrap JSON in markdown fences, add a leading
    sentence, or trail extra text. This does a best-effort extraction:
    1. Strip ``` / ```json fences.
    2. If that still isn't valid JSON, grab the substring between the
       first '{' and the last '}'.
    """
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(json)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        json.loads(cleaned)
        return cleaned
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = cleaned[start:end + 1]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    # Give back the best-effort cleaned string; caller will raise a clear error.
    return cleaned


def generate_meeting_notes(transcript_text):
    """
    Send the transcript to OpenRouter's free (or configured) LLM and return
    a parsed dict with: summary, action_items, key_highlights, decisions,
    follow_up_points.

    Raises RuntimeError with a user-friendly message on any failure
    (missing key, network error, rate limit, invalid JSON, etc). The raw
    response is always logged for debugging, never silently dropped.
    """
    if not transcript_text or not transcript_text.strip():
        raise RuntimeError("Cannot generate notes from an empty transcript.")

    api_key, model = _get_config()
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Get a free key at https://openrouter.ai/keys "
            "and add it to your .env file."
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        # Optional but recommended by OpenRouter for routing/analytics attribution.
        "HTTP-Referer": os.getenv("APP_URL", "http://127.0.0.1:5000"),
        "X-Title": "AI Meeting Notes Generator",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Transcript:\n\n{transcript_text}"},
        ],
        "temperature": 0.3,
    }

    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.exceptions.Timeout as exc:
        raise RuntimeError("OpenRouter request timed out. Please try again.") from exc
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError("Couldn't reach OpenRouter. Check your internet connection.") from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"OpenRouter request failed: {exc}") from exc

    if response.status_code == 401:
        raise RuntimeError("OpenRouter rejected the API key (401 Unauthorized). Check OPENROUTER_API_KEY in .env.")
    if response.status_code == 429:
        raise RuntimeError("OpenRouter rate limit reached. Wait a moment and try again, or switch OPENROUTER_MODEL.")
    if response.status_code == 404:
        raise RuntimeError(
            f"Model '{model}' was not found on OpenRouter (404). It may have been retired - "
            "check https://openrouter.ai/models for currently available free models and "
            "update OPENROUTER_MODEL in .env."
        )
    if response.status_code >= 500:
        raise RuntimeError("OpenRouter is currently unavailable (server error). Please try again shortly.")
    if response.status_code != 200:
        logger.error("OpenRouter error %s: %s", response.status_code, response.text[:1000])
        raise RuntimeError(f"OpenRouter returned an unexpected error ({response.status_code}). See server logs for details.")

    try:
        body = response.json()
    except ValueError as exc:
        logger.error("OpenRouter returned non-JSON response: %s", response.text[:1000])
        raise RuntimeError("OpenRouter returned an unreadable response. Please try again.") from exc

    try:
        raw_content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        logger.error("Unexpected OpenRouter response shape: %s", json.dumps(body)[:1000])
        raise RuntimeError(
            "OpenRouter response didn't contain the expected content. The selected free "
            "model may currently be unavailable - try a different OPENROUTER_MODEL."
        ) from exc

    cleaned = _extract_json(raw_content)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse AI JSON. Raw model output was:\n%s", raw_content)
        raise RuntimeError(
            "The AI's response wasn't valid JSON, so notes couldn't be generated. "
            "This can happen with some free models - please retry, or try a different "
            "OPENROUTER_MODEL. (Raw response has been logged for debugging.)"
        ) from exc

    # Defensive defaults so the frontend never crashes on a missing key
    data.setdefault("summary", "")
    data.setdefault("action_items", [])
    data.setdefault("key_highlights", [])
    data.setdefault("decisions", [])
    data.setdefault("follow_up_points", [])

    # Normalize action items so every one has all expected fields
    normalized_items = []
    for item in data.get("action_items", []):
        if not isinstance(item, dict):
            continue
        normalized_items.append({
            "task": item.get("task", ""),
            "assigned_to": item.get("assigned_to", ""),
            "deadline": item.get("deadline", ""),
            "priority": item.get("priority") or "Medium",
        })
    data["action_items"] = normalized_items

    return data
