/* =========================================================
   AI Meeting Generator - transcription.js
   Handles: file upload (drag & drop or click), POST /api/upload,
   POST /api/transcribe, and rendering the live transcript table.
   ========================================================= */

const Transcription = (() => {
  const ALLOWED_EXT = ["wav", "mp3", "m4a", "aac", "ogg", "flac", "webm", "mp4", "mov", "mkv", "avi"];

  const els = {};

  function cacheEls() {
    els.dropzone = document.getElementById("uploadDropzone");
    els.fileInput = document.getElementById("fileInput");
    els.transcriptBody = document.getElementById("transcriptBody");
    els.transcribeLoader = document.getElementById("transcribeLoader");
    els.statusPill = document.getElementById("recStatusPill");
    els.heroUploadBtn = document.getElementById("heroUploadBtn");
  }

  function isAllowed(filename) {
    const ext = filename.split(".").pop().toLowerCase();
    return ALLOWED_EXT.includes(ext);
  }

  async function handleFile(file) {
    if (!file) return;
    if (!isAllowed(file.name)) {
      UI.error(`Unsupported file type. Allowed: ${ALLOWED_EXT.join(", ")}`);
      return;
    }
    if (file.size > 500 * 1024 * 1024) {
      UI.error("File is too large. Maximum size is 500MB.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("title", file.name.replace(/\.[^/.]+$/, ""));

    UI.info(`Uploading "${file.name}"...`);
    els.statusPill.textContent = "Uploading...";

    try {
      const res = await fetch("/api/upload", { method: "POST", body: formData });
      const data = await res.json();
      if (!data.success) throw new Error(data.error || "Upload failed.");

      window.AppState.currentMeetingId = data.meeting_id;
      UI.success("File uploaded. Starting transcription...");
      transcribeMeeting(data.meeting_id);
      if (window.NotesModule) window.NotesModule.refreshMeetingsList();
    } catch (err) {
      UI.error(`Upload failed: ${err.message}`);
      els.statusPill.textContent = "Idle";
    }
  }

  async function transcribeMeeting(meetingId) {
    if (!meetingId) {
      UI.error("No meeting selected to transcribe.");
      return;
    }
    UI.setLoading(els.transcribeLoader, true);
    els.statusPill.textContent = "Transcribing...";

    try {
      const res = await fetch("/api/transcribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ meeting_id: meetingId }),
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.error || "Transcription failed.");

      window.AppState.lastSegments = data.segments || [];
      renderTranscript(data.segments || []);
      if (window.NotesModule) window.NotesModule.renderSpeakers(data.speakers || []);
      UI.success(`Transcription complete (${data.language || "auto"}, ${UI.formatTime(data.duration)}).`);
      els.statusPill.textContent = "Transcribed";
      if (window.NotesModule) window.NotesModule.refreshMeetingsList();
    } catch (err) {
      UI.error(`Transcription failed: ${err.message}`);
      els.statusPill.textContent = "Idle";
    } finally {
      UI.setLoading(els.transcribeLoader, false);
    }
  }

  function speakerClass(name, speakerOrder) {
    let idx = speakerOrder.indexOf(name);
    if (idx === -1) {
      speakerOrder.push(name);
      idx = speakerOrder.length - 1;
    }
    return `speaker-${idx % 6}`;
  }

  function renderTranscript(segments) {
    if (!els.transcriptBody) return;
    if (!segments || segments.length === 0) {
      els.transcriptBody.innerHTML = `<tr class="empty-row"><td colspan="3">No transcript available.</td></tr>`;
      return;
    }
    const speakerOrder = [];
    els.transcriptBody.innerHTML = segments
      .map((seg) => {
        const ts = UI.formatTime(seg.start || 0);
        const cls = speakerClass(seg.speaker || "Unknown", speakerOrder);
        return `
          <tr>
            <td>${ts}</td>
            <td><span class="speaker-tag ${cls}">${UI.escapeHtml(seg.speaker || "Unknown")}</span></td>
            <td>${UI.escapeHtml(seg.text || "")}</td>
          </tr>`;
      })
      .join("");
  }

  function initDropzone() {
    if (!els.dropzone) return;

    els.dropzone.addEventListener("click", (e) => {
      // label already triggers the hidden input, avoid double-trigger
    });

    els.fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files[0]) handleFile(e.target.files[0]);
      e.target.value = "";
    });

    ["dragenter", "dragover"].forEach((evt) => {
      els.dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        e.stopPropagation();
        els.dropzone.classList.add("dragover");
      });
    });

    ["dragleave", "drop"].forEach((evt) => {
      els.dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        e.stopPropagation();
        els.dropzone.classList.remove("dragover");
      });
    });

    els.dropzone.addEventListener("drop", (e) => {
      const file = e.dataTransfer.files && e.dataTransfer.files[0];
      if (file) handleFile(file);
    });

    if (els.heroUploadBtn) {
      els.heroUploadBtn.addEventListener("click", () => {
        els.dropzone.scrollIntoView({ behavior: "smooth", block: "center" });
        els.fileInput.click();
      });
    }
  }

  function init() {
    cacheEls();
    initDropzone();
  }

  document.addEventListener("DOMContentLoaded", init);

  return { transcribeMeeting, renderTranscript };
})();

window.Transcription = Transcription;
