"""
whisper_service.py
-------------------
Wraps OpenAI's open-source Whisper model for local, offline speech-to-text.
This does NOT call any paid API - the model runs on this machine (CPU or GPU),
so no OPENAI_API_KEY / OPENROUTER_API_KEY is required for transcription.

The model is lazy-loaded once and cached in memory for the life of the process.
"""

import os
import threading

_model = None
_model_lock = threading.Lock()
WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL", "base")


def _load_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                import whisper  # imported lazily so app.py can boot even before install finishes
                _model = whisper.load_model(WHISPER_MODEL_NAME)
    return _model


def transcribe_audio(file_path):
    """
    Transcribe an audio/video file on disk and return a dict:
    {
        "text": "full transcript text",
        "segments": [{"start": 0.0, "end": 3.2, "text": "..."}, ...],
        "language": "en"
    }
    Raises RuntimeError with a friendly message on failure.
    """
    if not os.path.exists(file_path):
        raise RuntimeError("Audio file not found on server.")

    try:
        model = _load_model()
        result = model.transcribe(file_path, fp16=False, verbose=False)
    except Exception as exc:  # noqa: BLE001 - surfaced to the user as a friendly error
        raise RuntimeError(
            f"Transcription failed. Make sure FFmpeg is installed and the file is a valid "
            f"audio/video file. Details: {exc}"
        ) from exc

    segments = [
        {
            "start": round(seg.get("start", 0), 2),
            "end": round(seg.get("end", 0), 2),
            "text": seg.get("text", "").strip(),
        }
        for seg in result.get("segments", [])
    ]

    return {
        "text": result.get("text", "").strip(),
        "segments": segments,
        "language": result.get("language", "en"),
    }


def assign_speakers_round_robin(segments, speaker_names=None):
    """
    Whisper does not do speaker diarization out of the box.
    As a lightweight stand-in, this assigns speakers to segments using
    simple heuristics (pause length between segments) rotating through a
    provided/default name list. Good enough for demo-quality speaker
    labelling; swap in pyannote.audio here for real diarization later.
    """
    speaker_names = speaker_names or ["Speaker 1", "Speaker 2", "Speaker 3", "Speaker 4"]
    labeled = []
    current_speaker_idx = 0
    last_end = 0.0

    for seg in segments:
        # A pause longer than 1.2s is treated as a likely speaker change
        if seg["start"] - last_end > 1.2 and labeled:
            current_speaker_idx = (current_speaker_idx + 1) % len(speaker_names)
        labeled.append({**seg, "speaker": speaker_names[current_speaker_idx]})
        last_end = seg["end"]

    return labeled
