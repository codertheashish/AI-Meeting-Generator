/* transcription.js — renders the live/processed transcription table */

const Transcription = (() => {
  const tbody = document.getElementById("transcription-body");
  const badge = document.getElementById("transcription-badge");
  const speakerColorMap = new Map();
  let colorIndex = 0;

  function colorClassFor(speaker) {
    if (!speakerColorMap.has(speaker)) {
      speakerColorMap.set(speaker, `speaker-${colorIndex % 6}`);
      colorIndex++;
    }
    return speakerColorMap.get(speaker);
  }

  function setBadge(text) {
    badge.textContent = text;
  }

  function clear() {
    speakerColorMap.clear();
    colorIndex = 0;
    tbody.innerHTML = '<tr class="empty-row"><td colspan="3">No transcription yet. Record or upload a meeting to get started.</td></tr>';
  }

  function render(rows) {
    if (!rows || rows.length === 0) {
      tbody.innerHTML = '<tr class="empty-row"><td colspan="3">Transcript came back empty.</td></tr>';
      return;
    }
    tbody.innerHTML = rows.map((row) => `
      <tr>
        <td>${UI.escapeHtml(row.timestamp)}</td>
        <td><span class="speaker-tag ${colorClassFor(row.speaker)}">${UI.escapeHtml(row.speaker)}</span></td>
        <td>${UI.escapeHtml(row.text)}</td>
      </tr>
    `).join("");
  }

  return { render, clear, setBadge };
})();
