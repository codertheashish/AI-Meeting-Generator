/* notes.js — renders summary, action items, highlights, decisions, speaker analytics, meeting history */

const Notes = (() => {
  const summaryText = document.getElementById("summary-text");
  const actionItemsList = document.getElementById("action-items-list");
  const highlightsList = document.getElementById("highlights-list");
  const decisionsList = document.getElementById("decisions-list");
  const followupsList = document.getElementById("followups-list");
  const speakersList = document.getElementById("speakers-list");
  const historyList = document.getElementById("history-list");
  const analysisErrorCard = document.getElementById("analysis-error-card");

  function clear() {
    summaryText.textContent = "Your AI-generated summary will appear here after processing.";
    actionItemsList.innerHTML = '<li class="empty-state">No action items yet.</li>';
    highlightsList.innerHTML = '<li class="empty-state">No highlights yet.</li>';
    decisionsList.innerHTML = '<li class="empty-state">No decisions yet.</li>';
    followupsList.innerHTML = '<li class="empty-state">No follow-up points yet.</li>';
    speakersList.innerHTML = '<p class="empty-state">Speaker analytics will appear after transcription.</p>';
    analysisErrorCard.classList.add("hidden");
  }

  function showAnalysisError(message) {
    document.getElementById("analysis-error-text").textContent = message;
    analysisErrorCard.classList.remove("hidden");
    analysisErrorCard.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function hideAnalysisError() {
    analysisErrorCard.classList.add("hidden");
  }

  const PRIORITY_CLASS = { High: "priority-high", Medium: "priority-medium", Low: "priority-low" };

  function renderSpeakers(speakers) {
    if (!speakers || speakers.length === 0) {
      speakersList.innerHTML = '<p class="empty-state">Speaker analytics will appear after transcription.</p>';
      return;
    }
    speakersList.innerHTML = speakers.map((s) => `
      <div class="speaker-row">
        <div class="speaker-row-top">
          <span class="name">${UI.escapeHtml(s.name)}</span>
          <span class="meta">${s.speaking_percentage || 0}% • ${UI.formatTime(s.speaking_time || 0)}</span>
        </div>
        <div class="progress-track"><div class="progress-fill" style="width:${s.speaking_percentage || 0}%"></div></div>
      </div>
    `).join("");
  }

  function renderMeetingNotes(meeting) {
    summaryText.textContent = meeting.summary || "No summary generated yet.";

    const items = meeting.action_items || [];
    actionItemsList.innerHTML = items.length
      ? items.map((item) => `
        <li class="action-item ${item.completed ? "completed" : ""}" data-id="${item.id}">
          <input type="checkbox" ${item.completed ? "checked" : ""} data-action-id="${item.id}">
          <div class="action-item-content">
            <div class="action-item-task">${UI.escapeHtml(item.task)}</div>
            <div class="action-item-meta">
              <span><i class="fa-regular fa-user"></i> ${UI.escapeHtml(item.assigned_to || "Unassigned")}</span>
              <span><i class="fa-regular fa-calendar"></i> ${UI.escapeHtml(item.deadline || "TBD")}</span>
              <span class="priority-tag ${PRIORITY_CLASS[item.priority] || "priority-medium"}">${UI.escapeHtml(item.priority || "Medium")}</span>
            </div>
          </div>
        </li>
      `).join("")
      : '<li class="empty-state">No action items yet.</li>';

    document.querySelectorAll("[data-action-id]").forEach((cb) => {
      cb.addEventListener("change", async (e) => {
        const id = e.target.dataset.actionId;
        const completed = e.target.checked;
        e.target.closest(".action-item").classList.toggle("completed", completed);
        try {
          await Api.updateActionItem(id, { completed });
        } catch (err) {
          UI.toast("Couldn't save that change: " + err.message, "error");
        }
      });
    });

    const highlights = meeting.key_highlights || [];
    highlightsList.innerHTML = highlights.length
      ? highlights.map((h) => `<li>${UI.escapeHtml(h)}</li>`).join("")
      : '<li class="empty-state">No highlights yet.</li>';

    const decisions = meeting.decisions || [];
    decisionsList.innerHTML = decisions.length
      ? decisions.map((d) => `<li>${UI.escapeHtml(typeof d === "string" ? d : d.decision)}</li>`).join("")
      : '<li class="empty-state">No decisions yet.</li>';

    const followUps = meeting.follow_up_points || [];
    followupsList.innerHTML = followUps.length
      ? followUps.map((f) => `<li>${UI.escapeHtml(f)}</li>`).join("")
      : '<li class="empty-state">No follow-up points yet.</li>';

    renderSpeakers(meeting.speakers);
    hideAnalysisError();
  }

  async function loadHistory() {
    try {
      const { meetings } = await Api.listMeetings();
      if (!meetings || meetings.length === 0) {
        historyList.innerHTML = '<p class="empty-state">No past meetings yet.</p>';
        return;
      }
      historyList.innerHTML = meetings.map((m) => `
        <div class="history-item">
          <div>
            <div class="history-item-title">${UI.escapeHtml(m.title)}</div>
            <div class="history-item-meta">${new Date(m.created_at).toLocaleString()} • ${m.status}</div>
          </div>
          <div class="history-item-actions">
            <button class="btn btn-outline" data-load-id="${m.id}"><i class="fa-solid fa-eye"></i> View</button>
            <button class="btn btn-ghost" data-delete-id="${m.id}"><i class="fa-solid fa-trash"></i></button>
          </div>
        </div>
      `).join("");

      historyList.querySelectorAll("[data-load-id]").forEach((btn) => {
        btn.addEventListener("click", () => App.loadMeeting(btn.dataset.loadId));
      });
      historyList.querySelectorAll("[data-delete-id]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          if (!confirm("Delete this meeting? This cannot be undone.")) return;
          try {
            await Api.deleteMeeting(btn.dataset.deleteId);
            UI.toast("Meeting deleted.", "success");
            loadHistory();
          } catch (err) {
            UI.toast("Couldn't delete meeting: " + err.message, "error");
          }
        });
      });
    } catch (err) {
      UI.toast("Couldn't load meeting history: " + err.message, "error");
    }
  }

  return { clear, renderMeetingNotes, renderSpeakers, loadHistory, showAnalysisError, hideAnalysisError };
})();
