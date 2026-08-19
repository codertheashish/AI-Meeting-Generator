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
      statusRow("Database (Postgres)", cfg.database_configured ? "Connected" : "Not set", cfg.database_configured),
      statusRow("Audio Storage (Vercel Blob)", cfg.blob_storage_configured ? "Configured" : "Not set", cfg.blob_storage_configured),
      statusRow("Speech-to-Text Engine", "Hosted Whisper API"),
      statusRow("Whisper Model", cfg.whisper_model),
      statusRow("Whisper API Key", cfg.whisper_key_configured ? "Configured" : "Not set", cfg.whisper_key_configured),
      statusRow("AI Analysis Provider", "OpenRouter"),
      statusRow("OpenRouter Model", cfg.openrouter_model),
      statusRow("OpenRouter API Key", cfg.openrouter_key_configured ? "Configured" : "Not set", cfg.openrouter_key_configured),
      statusRow("Email (SMTP)", cfg.mail_configured ? "Configured" : "Not set", cfg.mail_configured),
    ].join("");
  }

  function maybeShowBanner(cfg) {
    const problems = [];
    if (!cfg.database_configured) {
      problems.push("Database isn't connected — set DATABASE_URL in your environment variables.");
    }
    if (!cfg.blob_storage_configured) {
      problems.push("Audio storage isn't configured — connect a Vercel Blob store and set BLOB_READ_WRITE_TOKEN.");
    }
    if (!cfg.whisper_key_configured) {
      problems.push("Transcription API key is missing — set HOSTED_WHISPER_API_KEY (or GROQ_API_KEY).");
    }
    if (!cfg.openrouter_key_configured) {
      problems.push("OpenRouter API key is missing — set OPENROUTER_API_KEY to enable AI notes.");
    }
    if (problems.length) {
      UI.showConfigBanner('<i class="fa-solid fa-triangle-exclamation"></i> ' + problems.join(' &nbsp;•&nbsp; '));
    }
  }

  document.addEventListener("DOMContentLoaded", () => load());

  return { load };
})();
