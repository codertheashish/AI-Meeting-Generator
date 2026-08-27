"""
ai_service.py
-------------
Handles all calls to the LLM used for meeting-notes generation.

Provider: OpenRouter (https://openrouter.ai) - an OpenAI-compatible API
that can route to many different models (OpenAI, Anthropic, Meta, etc.)
through a single API key.

This module is intentionally isolated from the rest of the app so the
LLM provider can be swapped later (e.g. back to native OpenAI, or to
Azure OpenAI) by editing ONLY this file.
"""

import os
import json
import re
import requests

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
SITE_URL = os.getenv("OPENROUTER_SITE_URL", "http://127.0.0.1:5000")
SITE_NAME = os.getenv("OPENROUTER_SITE_NAME", "AI Meeting Generator")

SYSTEM_PROMPT = (
    "You are an assistant that turns raw meeting transcripts into structured, "
    "accurate meeting notes. Only use information present in the transcript. "
    "Do not invent names, dates, or facts that are not present. "
    "Always reply with valid JSON only - no markdown fences, no commentary."
)

PROMPT_TEMPLATE = """Analyze the following meeting transcript and return ONLY valid JSON
(no markdown, no code fences, no extra text) with exactly this shape:

{{
  "summary": "a concise 3-6 sentence summary of the meeting",
  "action_items": [
    {{"task": "...", "assigned_to": "...", "deadline": "..."}}
  ],
  "key_highlights": ["...", "..."],
  "decisions": ["...", "..."],
  "speakers": [
    {{"name": "...", "speaking_percentage": 0}}
  ]
}}

Rules:
- Do not invent information that is not present in the transcript.
- If deadlines or assignees are not mentioned, use an empty string.
- If speaker names are not identifiable, use "Speaker 1", "Speaker 2", etc.
- speaking_percentage values should roughly add up to 100 if derivable, otherwise use 0.

Transcript:
\"\"\"
{transcript}
\"\"\"
"""


class AIServiceError(Exception):
    pass


def _call_openrouter(messages, temperature=0.3, max_tokens=2000):
    if not OPENROUTER_API_KEY:
        raise AIServiceError(
            "OPENROUTER_API_KEY is not set. Add it to your .env file to enable AI note generation."
        )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        # Optional but recommended by OpenRouter for attribution / rankings
        "HTTP-Referer": SITE_URL,
        "X-Title": SITE_NAME,
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=90)
    except requests.RequestException as exc:
        raise AIServiceError(f"Could not reach OpenRouter: {exc}") from exc

    if resp.status_code != 200:
        raise AIServiceError(f"OpenRouter API error ({resp.status_code}): {resp.text[:500]}")

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise AIServiceError(f"Unexpected response from OpenRouter: {data}") from exc


def _safe_parse_json(raw_text):
    """Strip markdown fences if present and parse JSON, with a regex fallback."""
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(json)?", "", cleaned.strip(), flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned.strip()).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    raise AIServiceError("AI response was not valid JSON. Please try generating notes again.")


def generate_meeting_notes(transcript_text):
    """
    Sends the transcript to the LLM and returns a normalized dict:
    {summary, action_items, key_highlights, decisions, speakers}
    """
    if not transcript_text or not transcript_text.strip():
        raise AIServiceError("Transcript is empty - nothing to analyze.")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": PROMPT_TEMPLATE.format(transcript=transcript_text[:15000])},
    ]

    raw = _call_openrouter(messages)
    parsed = _safe_parse_json(raw)

    return {
        "summary": parsed.get("summary", ""),
        "action_items": parsed.get("action_items", []) or [],
        "key_highlights": parsed.get("key_highlights", []) or [],
        "decisions": parsed.get("decisions", []) or [],
        "speakers": parsed.get("speakers", []) or [],
    }
