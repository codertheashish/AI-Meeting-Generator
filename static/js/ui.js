/* =========================================================
   AI Meeting Generator - ui.js
   Shared UI helpers: toasts, mobile nav, loaders, formatting.
   Exposes a global `UI` object used by the other JS modules.
   ========================================================= */

// Shared global app state, used across recorder.js / transcription.js / notes.js / export.js / app.js
window.AppState = {
  currentMeetingId: null,
  currentMeeting: null,   // full meeting object once notes are generated
  lastSegments: [],
};

const UI = (() => {
  const toastContainer = document.getElementById("toastContainer");

  function toast(message, type = "info", timeout = 4000) {
    const el = document.createElement("div");
    el.className = `toast ${type}`;
    const icon =
      type === "success" ? "fa-circle-check" :
      type === "error" ? "fa-circle-exclamation" : "fa-circle-info";
    el.innerHTML = `<i class="fa-solid ${icon}"></i><span></span>`;
    el.querySelector("span").textContent = message;
    toastContainer.appendChild(el);
    setTimeout(() => {
      el.style.opacity = "0";
      el.style.transition = "opacity .25s ease";
      setTimeout(() => el.remove(), 250);
    }, timeout);
  }

  function success(msg) { toast(msg, "success"); }
  function error(msg) { toast(msg, "error", 6000); }
  function info(msg) { toast(msg, "info"); }

  function setLoading(el, isLoading) {
    if (!el) return;
    el.style.display = isLoading ? "inline-flex" : "none";
  }

  function setButtonBusy(btn, isBusy, busyLabel) {
    if (!btn) return;
    if (isBusy) {
      btn.dataset.originalHtml = btn.innerHTML;
      btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ${busyLabel || "Working..."}`;
      btn.disabled = true;
    } else {
      if (btn.dataset.originalHtml) btn.innerHTML = btn.dataset.originalHtml;
      btn.disabled = false;
    }
  }

  function formatTime(totalSeconds) {
    totalSeconds = Math.max(0, Math.floor(totalSeconds || 0));
    const h = String(Math.floor(totalSeconds / 3600)).padStart(2, "0");
    const m = String(Math.floor((totalSeconds % 3600) / 60)).padStart(2, "0");
    const s = String(totalSeconds % 60).padStart(2, "0");
    return `${h}:${m}:${s}`;
  }

  function formatDate(isoString) {
    if (!isoString) return "-";
    try {
      const d = new Date(isoString);
      if (isNaN(d.getTime())) return isoString;
      return d.toLocaleString(undefined, {
        year: "numeric", month: "short", day: "numeric",
        hour: "2-digit", minute: "2-digit",
      });
    } catch {
      return isoString;
    }
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str ?? "";
    return div.innerHTML;
  }

  function statusLabel(status) {
    const map = {
      created: "Created",
      recorded: "Recorded",
      uploaded: "Uploaded",
      transcribed: "Transcribed",
      notes_generated: "Notes Ready",
    };
    return map[status] || status || "Unknown";
  }

  // ---- Mobile nav toggle ----
  function initNav() {
    const nav = document.getElementById("mainNav");
    const btn = document.getElementById("hamburgerBtn");
    if (!nav || !btn) return;
    btn.addEventListener("click", () => nav.classList.toggle("open"));

    document.querySelectorAll(".nav-link").forEach((link) => {
      link.addEventListener("click", () => {
        document.querySelectorAll(".nav-link").forEach((l) => l.classList.remove("active"));
        link.classList.add("active");
        nav.classList.remove("open");
      });
    });
  }

  document.addEventListener("DOMContentLoaded", initNav);

  return { toast, success, error, info, setLoading, setButtonBusy, formatTime, formatDate, escapeHtml, statusLabel };
})();
