/* =========================================================
   AI Meeting Generator - app.js
   Final bootstrap glue. Individual modules (ui.js, recorder.js,
   transcription.js, notes.js, export.js) self-initialize on
   DOMContentLoaded; this file just handles any last cross-module
   wiring and a friendly startup check.
   ========================================================= */

document.addEventListener("DOMContentLoaded", async () => {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    if (!data.success) {
      UI.error("Backend API did not respond as expected.");
    }
  } catch {
    UI.error("Could not reach the backend. Make sure the Flask server is running (python app.py).");
  }

  console.log(
    "%cAI Meeting Generator",
    "font-weight:bold;font-size:14px;color:#7c3aed;",
    "- frontend loaded."
  );
});
