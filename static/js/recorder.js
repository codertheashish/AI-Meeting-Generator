/* recorder.js — microphone capture, waveform visualization, recording timer */

const Recorder = (() => {
  let mediaRecorder = null;
  let mediaStream = null;
  let audioChunks = [];
  let timerInterval = null;
  let elapsedSeconds = 0;
  let isPaused = false;
  let audioContext, analyser, sourceNode, animationId;

  const micBtn = document.getElementById("mic-btn");
  const pulseRing = document.getElementById("pulse-ring");
  const timerEl = document.getElementById("recording-timer");
  const statusEl = document.getElementById("recording-status");
  const waveformCanvas = document.getElementById("waveform");
  const canvasCtx = waveformCanvas.getContext("2d");

  const startBtn = document.getElementById("start-recording-btn");
  const pauseBtn = document.getElementById("pause-recording-btn");
  const stopBtn = document.getElementById("stop-recording-btn");
  const deleteBtn = document.getElementById("delete-recording-btn");

  function resizeCanvas() {
    const rect = waveformCanvas.getBoundingClientRect();
    waveformCanvas.width = rect.width * devicePixelRatio;
    waveformCanvas.height = rect.height * devicePixelRatio;
  }
  window.addEventListener("resize", resizeCanvas);

  async function start() {
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      UI.toast("Microphone permission denied. Please allow microphone access to record.", "error");
      return;
    }

    resizeCanvas();
    audioChunks = [];
    elapsedSeconds = 0;
    isPaused = false;

    const mimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "";
    mediaRecorder = new MediaRecorder(mediaStream, mimeType ? { mimeType } : undefined);

    mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunks.push(e.data); };
    mediaRecorder.onstop = handleStop;

    mediaRecorder.start(250);
    setupVisualizer();
    startTimer();
    updateUIRecording(true);
  }

  function setupVisualizer() {
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    sourceNode = audioContext.createMediaStreamSource(mediaStream);
    sourceNode.connect(analyser);
    drawWaveform();
  }

  function drawWaveform() {
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    function render() {
      animationId = requestAnimationFrame(render);
      analyser.getByteFrequencyData(dataArray);

      const w = waveformCanvas.width;
      const h = waveformCanvas.height;
      canvasCtx.clearRect(0, 0, w, h);

      const barWidth = (w / bufferLength) * 2.2;
      let x = 0;
      const gradient = canvasCtx.createLinearGradient(0, 0, w, 0);
      gradient.addColorStop(0, "#7c3aed");
      gradient.addColorStop(1, "#3b82f6");
      canvasCtx.fillStyle = gradient;

      for (let i = 0; i < bufferLength; i++) {
        const barHeight = (dataArray[i] / 255) * h * 0.9;
        canvasCtx.fillRect(x, (h - barHeight) / 2, barWidth, barHeight);
        x += barWidth + 2;
      }
    }
    render();
  }

  function stopVisualizer() {
    if (animationId) cancelAnimationFrame(animationId);
    if (audioContext) audioContext.close();
    canvasCtx.clearRect(0, 0, waveformCanvas.width, waveformCanvas.height);
  }

  function startTimer() {
    timerInterval = setInterval(() => {
      if (!isPaused) {
        elapsedSeconds++;
        timerEl.textContent = UI.formatTime(elapsedSeconds);
      }
    }, 1000);
  }

  function stopTimer() {
    clearInterval(timerInterval);
  }

  function pauseResume() {
    if (!mediaRecorder) return;
    if (isPaused) {
      mediaRecorder.resume();
      isPaused = false;
      pauseBtn.innerHTML = '<i class="fa-solid fa-pause"></i> Pause';
      statusEl.textContent = "Recording";
      statusEl.className = "status-pill recording";
    } else {
      mediaRecorder.pause();
      isPaused = true;
      pauseBtn.innerHTML = '<i class="fa-solid fa-play"></i> Resume';
      statusEl.textContent = "Paused";
      statusEl.className = "status-pill";
    }
  }

  function stop() {
    if (!mediaRecorder || mediaRecorder.state === "inactive") return;
    mediaRecorder.stop();
    mediaStream.getTracks().forEach((t) => t.stop());
    stopTimer();
    stopVisualizer();
  }

  function discard() {
    stop();
    audioChunks = [];
    elapsedSeconds = 0;
    timerEl.textContent = "00:00:00";
    updateUIRecording(false);
    statusEl.textContent = "Ready";
    statusEl.className = "status-pill";
  }

  async function handleStop() {
    updateUIRecording(false);
    if (audioChunks.length === 0) return;
    const blob = new Blob(audioChunks, { type: "audio/webm" });
    statusEl.textContent = "Uploading...";
    statusEl.className = "status-pill processing";
    await App.processRecordedAudio(blob, elapsedSeconds);
  }

  function updateUIRecording(recording) {
    if (recording) {
      micBtn.classList.add("recording");
      pulseRing.classList.add("active");
      startBtn.classList.add("hidden");
      pauseBtn.classList.remove("hidden");
      stopBtn.classList.remove("hidden");
      deleteBtn.classList.remove("hidden");
      statusEl.textContent = "Recording";
      statusEl.className = "status-pill recording";
    } else {
      micBtn.classList.remove("recording");
      pulseRing.classList.remove("active");
      startBtn.classList.remove("hidden");
      pauseBtn.classList.add("hidden");
      pauseBtn.innerHTML = '<i class="fa-solid fa-pause"></i> Pause';
      stopBtn.classList.add("hidden");
      deleteBtn.classList.add("hidden");
    }
  }

  startBtn.addEventListener("click", start);
  micBtn.addEventListener("click", () => (mediaRecorder && mediaRecorder.state === "recording" ? null : start()));
  pauseBtn.addEventListener("click", pauseResume);
  stopBtn.addEventListener("click", stop);
  deleteBtn.addEventListener("click", discard);

  return { start, stop };
})();
