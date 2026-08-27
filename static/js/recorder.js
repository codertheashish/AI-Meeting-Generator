/* =========================================================
   AI Meeting Generator - recorder.js
   Live microphone recording using MediaRecorder + Web Audio API
   waveform visualization. Uploads the finished recording to
   POST /api/record, then kicks off transcription automatically.
   ========================================================= */

const Recorder = (() => {
  let mediaRecorder = null;
  let mediaStream = null;
  let audioChunks = [];
  let audioContext = null;
  let analyser = null;
  let animationId = null;
  let isRecording = false;
  let isPaused = false;
  let elapsedSeconds = 0;
  let timerInterval = null;
  let lastBlob = null;

  const els = {};

  function cacheEls() {
    els.micBtn = document.getElementById("micBtn");
    els.startBtn = document.getElementById("startRecBtn");
    els.stopBtn = document.getElementById("stopRecBtn");
    els.pauseBtn = document.getElementById("pauseRecBtn");
    els.deleteBtn = document.getElementById("deleteRecBtn");
    els.timer = document.getElementById("recTimer");
    els.statusPill = document.getElementById("recStatusPill");
    els.canvas = document.getElementById("waveCanvas");
    els.heroStartBtn = document.getElementById("heroStartRecordingBtn");
  }

  // ---------------- Waveform ----------------
  function drawIdleWave() {
    const canvas = els.canvas;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const w = (canvas.width = canvas.clientWidth);
    const h = (canvas.height = canvas.clientHeight);
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = "#d9d4f5";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, h / 2);
    ctx.lineTo(w, h / 2);
    ctx.stroke();
  }

  function drawLiveWave() {
    const canvas = els.canvas;
    if (!canvas || !analyser) return;
    const ctx = canvas.getContext("2d");
    const w = (canvas.width = canvas.clientWidth);
    const h = (canvas.height = canvas.clientHeight);
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    function render() {
      animationId = requestAnimationFrame(render);
      analyser.getByteFrequencyData(dataArray);
      ctx.clearRect(0, 0, w, h);

      const barCount = 48;
      const step = Math.floor(bufferLength / barCount);
      const barWidth = w / barCount;
      const grad = ctx.createLinearGradient(0, 0, w, 0);
      grad.addColorStop(0, "#6d28d9");
      grad.addColorStop(0.5, "#4f46e5");
      grad.addColorStop(1, "#3b82f6");
      ctx.fillStyle = grad;

      for (let i = 0; i < barCount; i++) {
        const value = dataArray[i * step] || 0;
        const barHeight = Math.max(3, (value / 255) * h * 0.9);
        const x = i * barWidth;
        const y = (h - barHeight) / 2;
        const radius = Math.min(3, barWidth / 3);
        roundRect(ctx, x + barWidth * 0.15, y, barWidth * 0.7, barHeight, radius);
      }
    }
    render();
  }

  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
    ctx.fill();
  }

  function stopWaveAnimation() {
    if (animationId) cancelAnimationFrame(animationId);
    animationId = null;
    drawIdleWave();
  }

  // ---------------- Timer ----------------
  function startTimer() {
    timerInterval = setInterval(() => {
      if (!isPaused) {
        elapsedSeconds++;
        els.timer.textContent = UI.formatTime(elapsedSeconds);
      }
    }, 1000);
  }

  function stopTimer() {
    clearInterval(timerInterval);
    timerInterval = null;
  }

  // ---------------- Recording control ----------------
  async function startRecording() {
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      UI.error("Microphone permission denied. Please allow microphone access to record.");
      return;
    }

    audioChunks = [];
    elapsedSeconds = 0;
    isPaused = false;
    lastBlob = null;
    els.timer.textContent = "00:00:00";

    const mimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "";
    try {
      mediaRecorder = mimeType
        ? new MediaRecorder(mediaStream, { mimeType })
        : new MediaRecorder(mediaStream);
    } catch (err) {
      UI.error("Recording is not supported in this browser.");
      return;
    }

    mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = handleRecordingStopped;

    mediaRecorder.start();
    isRecording = true;

    // Web Audio API analyser for live waveform
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioContext.createMediaStreamSource(mediaStream);
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);
    drawLiveWave();

    startTimer();
    updateButtonStates();
    els.statusPill.textContent = "Recording...";
    els.statusPill.classList.add("live");
    els.micBtn.classList.add("recording");
    UI.success("Recording started.");
  }

  function togglePause() {
    if (!mediaRecorder) return;
    if (!isPaused) {
      mediaRecorder.pause();
      isPaused = true;
      els.pauseBtn.innerHTML = '<i class="fa-solid fa-play"></i> Resume';
      els.statusPill.textContent = "Paused";
      els.statusPill.classList.remove("live");
    } else {
      mediaRecorder.resume();
      isPaused = false;
      els.pauseBtn.innerHTML = '<i class="fa-solid fa-pause"></i> Pause';
      els.statusPill.textContent = "Recording...";
      els.statusPill.classList.add("live");
    }
  }

  function stopRecording() {
    if (!mediaRecorder || !isRecording) return;
    mediaRecorder.stop();
    isRecording = false;
    isPaused = false;
    stopTimer();
    stopWaveAnimation();
    if (mediaStream) mediaStream.getTracks().forEach((t) => t.stop());
    if (audioContext) audioContext.close();
    els.statusPill.textContent = "Processing...";
    els.statusPill.classList.remove("live");
    els.micBtn.classList.remove("recording");
    updateButtonStates();
  }

  function handleRecordingStopped() {
    lastBlob = new Blob(audioChunks, { type: "audio/webm" });
    els.statusPill.textContent = "Recorded";
    UI.success(`Recording saved (${UI.formatTime(elapsedSeconds)}). Uploading...`);
    uploadRecording(lastBlob);
  }

  function deleteRecording() {
    if (isRecording) stopRecording();
    lastBlob = null;
    audioChunks = [];
    elapsedSeconds = 0;
    els.timer.textContent = "00:00:00";
    els.statusPill.textContent = "Idle";
    els.statusPill.classList.remove("live");
    updateButtonStates();
    UI.info("Recording discarded.");
  }

  function updateButtonStates() {
    els.startBtn.disabled = isRecording;
    els.stopBtn.disabled = !isRecording;
    els.pauseBtn.disabled = !isRecording;
    els.deleteBtn.disabled = isRecording ? false : !lastBlob && elapsedSeconds === 0;
    els.pauseBtn.innerHTML = '<i class="fa-solid fa-pause"></i> Pause';
  }

  // ---------------- Upload finished recording ----------------
  async function uploadRecording(blob) {
    const formData = new FormData();
    formData.append("audio", blob, "recording.webm");
    formData.append("title", `Live Recording - ${new Date().toLocaleString()}`);

    try {
      const res = await fetch("/api/record", { method: "POST", body: formData });
      const data = await res.json();
      if (!data.success) throw new Error(data.error || "Upload failed.");

      window.AppState.currentMeetingId = data.meeting_id;
      els.statusPill.textContent = "Idle";
      UI.success("Recording uploaded. Starting transcription...");
      if (window.Transcription) {
        window.Transcription.transcribeMeeting(data.meeting_id);
      }
      if (window.NotesModule) window.NotesModule.refreshMeetingsList();
    } catch (err) {
      els.statusPill.textContent = "Idle";
      UI.error(`Could not upload recording: ${err.message}`);
    }
  }

  function init() {
    cacheEls();
    if (!els.canvas) return;
    drawIdleWave();
    window.addEventListener("resize", () => {
      if (!isRecording) drawIdleWave();
    });

    const start = () => {
      if (!isRecording) startRecording();
    };

    els.micBtn.addEventListener("click", () => {
      isRecording ? stopRecording() : startRecording();
    });
    els.startBtn.addEventListener("click", start);
    els.stopBtn.addEventListener("click", stopRecording);
    els.pauseBtn.addEventListener("click", togglePause);
    els.deleteBtn.addEventListener("click", deleteRecording);
    if (els.heroStartBtn) els.heroStartBtn.addEventListener("click", start);

    updateButtonStates();
  }

  document.addEventListener("DOMContentLoaded", init);

  return { startRecording, stopRecording };
})();
