/* app.js — API wrapper + top-level orchestration of the record→transcribe→analyze pipeline */

const Api = (() => {
  async function request(url, options = {}) {
    const res = await fetch(url, options);
    let data;
    try {
      data = await res.json();
    } catch {
      data = {};
    }
    if (res.status === 401 && data.login_required) {
      window.location.href = "/login";
      throw new Error("Please log in to continue.");
    }
    if (!res.ok) {
      throw new Error(data.error || `Request failed (${res.status})`);
    }
    return data;
  }

  return {
    uploadRecording: (blob, title) => {
      const fd = new FormData();
      fd.append("audio", blob, "recording.webm");
      fd.append("title", title);
      return request("/api/record", { method: "POST", body: fd });
    },
    uploadFile: (file, title) => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("title", title);
      return request("/api/upload", { method: "POST", body: fd });
    },
    transcribe: (meetingId) =>
      request("/api/transcribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ meeting_id: meetingId }),
      }),
    generateNotes: (meetingId) =>
      request("/api/generate-notes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ meeting_id: meetingId }),
      }),
    listMeetings: () => request("/api/meetings"),
    getMeeting: (id) => request(`/api/meetings/${id}`),
    deleteMeeting: (id) => request(`/api/meetings/${id}`, { method: "DELETE" }),
    updateActionItem: (id, fields) =>
      request(`/api/action-items/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fields),
      }),
    updateMeeting: (id, fields) =>
      request(`/api/meetings/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fields),
      }),
    sendEmail: (payload) =>
      request("/api/email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }),
  };
})();

const App = (() => {
  let currentMeetingId = null;
  let currentMeeting = null;

  const recordingStatus = document.getElementById("recording-status");
  const titleBar = document.getElementById("meeting-title-bar");
  const titleDisplay = document.getElementById("meeting-title-display");
  const titleText = document.getElementById("meeting-title-text");
  const titleEdit = document.getElementById("meeting-title-edit");
  const titleInput = document.getElementById("meeting-title-input");

  function showMeetingTitle(title) {
    titleText.textContent = title || "Untitled Meeting";
    titleBar.classList.remove("hidden");
    titleEdit.classList.add("hidden");
    titleDisplay.classList.remove("hidden");
  }

  function bindTitleEditor() {
    document.getElementById("edit-title-btn").addEventListener("click", () => {
      titleInput.value = titleText.textContent;
      titleDisplay.classList.add("hidden");
      titleEdit.classList.remove("hidden");
      titleInput.focus();
      titleInput.select();
    });

    document.getElementById("cancel-title-btn").addEventListener("click", () => {
      titleEdit.classList.add("hidden");
      titleDisplay.classList.remove("hidden");
    });

    async function saveTitle() {
      const newTitle = titleInput.value.trim();
      if (!newTitle) {
        UI.toast("Meeting title can't be empty.", "warning");
        return;
      }
      if (!currentMeetingId) return;
      try {
        const { meeting } = await Api.updateMeeting(currentMeetingId, { title: newTitle });
        currentMeeting = meeting;
        showMeetingTitle(meeting.title);
        UI.toast("Meeting renamed.", "success");
        Notes.loadHistory();
      } catch (err) {
        UI.toast("Couldn't rename meeting: " + err.message, "error");
      }
    }

    document.getElementById("save-title-btn").addEventListener("click", saveTitle);
    titleInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") saveTitle();
      if (e.key === "Escape") { titleEdit.classList.add("hidden"); titleDisplay.classList.remove("hidden"); }
    });
  }

  async function processRecordedAudio(blob, durationSeconds) {
    try {
      UI.showLoading("Uploading recording...");
      const title = `Meeting - ${new Date().toLocaleString()}`;
      const { meeting_id } = await Api.uploadRecording(blob, title);
      currentMeetingId = meeting_id;
      showMeetingTitle(title);
      recordingStatus.textContent = "Ready";
      recordingStatus.className = "status-pill";
      await runPipeline(meeting_id);
    } catch (err) {
      UI.hideLoading();
      recordingStatus.textContent = "Ready";
      recordingStatus.className = "status-pill";
      UI.toast("Upload failed: " + err.message, "error");
    }
  }

  async function processUploadedFile(file) {
    try {
      UI.showLoading("Uploading file...");
      const { meeting_id } = await Api.uploadFile(file, file.name);
      currentMeetingId = meeting_id;
      showMeetingTitle(file.name);
      await runPipeline(meeting_id);
    } catch (err) {
      UI.hideLoading();
      UI.toast("Upload failed: " + err.message, "error");
    }
  }

  async function runPipeline(meetingId) {
    Transcription.clear();
    Notes.clear();
    Transcription.setBadge("Transcribing...");

    try {
      UI.showLoading("Transcribing audio...");
      const transcribeResult = await Api.transcribe(meetingId);
      Transcription.render(transcribeResult.transcript_rows);
      Notes.renderSpeakers(transcribeResult.speakers);
      Transcription.setBadge("Analyzing with AI...");
    } catch (err) {
      Transcription.setBadge("Transcription Failed");
      UI.hideLoading();
      UI.toast(err.message || "Something went wrong transcribing this meeting.", "error");
      return;
    }

    await runAnalysis(meetingId);
  }

  async function runAnalysis(meetingId) {
    Transcription.setBadge("Analyzing with AI...");
    Notes.hideAnalysisError();
    try {
      UI.showLoading("Analyzing with AI (OpenRouter)...");
      const { meeting } = await Api.generateNotes(meetingId);
      currentMeeting = meeting;
      currentMeetingId = meeting.id;
      showMeetingTitle(meeting.title);
      Notes.renderMeetingNotes(meeting);
      Transcription.setBadge("Complete");
      UI.toast("Meeting notes generated successfully!", "success");
      Notes.loadHistory();
    } catch (err) {
      Transcription.setBadge("Analysis Failed");
      const message = err.message || "Something went wrong generating AI notes for this meeting.";
      Notes.showAnalysisError(message);
      UI.toast(message, "error");
    } finally {
      UI.hideLoading();
    }
  }

  async function loadMeeting(meetingId) {
    try {
      UI.showLoading("Loading meeting...");
      const { meeting } = await Api.getMeeting(meetingId);
      currentMeetingId = meeting.id;
      currentMeeting = meeting;
      showMeetingTitle(meeting.title);
      Notes.renderMeetingNotes(meeting);

      if (meeting.transcript) {
        // Rebuild simple transcript rows (single timestamp per speaker isn't
        // stored separately from the raw transcript once loaded from history,
        // so we show the full transcript as one entry per speaker turn).
        const rows = meeting.transcript.split(/\n+/).filter(Boolean).map((line, i) => ({
          timestamp: UI.formatTime(i * 5),
          speaker: meeting.speakers[0]?.name || "Speaker",
          text: line,
        }));
        Transcription.clear();
        Transcription.render(rows);
        Transcription.setBadge("Loaded");
      }
      document.getElementById("recording-card").scrollIntoView({ behavior: "smooth" });
    } catch (err) {
      UI.toast("Couldn't load meeting: " + err.message, "error");
    } finally {
      UI.hideLoading();
    }
  }

  function bindUploadUI() {
    const dropzone = document.getElementById("upload-dropzone");
    const fileInput = document.getElementById("file-input");
    const heroUploadBtn = document.getElementById("hero-upload-meeting");
    const heroRecordBtn = document.getElementById("hero-start-recording");

    fileInput.addEventListener("change", (e) => {
      if (e.target.files[0]) processUploadedFile(e.target.files[0]);
    });

    dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
    dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
      if (e.dataTransfer.files[0]) processUploadedFile(e.dataTransfer.files[0]);
    });

    heroUploadBtn.addEventListener("click", () => {
      document.getElementById("recording-card").scrollIntoView({ behavior: "smooth" });
      fileInput.click();
    });
    heroRecordBtn.addEventListener("click", () => {
      document.getElementById("recording-card").scrollIntoView({ behavior: "smooth" });
      Recorder.start();
    });
  }

  function bindRetryButton() {
    document.getElementById("retry-analysis-btn").addEventListener("click", () => {
      if (!currentMeetingId) {
        UI.toast("No meeting to retry. Record or upload one first.", "warning");
        return;
      }
      runAnalysis(currentMeetingId);
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    bindUploadUI();
    bindRetryButton();
    bindTitleEditor();
    Notes.loadHistory();
  });

  return {
    processRecordedAudio,
    processUploadedFile,
    loadMeeting,
    runAnalysis,
    get currentMeetingId() { return currentMeetingId; },
    get currentMeeting() { return currentMeeting; },
  };
})();
