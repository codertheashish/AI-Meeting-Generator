"""
Audio/video upload handling for the Vercel deployment.

Two things changed from the original FFmpeg-based version:

1. Uploads go straight to Vercel Blob storage (services/storage_service.py)
   instead of local disk, since Vercel's serverless filesystem doesn't
   persist between the /api/upload request and the later /api/transcribe
   request - they can even run on different physical machines.

2. FFmpeg conversion is gone entirely. It's not reliably available in
   Vercel's Python runtime, and it turned out to be unnecessary anyway:
   the hosted Whisper API (services/whisper_service.py) natively accepts
   all the formats this app allows (mp3, wav, m4a, webm, mp4, mov, etc.),
   so the original uploaded bytes are sent as-is.

Duration is read from file metadata via `mutagen` (pure Python, no
external binary) instead of `ffprobe`.
"""
import io
import os
from werkzeug.utils import secure_filename

from services import storage_service

ALLOWED_EXTENSIONS = {"wav", "mp3", "m4a", "webm", "ogg", "mp4", "mov", "mkv", "flac"}
MAX_FILE_SIZE_MB = 25  # keep uploads well inside serverless function payload/time limits


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file_storage):
    """
    Validate an uploaded file and persist it to Vercel Blob storage.
    Returns the blob's public URL (stored in meetings.audio_file), or
    raises ValueError for anything the user needs to fix (bad type, too big).
    """
    if not file_storage or file_storage.filename == "":
        raise ValueError("No file selected.")

    filename = secure_filename(file_storage.filename)
    if not allowed_file(filename):
        raise ValueError(
            f"Unsupported file type. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    data = file_storage.read()
    size_mb = len(data) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise ValueError(
            f"File too large ({size_mb:.1f}MB). Max is {MAX_FILE_SIZE_MB}MB on this deployment "
            "(serverless functions have request-size and execution-time limits)."
        )
    if size_mb == 0:
        raise ValueError("The uploaded file is empty.")

    content_type = file_storage.mimetype or "application/octet-stream"
    return storage_service.upload_bytes(data, filename, content_type)


def get_duration_seconds(audio_bytes):
    """
    Best-effort duration in seconds from file metadata (no external binary
    needed). Returns 0.0 if the format isn't recognized - duration is
    display-only, so this never blocks transcription.
    """
    try:
        from mutagen import File as MutagenFile
        f = MutagenFile(io.BytesIO(audio_bytes))
        if f is not None and f.info is not None:
            return float(f.info.length)
    except Exception:  # noqa: BLE001 - metadata parsing is best-effort only
        pass
    return 0.0
