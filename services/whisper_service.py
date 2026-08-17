"""
Speech-to-text via Faster-Whisper, running fully locally (no API key,
no network call, no per-minute cost).

Kept as its own module (separate from ai_service.py) so the transcription
backend could be swapped later (e.g. a different local model or a hosted
STT API) without touching the summarization logic.
"""
import os
import threading

_model = None
_model_lock = threading.Lock()


def _get_model():
    """
    Lazily load and cache the Faster-Whisper model. Loading is expensive
    (it reads model weights from disk/downloads them on first run), so we
    only do it once per process.
    """
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:  # re-check inside the lock
                from faster_whisper import WhisperModel

                model_size = os.getenv("WHISPER_MODEL", "small")
                device = os.getenv("WHISPER_DEVICE", "cpu")
                compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

                try:
                    _model = WhisperModel(model_size, device=device, compute_type=compute_type)
                except Exception as exc:  # noqa: BLE001
                    raise RuntimeError(
                        f"Failed to load Faster-Whisper model '{model_size}': {exc}. "
                        "Check that the model name is valid (tiny, base, small, medium, "
                        "large-v2, large-v3) and that you have network access the first "
                        "time it downloads weights, or a local model path if offline."
                    ) from exc
    return _model


def transcribe_audio(file_path):
    """
    Transcribe an audio file locally with Faster-Whisper and return a dict:
    {
        "text": "full transcript text",
        "segments": [ {"start": float, "end": float, "text": str}, ... ]
    }
    Timestamps are preserved per-segment for the live transcription panel.
    """
    if not os.path.exists(file_path):
        raise RuntimeError(f"Audio file not found: {file_path}")

    try:
        model = _get_model()
        segments_iter, info = model.transcribe(file_path, beam_size=5, vad_filter=True)
    except RuntimeError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Faster-Whisper transcription failed: {exc}") from exc

    segments = []
    text_parts = []
    for seg in segments_iter:
        clean_text = seg.text.strip()
        segments.append({"start": seg.start, "end": seg.end, "text": clean_text})
        text_parts.append(clean_text)

    text = " ".join(text_parts).strip()

    if not text:
        raise RuntimeError("Transcription returned empty text. The audio may be silent or unsupported.")

    return {"text": text, "segments": segments, "detected_language": getattr(info, "language", None)}
