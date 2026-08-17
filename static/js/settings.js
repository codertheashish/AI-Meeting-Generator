/* settings.js — read-only configuration panel + startup config-warning banner */

const Settings = (() => {
  const grid = document.getElementById("settings-grid");
  let loaded = false;

  function statusRow(label, value, ok) {
    return `
      <div class="settings-item">
        <div class="settings-item-label">${UI.escapeHtml(label)}</div>
        <div class="settings-item-value">
          ${ok !== undefined ? `<span class="status-dot ${ok ? "ok" : "warn"}"></span>` : ""}
          ${UI.escapeHtml(value)}
        </div>
      </div>
    `;
  }

  async function load(force = false) {
    if (loaded && !force) return;
    try {
      const res = await fetch("/api/settings");
      if (!res.ok) throw new Error(`Request failed (${res.status})`);
      const cfg = await res.json();
      render(cfg);
      loaded = true;
      maybeShowBanner(cfg);
    } catch (err) {
      grid.innerHTML = `<p class="empty-state">Couldn't load settings: ${UI.escapeHtml(err.message)}</p>`;
    }
  }

  function render(cfg) {
    grid.innerHTML = [
      statusRow("Speech-to-Text Engine", "Faster-Whisper (local)"),
      statusRow("Whisper Model", `${cfg.whisper_model} (${cfg.whisper_device})`),
      statusRow("AI Analysis Provider", "OpenRouter"),
      statusRow("OpenRouter Model", cfg.openrouter_model),
      statusRow("OpenRouter API Key", cfg.openrouter_key_configured ? "Configured" : "Not set", cfg.openrouter_key_configured),
      statusRow("FFmpeg", cfg.ffmpeg_available ? "Available" : "Not found on PATH", cfg.ffmpeg_available),
      statusRow("Email (SMTP)", cfg.mail_configured ? "Configured" : "Not set", cfg.mail_configured),
    ].join("");
  }

  function maybeShowBanner(cfg) {
    const problems = [];
    if (!cfg.ffmpeg_available) {
      problems.push('FFmpeg is not installed — <a href="https://ffmpeg.org/download.html" target="_blank" rel="noopener">install it</a> to enable recording/upload transcription.');
    }
    if (!cfg.openrouter_key_configured) {
      problems.push('OpenRouter API key is missing — add OPENROUTER_API_KEY to your .env file to enable AI notes.');
    }
    if (problems.length) {
      UI.showConfigBanner('<i class="fa-solid fa-triangle-exclamation"></i> ' + problems.join(' &nbsp;•&nbsp; '));
    }
  }

  document.addEventListener("DOMContentLoaded", () => load());

  return { load };
})();
