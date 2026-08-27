/* =========================================================
   AI Meeting Generator - notes.js
   AI note generation (POST /api/generate-notes), rendering of
   summary / action items / highlights / decisions / speakers,
   action-item completion toggling, and meeting history table.
   ========================================================= */

const NotesModule = (() => {
  const els = {};
  const SPEAKER_COLORS = ["#6d28d9", "#1d4ed8", "#15803d", "#b45309", "#be185d", "#0369a1"];

  function cacheEls() {
    els.generateBtn = document.getElementById("generateNotesBtn");
    els.notesLoader = document.getElementById("notesLoader");
    els.summaryText = document.getElementById("summaryText");
    els.actionList = document.getElementById("actionList");
    els.highlightList = document.getElementById("highlightList");
    els.decisionList = document.getElementById("decisionList");
    els.speakerList = document.getElementById("speakerList");
    els.meetingsBody = document.getElementById("meetingsBody");
  }

  // ---------------- Generate notes ----------------
  async function generateNotes() {
    const meetingId = window.AppState.currentMeetingId;
    if (!meetingId) {
      UI.error("Record or upload a meeting and transcribe it first.");
      return;
    }

    UI.setLoading(els.notesLoader, true);
    UI.setButtonBusy(els.generateBtn, true, "Generating...");

    try {
      const res = await fetch("/api/generate-notes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ meeting_id: meetingId }),
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.error || "Note generation failed.");

      window.AppState.currentMeeting = data.meeting;
      renderNotes(data.meeting);
      UI.success("AI meeting notes generated.");
      refreshMeetingsList();
    } catch (err) {
      UI.error(`Could not generate notes: ${err.message}`);
    } finally {
      UI.setLoading(els.notesLoader, false);
      UI.setButtonBusy(els.generateBtn, false);
    }
  }

  function renderNotes(meeting) {
    els.summaryText.textContent = meeting.summary || "No summary available.";
    renderActionItems(meeting.action_items || []);
    renderList(els.highlightList, meeting.key_highlights || [], "No highlights yet.");
    renderList(els.decisionList, meeting.decisions || [], "No decisions recorded yet.");
    if (meeting.speakers && meeting.speakers.length) renderSpeakers(meeting.speakers);
  }

  function renderList(ulEl, items, emptyMsg) {
    if (!ulEl) return;
    if (!items || items.length === 0) {
      ulEl.innerHTML = `<li class="empty-item">${emptyMsg}</li>`;
      return;
    }
    ulEl.innerHTML = items.map((item) => `<li>${UI.escapeHtml(item)}</li>`).join("");
  }

  function renderActionItems(items) {
    if (!els.actionList) return;
    if (!items || items.length === 0) {
      els.actionList.innerHTML = `<li class="empty-item">No action items yet.</li>`;
      return;
    }
    els.actionList.innerHTML = items
      .map((item) => {
        const completed = !!item.completed;
        return `
          <li class="action-item ${completed ? "completed" : ""}" data-item-id="${item.id}">
            <input type="checkbox" class="action-checkbox" ${completed ? "checked" : ""} />
            <div class="action-info">
              <div class="action-task">${UI.escapeHtml(item.task)}</div>
              <div class="action-meta">
                <span><i class="fa-solid fa-user"></i> ${UI.escapeHtml(item.assigned_to || "Unassigned")}</span>
                <span><i class="fa-solid fa-calendar"></i> ${UI.escapeHtml(item.deadline || "No deadline")}</span>
              </div>
            </div>
          </li>`;
      })
      .join("");

    els.actionList.querySelectorAll(".action-checkbox").forEach((cb) => {
      cb.addEventListener("change", async (e) => {
        const li = e.target.closest(".action-item");
        const itemId = li.dataset.itemId;
        const completed = e.target.checked;
        li.classList.toggle("completed", completed);
        try {
          const res = await fetch(`/api/action-items/${itemId}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ completed }),
          });
          const data = await res.json();
          if (!data.success) throw new Error(data.error || "Update failed.");
        } catch (err) {
          UI.error(`Could not update action item: ${err.message}`);
          e.target.checked = !completed;
          li.classList.toggle("completed", !completed);
        }
      });
    });
  }

  // ---------------- Speaker analytics ----------------
  function renderSpeakers(speakers) {
    if (!els.speakerList) return;
    if (!speakers || speakers.length === 0) {
      els.speakerList.innerHTML = `<p class="empty-item">No speaker data yet.</p>`;
      return;
    }
    els.speakerList.innerHTML = speakers
      .map((sp, idx) => {
        const color = SPEAKER_COLORS[idx % SPEAKER_COLORS.length];
        const pct = Math.round(sp.speaking_percentage || 0);
        return `
          <div class="speaker-row">
            <div class="speaker-name">
              <span class="speaker-dot" style="background:${color}"></span>
              ${UI.escapeHtml(sp.name)}
            </div>
            <div class="speaker-bar-track">
              <div class="speaker-bar-fill" style="width:${pct}%; background:${color}"></div>
            </div>
            <div class="speaker-stats">${pct}% &middot; ${UI.formatTime(sp.speaking_time || 0)}</div>
          </div>`;
      })
      .join("");
  }

  // ---------------- Meeting history ----------------
  async function refreshMeetingsList() {
    if (!els.meetingsBody) return;
    try {
      const res = await fetch("/api/meetings");
      const data = await res.json();
      if (!data.success) throw new Error(data.error || "Could not load meetings.");
      renderMeetingsList(data.meetings || []);
    } catch (err) {
      // Non-blocking - just leave the table as-is with an error toast on demand
      console.error(err);
    }
  }

  function renderMeetingsList(meetings) {
    if (!meetings || meetings.length === 0) {
      els.meetingsBody.innerHTML = `<tr class="empty-row"><td colspan="4">No meetings yet.</td></tr>`;
      return;
    }
    els.meetingsBody.innerHTML = meetings
      .map(
        (m) => `
        <tr data-meeting-id="${m.id}">
          <td>${UI.escapeHtml(m.title)}</td>
          <td>${UI.formatDate(m.date || m.created_at)}</td>
          <td><span class="meeting-status ${m.status}">${UI.escapeHtml(UI.statusLabel(m.status))}</span></td>
          <td>
            <div class="row-actions">
              <button class="btn btn-outline btn-sm" data-action="load" data-id="${m.id}"><i class="fa-solid fa-eye"></i> Open</button>
              <button class="btn btn-ghost btn-sm" data-action="delete" data-id="${m.id}"><i class="fa-solid fa-trash"></i></button>
            </div>
          </td>
        </tr>`
      )
      .join("");

    els.meetingsBody.querySelectorAll('[data-action="load"]').forEach((btn) => {
      btn.addEventListener("click", () => loadMeeting(btn.dataset.id));
    });
    els.meetingsBody.querySelectorAll('[data-action="delete"]').forEach((btn) => {
      btn.addEventListener("click", () => deleteMeeting(btn.dataset.id));
    });
  }

  async function loadMeeting(meetingId) {
    try {
      const res = await fetch(`/api/meetings/${meetingId}`);
      const data = await res.json();
      if (!data.success) throw new Error(data.error || "Could not load meeting.");

      window.AppState.currentMeetingId = data.meeting.id;
      window.AppState.currentMeeting = data.meeting;

      renderNotes(data.meeting);
      if (data.meeting.transcript) {
        // We don't store per-segment speaker timing after reload, so show the
        // full transcript as a single row attributed to "Full Transcript".
        window.Transcription.renderTranscript([
          { start: 0, speaker: "Full Transcript", text: data.meeting.transcript },
        ]);
      }
      UI.success(`Loaded "${data.meeting.title}".`);
      document.querySelector('[data-view="notes"]')?.scrollIntoView?.();
      document.getElementById("notes")?.scrollIntoView({ behavior: "smooth" });
    } catch (err) {
      UI.error(`Could not open meeting: ${err.message}`);
    }
  }

  async function deleteMeeting(meetingId) {
    if (!confirm("Delete this meeting permanently? This cannot be undone.")) return;
    try {
      const res = await fetch(`/api/meetings/${meetingId}`, { method: "DELETE" });
      const data = await res.json();
      if (!data.success) throw new Error(data.error || "Delete failed.");
      UI.success("Meeting deleted.");
      if (String(window.AppState.currentMeetingId) === String(meetingId)) {
        window.AppState.currentMeetingId = null;
        window.AppState.currentMeeting = null;
      }
      refreshMeetingsList();
    } catch (err) {
      UI.error(`Could not delete meeting: ${err.message}`);
    }
  }

  function init() {
    cacheEls();
    if (els.generateBtn) els.generateBtn.addEventListener("click", generateNotes);
    refreshMeetingsList();
  }

  document.addEventListener("DOMContentLoaded", init);

  return { renderSpeakers, renderNotes, refreshMeetingsList, loadMeeting };
})();

window.NotesModule = NotesModule;
