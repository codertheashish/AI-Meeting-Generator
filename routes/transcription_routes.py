"""
transcription_routes.py
------------------------
Endpoints covering the record -> upload -> transcribe -> analyze -> generate-notes
pipeline described in the project spec.
"""

import os
import json
from flask import Blueprint, request, jsonify, current_app

from models import database as db
from services import audio_service, whisper_service, ai_service, speaker_service

transcription_bp = Blueprint("transcription_bp", __name__)


def _upload_dir():
    return current_app.config["UPLOAD_FOLDER"]


@transcription_bp.route("/api/record", methods=["POST"])
def save_recording():
    """
    Accepts a recorded audio blob (multipart/form-data, field name 'audio')
    from the browser's MediaRecorder and stores it as a new meeting.
    """
    if "audio" not in request.files:
        return jsonify({"success": False, "error": "No audio data received from recorder."}), 400

    file_storage = request.files["audio"]
    title = request.form.get("title", "Live Recording")

    # Recorded blobs are typically webm; accept regardless of validate_upload's
    # extension whitelist by forcing a safe extension if missing.
    filename = file_storage.filename or "recording.webm"
    if "." not in filename:
        filename = "recording.webm"
    file_storage.filename = filename

    try:
        audio_service.validate_upload(file_storage)
        saved_path = audio_service.save_upload(file_storage, _upload_dir())
    except audio_service.AudioServiceError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    meeting_id = db.create_meeting(title=title, audio_file=saved_path)
    db.update_meeting(meeting_id, status="recorded")

    return jsonify({"success": True, "meeting_id": meeting_id, "audio_file": os.path.basename(saved_path)})


@transcription_bp.route("/api/upload", methods=["POST"])
def upload_meeting_file():
    """Accepts an uploaded audio/video meeting file (multipart/form-data, field 'file')."""
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file part in the request."}), 400

    file_storage = request.files["file"]
    title = request.form.get("title") or (file_storage.filename.rsplit(".", 1)[0] if file_storage.filename else "Uploaded Meeting")

    try:
        audio_service.validate_upload(file_storage)
        saved_path = audio_service.save_upload(file_storage, _upload_dir())
    except audio_service.AudioServiceError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    meeting_id = db.create_meeting(title=title, audio_file=saved_path)
    db.update_meeting(meeting_id, status="uploaded")

    return jsonify({"success": True, "meeting_id": meeting_id, "audio_file": os.path.basename(saved_path)})


@transcription_bp.route("/api/transcribe", methods=["POST"])
def transcribe_meeting():
    """
    Body JSON: {"meeting_id": int, "speaker_names": ["Sarah","John",...] (optional)}
    Converts audio -> WAV via FFmpeg, runs local Whisper, labels speakers,
    stores transcript + duration + speaker stats.
    """
    data = request.get_json(silent=True) or {}
    meeting_id = data.get("meeting_id")
    speaker_names = data.get("speaker_names")

    meeting = db.get_meeting(meeting_id) if meeting_id else None
    if not meeting:
        return jsonify({"success": False, "error": "Valid meeting_id is required."}), 400

    audio_path = meeting.get("audio_file")
    if not audio_path or not os.path.exists(audio_path):
        return jsonify({"success": False, "error": "No audio file found for this meeting."}), 400

    try:
        wav_path = audio_service.convert_to_wav(audio_path, _upload_dir())
    except audio_service.AudioServiceError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    try:
        result = whisper_service.transcribe_audio(wav_path)
    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 500

    if not result["text"]:
        return jsonify({"success": False, "error": "Transcription returned empty text. Try a clearer recording."}), 422

    labeled_segments = whisper_service.assign_speakers_round_robin(result["segments"], speaker_names)
    stats = speaker_service.compute_speaker_stats(labeled_segments)
    duration = audio_service.get_audio_duration_seconds(wav_path)

    db.update_meeting(
        meeting_id,
        transcript=result["text"],
        duration=duration,
        status="transcribed",
    )
    db.replace_speakers(meeting_id, stats)

    return jsonify({
        "success": True,
        "meeting_id": meeting_id,
        "transcript": result["text"],
        "segments": labeled_segments,
        "speakers": stats,
        "duration": duration,
        "language": result["language"],
    })


@transcription_bp.route("/api/analyze", methods=["POST"])
def analyze_meeting():
    """
    Body JSON: {"meeting_id": int}
    Lightweight re-check of the transcript + returns current speaker analytics.
    Useful for refreshing analytics without re-running full note generation.
    """
    data = request.get_json(silent=True) or {}
    meeting_id = data.get("meeting_id")
    meeting = db.get_full_meeting(meeting_id) if meeting_id else None
    if not meeting:
        return jsonify({"success": False, "error": "Valid meeting_id is required."}), 400

    if not meeting.get("transcript"):
        return jsonify({"success": False, "error": "This meeting has no transcript yet. Run /api/transcribe first."}), 400

    word_count = len(meeting["transcript"].split())
    return jsonify({
        "success": True,
        "meeting_id": meeting_id,
        "word_count": word_count,
        "speakers": meeting["speakers"],
        "duration": meeting.get("duration", 0),
    })


@transcription_bp.route("/api/generate-notes", methods=["POST"])
def generate_notes():
    """
    Body JSON: {"meeting_id": int}
    Sends the transcript to the LLM (via OpenRouter) and stores the
    structured notes: summary, action items, highlights, decisions.
    """
    data = request.get_json(silent=True) or {}
    meeting_id = data.get("meeting_id")
    meeting = db.get_meeting(meeting_id) if meeting_id else None
    if not meeting:
        return jsonify({"success": False, "error": "Valid meeting_id is required."}), 400

    transcript = meeting.get("transcript")
    if not transcript:
        return jsonify({"success": False, "error": "No transcript available. Please transcribe the meeting first."}), 400

    try:
        notes = ai_service.generate_meeting_notes(transcript)
    except ai_service.AIServiceError as exc:
        return jsonify({"success": False, "error": str(exc)}), 502

    db.update_meeting(
        meeting_id,
        summary=notes["summary"],
        key_highlights=json.dumps(notes["key_highlights"]),
        status="notes_generated",
    )
    db.replace_action_items(meeting_id, notes["action_items"])
    db.replace_decisions(meeting_id, notes["decisions"])

    # If the AI produced speaker names/percentages and we don't already have
    # diarization-based stats, use the AI's estimate as a fallback only.
    existing_speakers = db.get_speakers(meeting_id)
    if not existing_speakers and notes["speakers"]:
        normalized = [
            {
                "name": s.get("name", "Unknown"),
                "speaking_time": 0,
                "speaking_percentage": s.get("speaking_percentage", 0),
            }
            for s in notes["speakers"]
        ]
        db.replace_speakers(meeting_id, normalized)

    return jsonify({"success": True, "meeting": db.get_full_meeting(meeting_id)})
