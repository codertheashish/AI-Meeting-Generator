/* export.js — copy notes, download PDF/DOCX/TXT, send email */

const Exporter = (() => {
  function bindEvents() {
    document.getElementById("copy-notes-btn").addEventListener("click", copyNotes);
    document.getElementById("download-pdf-btn").addEventListener("click", () => download("pdf"));
    document.getElementById("download-docx-btn").addEventListener("click", () => download("docx"));
    document.getElementById("download-txt-btn").addEventListener("click", () => download("txt"));
    document.getElementById("send-email-btn").addEventListener("click", sendEmail);
  }

  function requireMeeting() {
    if (!App.currentMeetingId) {
      UI.toast("Record or upload a meeting first, then generate notes before exporting.", "warning");
      return false;
    }
    return true;
  }

  async function copyNotes() {
    if (!requireMeeting()) return;
    const meeting = App.currentMeeting;
    if (!meeting) return;

    const lines = [
      `Meeting: ${meeting.title}`,
      `Date: ${meeting.date}`,
      "",
      "Summary:",
      meeting.summary || "N/A",
      "",
      "Action Items:",
      ...(meeting.action_items || []).map((i) => `- ${i.task} (${i.assigned_to || "Unassigned"}, due ${i.deadline || "TBD"}, priority: ${i.priority || "Medium"})`),
      "",
      "Key Highlights:",
      ...(meeting.key_highlights || []).map((h) => `- ${h}`),
      "",
      "Decisions:",
      ...(meeting.decisions || []).map((d) => `- ${typeof d === "string" ? d : d.decision}`),
      "",
      "Follow-up Points:",
      ...(meeting.follow_up_points || []).map((f) => `- ${f}`),
    ];

    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      UI.toast("Notes copied to clipboard.", "success");
    } catch (err) {
      UI.toast("Couldn't copy notes: clipboard access denied.", "error");
    }
  }

  function download(format) {
    if (!requireMeeting()) return;
    const url = `/api/export/${format}/${App.currentMeetingId}`;
    const a = document.createElement("a");
    a.href = url;
    a.download = "";
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  async function sendEmail() {
    if (!requireMeeting()) return;
    const to = document.getElementById("email-to-input").value.trim();
    if (!to || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(to)) {
      UI.toast("Enter a valid recipient email address.", "warning");
      return;
    }

    UI.showLoading("Sending email...");
    try {
      await Api.sendEmail({ meeting_id: App.currentMeetingId, to, format: "pdf" });
      UI.toast(`Meeting notes sent to ${to}.`, "success");
    } catch (err) {
      UI.toast("Email failed: " + err.message, "error");
    } finally {
      UI.hideLoading();
    }
  }

  return { bindEvents };
})();

document.addEventListener("DOMContentLoaded", () => Exporter.bindEvents());
