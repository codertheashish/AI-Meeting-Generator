"""
speaker_service.py
-------------------
Derives per-speaker talk-time statistics from labeled transcript segments.
"""


def compute_speaker_stats(labeled_segments):
    """
    labeled_segments: [{"start": float, "end": float, "text": str, "speaker": str}, ...]
    Returns: [{"name": str, "speaking_time": int_seconds, "speaking_percentage": float}, ...]
    sorted by speaking_percentage descending.
    """
    if not labeled_segments:
        return []

    totals = {}
    for seg in labeled_segments:
        duration = max(0.0, seg.get("end", 0) - seg.get("start", 0))
        speaker = seg.get("speaker", "Unknown")
        totals[speaker] = totals.get(speaker, 0.0) + duration

    grand_total = sum(totals.values()) or 1.0

    stats = [
        {
            "name": speaker,
            "speaking_time": int(round(seconds)),
            "speaking_percentage": round((seconds / grand_total) * 100, 1),
        }
        for speaker, seconds in totals.items()
    ]

    stats.sort(key=lambda s: s["speaking_percentage"], reverse=True)
    return stats


def format_duration(total_seconds):
    """Seconds -> HH:MM:SS or MM:SS string."""
    total_seconds = int(total_seconds or 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"
