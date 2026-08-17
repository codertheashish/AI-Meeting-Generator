"""Recording upload, transcription, and AI note-generation endpoints."""
import os
import traceback

from flask import Blueprint, current_app, jsonify, request

from extensions import current_user_id
from models import database as db
from services import audio_service, whisper_service, ai_service, speaker_service

transcription_bp = Blueprint("transcription", __name__)


def _upload_dir():
    return current_app.config["UPLOAD_DIR"]


@transcription_bp.route("/api/record", methods=["POST"])
def save_recording():
    """
    Accepts a recorded audio blob from the browser's MediaRecorder API
    (multipart/form-data, field name 'audio') and stores it as a new meeting.
    """
    if "audio" not in request.files:
        return jsonify({"error": "No audio data received."}), 400

    title = request.form.get("title", "Recorded Meeting")
    try:
        saved_path = audio_service.save_upload(request.files["audio"], _upload_dir())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    meeting_id = db.create_meeting(title=title, audio_file=saved_path, user_id=current_user_id())
    return jsonify({"meeting_id": meeting_id, "audio_file": saved_path})


@transcription_bp.route("/api/upload", methods=["POST"])
def upload_meeting():
    """Accepts an uploaded audio/video file (multipart/form-data, field name 'file')."""
    if "file" not in request.files:
        return jsonify({"error": "No file part in the request."}), 400

    title = request.form.get("title") or request.files["file"].filename
    try:
        saved_path = audio_service.save_upload(request.files["file"], _upload_dir())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    meeting_id = db.create_meeting(title=title, audio_file=saved_path, user_id=current_user_id())
    return jsonify({"meeting_id": meeting_id, "audio_file": saved_path})


@transcription_bp.route("/api/transcribe", methods=["POST"])
def transcribe():
    """
    Body: { "meeting_id": <int> }
    Converts the stored audio to WAV, runs Whisper, saves the transcript,
    and returns speaker-labeled rows for the live transcription panel.
    """
    data = request.get_json(force=True, silent=True) or {}
    meeting_id = data.get("meeting_id")
    meeting = db.get_meeting(meeting_id, user_id=current_user_id()) if meeting_id else None
    if not meeting:
        return jsonify({"error": "Invalid or missing meeting_id."}), 400
    if not meeting.get("audio_file") or not os.path.exists(meeting["audio_file"]):
        return jsonify({"error": "Audio file not found for this meeting."}), 400

    try:
        wav_path = audio_service.convert_to_wav(meeting["audio_file"], _upload_dir())
        duration = audio_service.get_duration_seconds(wav_path)
        result = whisper_service.transcribe_audio(wav_path)
    except RuntimeError as exc:
        # Covers: FFmpeg missing/failed, invalid audio, and Faster-Whisper load/inference errors.
        return jsonify({"error": str(exc)}), 502
    except Exception:  # noqa: BLE001
        current_app.logger.error(traceback.format_exc())
        return jsonify({"error": "Unexpected error during transcription."}), 500

    # Speaker identification is optional/best-effort - see speaker_service.py.
    # Faster-Whisper does NOT perform diarization; this only detects explicit
    # "Name: text" labels already present in the audio's speech, if any.
    labeled = speaker_service.label_segments_with_speakers(result["segments"])
    display_rows = speaker_service.format_transcript_for_display(labeled)
    stats = speaker_service.compute_speaking_stats(labeled)

    db.update_meeting(meeting_id, transcript=result["text"], duration=round(duration), status="transcribed")
    db.replace_speakers(meeting_id, stats)

    return jsonify({
        "meeting_id": meeting_id,
        "transcript": result["text"],
        "transcript_rows": display_rows,
        "speakers": stats,
        "duration": round(duration),
    })


@transcription_bp.route("/api/analyze", methods=["POST"])
@transcription_bp.route("/api/generate-notes", methods=["POST"])
def generate_notes():
    """
    Body: { "meeting_id": <int> }
    Sends the stored transcript to the LLM and persists the structured notes.
    (Both /api/analyze and /api/generate-notes point here since they're the
    same operation in this implementation.)
    """
    data = request.get_json(force=True, silent=True) or {}
    meeting_id = data.get("meeting_id")
    meeting = db.get_meeting(meeting_id, user_id=current_user_id()) if meeting_id else None
    if not meeting:
        return jsonify({"error": "Invalid or missing meeting_id."}), 400
    if not meeting.get("transcript"):
        return jsonify({"error": "This meeting has no transcript yet. Run /api/transcribe first."}), 400

    try:
        # This is the only place OpenRouter is called from - all HTTP details
        # live in services/ai_service.py so the provider can change later
        # without touching route code.
        notes = ai_service.generate_meeting_notes(meeting["transcript"])
    except RuntimeError as exc:
        # Covers: missing/invalid OPENROUTER_API_KEY, rate limits, model
        # unavailable, network errors, timeouts, and unparsable AI JSON.
        return jsonify({"error": str(exc), "retryable": True}), 502
    except Exception:  # noqa: BLE001
        current_app.logger.error(traceback.format_exc())
        return jsonify({"error": "Unexpected error during note generation.", "retryable": True}), 500

    db.update_meeting(
        meeting_id,
        summary=notes["summary"],
        key_highlights=notes["key_highlights"],
        decisions=notes["decisions"],
        follow_up_points=notes["follow_up_points"],
        status="completed",
    )
    db.replace_action_items(meeting_id, notes["action_items"])

    return jsonify({"meeting": db.get_meeting(meeting_id, user_id=current_user_id())})
