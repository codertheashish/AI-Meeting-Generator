"""
audio_service.py
-----------------
Handles uploaded-file validation and converts audio/video files into a
Whisper-friendly 16kHz mono WAV using FFmpeg (via subprocess - FFmpeg
must be installed and available on PATH).
"""

import os
import subprocess
import shutil
import uuid

ALLOWED_EXTENSIONS = {
    "wav", "mp3", "m4a", "aac", "ogg", "flac", "webm",  # audio
    "mp4", "mov", "mkv", "avi",                          # video (audio track extracted)
}
MAX_FILE_SIZE_MB = 500


class AudioServiceError(Exception):
    pass


def is_allowed_file(filename):
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def validate_upload(file_storage):
    """Validate a Flask FileStorage object before saving to disk."""
    if not file_storage or file_storage.filename == "":
        raise AudioServiceError("No file was selected.")

    if not is_allowed_file(file_storage.filename):
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise AudioServiceError(f"Unsupported file type. Allowed types: {allowed}")


def save_upload(file_storage, upload_dir):
    """Save with a unique filename to avoid collisions; returns the saved path."""
    os.makedirs(upload_dir, exist_ok=True)
    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    dest_path = os.path.join(upload_dir, unique_name)
    file_storage.save(dest_path)
    return dest_path


def ffmpeg_available():
    return shutil.which("ffmpeg") is not None


def convert_to_wav(src_path, upload_dir):
    """
    Converts any supported audio/video file to 16kHz mono WAV using FFmpeg.
    Returns the path to the converted file. If FFmpeg isn't installed,
    raises a friendly error (Whisper can still handle some formats directly,
    but WAV conversion is far more reliable).
    """
    if not ffmpeg_available():
        raise AudioServiceError(
            "FFmpeg is not installed or not on PATH. Install it from https://ffmpeg.org/download.html "
            "and make sure the 'ffmpeg' command works in your terminal."
        )

    out_path = os.path.join(upload_dir, f"{uuid.uuid4().hex}.wav")
    cmd = [
        "ffmpeg", "-y", "-i", src_path,
        "-ac", "1", "-ar", "16000", "-vn",
        out_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired as exc:
        raise AudioServiceError("Audio conversion timed out.") from exc

    if result.returncode != 0 or not os.path.exists(out_path):
        raise AudioServiceError(f"FFmpeg conversion failed: {result.stderr[-500:]}")

    return out_path


def get_audio_duration_seconds(wav_path):
    """Uses ffprobe (ships with FFmpeg) to read duration in seconds."""
    if not shutil.which("ffprobe"):
        return 0
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", wav_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return int(float(result.stdout.strip()))
    except (subprocess.TimeoutExpired, ValueError):
        return 0
