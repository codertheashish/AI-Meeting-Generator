"""
Audio/video handling: validation, saving uploads, and converting to a
Whisper-friendly format (16kHz mono WAV) using FFmpeg.
"""
import os
import subprocess
import uuid
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {"wav", "mp3", "m4a", "webm", "ogg", "mp4", "mov", "mkv", "flac"}
MAX_FILE_SIZE_MB = 500


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file_storage, upload_dir):
    """Validate and persist an uploaded file. Returns the saved path or raises ValueError."""
    if not file_storage or file_storage.filename == "":
        raise ValueError("No file selected.")

    filename = secure_filename(file_storage.filename)
    if not allowed_file(filename):
        raise ValueError(
            f"Unsupported file type. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    os.makedirs(upload_dir, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    path = os.path.join(upload_dir, unique_name)
    file_storage.save(path)

    size_mb = os.path.getsize(path) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        os.remove(path)
        raise ValueError(f"File too large ({size_mb:.1f}MB). Max is {MAX_FILE_SIZE_MB}MB.")

    return path


def convert_to_wav(input_path, output_dir):
    """Convert any audio/video file to 16kHz mono WAV using ffmpeg. Returns output path."""
    os.makedirs(output_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base}_converted.wav")

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        output_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except FileNotFoundError:
        raise RuntimeError(
            "FFmpeg is not installed or not on PATH. Install it from https://ffmpeg.org/download.html"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("Audio conversion timed out.")

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg conversion failed: {result.stderr[-500:]}")

    return output_path


def get_duration_seconds(file_path):
    """Return media duration in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", file_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return float(result.stdout.strip())
    except (FileNotFoundError, ValueError, subprocess.TimeoutExpired):
        return 0.0


def is_ffmpeg_available():
    """Quick check used at app startup / by the Settings panel - does not raise."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=10)
        subprocess.run(["ffprobe", "-version"], capture_output=True, timeout=10)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False
