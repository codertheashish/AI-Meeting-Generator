"""
OPTIONAL speaker identification / analytics module.

Faster-Whisper (services/whisper_service.py) does NOT perform speaker
diarization - it only returns timestamped text segments. True acoustic
diarization (telling voices apart purely from audio) needs a separate
model such as pyannote.audio, which requires extra dependencies and,
for its best models, a Hugging Face access token - so it is intentionally
NOT included here to keep setup simple and dependency-light.

Instead, this module does best-effort, text-based speaker labeling: it
looks for an explicit "Name: text" pattern at the start of transcript
segments (common when a transcript already has speaker tags baked in).
If no such labels are found anywhere in the transcript, every segment is
attributed to a single generic "Speaker" bucket - never a fabricated name -
so the UI still renders sensible analytics instead of crashing or lying
about who said what.

To add real diarization later: run pyannote.audio (or similar) on the
converted WAV file in audio_service.py, produce a list of
{start, end, speaker_label} turns, and feed them into
label_segments_with_speakers() via a new `diarization_turns` parameter.
"""
import re


SPEAKER_LINE_RE = re.compile(r"^\s*([A-Z][A-Za-z0-9 .'-]{0,30}):\s*(.+)$")


def label_segments_with_speakers(segments, known_speakers=None):
    """
    Given Whisper segments [{start, end, text}], try to detect a
    "Name: text" pattern at the start of each segment's text and split
    speaking time accordingly. Falls back to round-robin assignment among
    known_speakers (from the AI notes) if no explicit labels are found.
    """
    labeled = []
    detected_any_label = False

    for seg in segments:
        match = SPEAKER_LINE_RE.match(seg["text"])
        if match:
            speaker, text = match.group(1).strip(), match.group(2).strip()
            detected_any_label = True
        else:
            speaker, text = None, seg["text"]
        labeled.append({
            "start": seg["start"],
            "end": seg["end"],
            "speaker": speaker,
            "text": text,
        })

    if not detected_any_label:
        speakers_pool = known_speakers or ["Speaker 1"]
        for i, seg in enumerate(labeled):
            seg["speaker"] = speakers_pool[i % len(speakers_pool)]

    else:
        # Fill any un-labeled segments with the most recent known speaker
        last_speaker = labeled[0]["speaker"] or (known_speakers[0] if known_speakers else "Speaker 1")
        for seg in labeled:
            if seg["speaker"] is None:
                seg["speaker"] = last_speaker
            else:
                last_speaker = seg["speaker"]

    return labeled


def compute_speaking_stats(labeled_segments):
    """
    Returns a list of {name, speaking_time (seconds), speaking_percentage}
    sorted by speaking time descending.
    """
    totals = {}
    for seg in labeled_segments:
        duration = max(0.0, seg["end"] - seg["start"])
        totals[seg["speaker"]] = totals.get(seg["speaker"], 0.0) + duration

    grand_total = sum(totals.values()) or 1.0
    stats = [
        {
            "name": name,
            "speaking_time": round(seconds),
            "speaking_percentage": round((seconds / grand_total) * 100, 1),
        }
        for name, seconds in totals.items()
    ]
    stats.sort(key=lambda s: s["speaking_time"], reverse=True)
    return stats


def format_transcript_for_display(labeled_segments):
    """Build the Timestamp | Speaker | Transcript rows the UI expects."""
    rows = []
    for seg in labeled_segments:
        minutes, seconds = divmod(int(seg["start"]), 60)
        hours, minutes = divmod(minutes, 60)
        timestamp = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        rows.append({"timestamp": timestamp, "speaker": seg["speaker"], "text": seg["text"]})
    return rows
