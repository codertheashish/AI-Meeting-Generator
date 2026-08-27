/* =========================================================
   AI Meeting Generator - export.js
   Copy notes, download PDF/DOCX/TXT, and send-via-email flow.
   ========================================================= */

const ExportModule = (() => {
  const els = {};

  function cacheEls() {
    els.copyBtn = document.getElementById("copyNotesBtn");
    els.pdfBtn = document.getElementById("downloadPdfBtn");
    els.docxBtn = document.getElementById("downloadDocxBtn");
    els.txtBtn = document.getElementById("downloadTxtBtn");
    els.openEmailBtn = document.getElementById("openEmailBtn");
    els.emailCard = document.getElementById("emailCard");
    els.emailTo = document.getElementById("emailTo");
    els.emailSubject = document.getElementById("emailSubject");
    els.sendEmailBtn = document.getElementById("sendEmailBtn");
    els.emailLoader = document.getElementById("emailLoader");
  }

  function requireMeeting() {
    const meeting = window.AppState.currentMeeting;
    if (!meeting) {
      UI.error("Generate meeting notes first, then export or share them.");
      return null;
    }
    return meeting;
  }

  function buildPlainTextNotes(meeting) {
    const lines = [];
    lines.push(`Meeting Notes - ${meeting.title}`);
    lines.push(`Date: ${UI.formatDate(meeting.date)}`);
    lines.push("");
    lines.push("SUMMARY");
    lines.push(meeting.summary || "N/A");
    lines.push("");
    lines.push("ACTION ITEMS");
    (meeting.action_items || []).forEach((a) => {
      lines.push(`- [${a.completed ? "x" : " "}] ${a.task} (${a.assigned_to || "Unassigned"}, due ${a.deadline || "N/A"})`);
    });
    lines.push("");
    lines.push("KEY HIGHLIGHTS");
    (meeting.key_highlights || []).forEach((h) => lines.push(`- ${h}`));
    lines.push("");
    lines.push("DECISIONS MADE");
    (meeting.decisions || []).forEach((d) => lines.push(`- ${d}`));
    return lines.join("\n");
  }

  async function copyNotes() {
    const meeting = requireMeeting();
    if (!meeting) return;
    try {
      await navigator.clipboard.writeText(buildPlainTextNotes(meeting));
      UI.success("Notes copied to clipboard.");
    } catch {
      UI.error("Could not copy to clipboard. Your browser may be blocking clipboard access.");
    }
  }

  async function downloadFile(url, btn, label) {
    const meeting = requireMeeting();
    if (!meeting) return;
    UI.setButtonBusy(btn, true, label);
    try {
      const res = await fetch(url);
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || `Export failed (${res.status}).`);
      }
      const blob = await res.blob();
      const disposition = res.headers.get("Content-Disposition") || "";
      const match = disposition.match(/filename="?([^"]+)"?/);
      const filename = match ? match[1] : "meeting-notes";

      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(link.href);
      UI.success("Download started.");
    } catch (err) {
      UI.error(`Export failed: ${err.message}`);
    } finally {
      UI.setButtonBusy(btn, false);
    }
  }

  function toggleEmailCard() {
    const meeting = requireMeeting();
    if (!meeting) return;
    const visible = els.emailCard.style.display !== "none";
    els.emailCard.style.display = visible ? "none" : "block";
    els.emailSubject.value = `Meeting Notes - ${meeting.title}`;
    if (!visible) els.emailCard.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  async function sendEmail() {
    const meeting = requireMeeting();
    if (!meeting) return;
    const to = els.emailTo.value.trim();
    if (!to || !to.includes("@")) {
      UI.error("Enter a valid recipient email address.");
      return;
    }

    UI.setLoading(els.emailLoader, true);
    UI.setButtonBusy(els.sendEmailBtn, true, "Sending...");

    try {
      const res = await fetch("/api/email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          meeting_id: meeting.id,
          to,
          subject: els.emailSubject.value,
        }),
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.error || "Email failed to send.");
      UI.success(data.message || "Email sent.");
      els.emailCard.style.display = "none";
    } catch (err) {
      UI.error(`Could not send email: ${err.message}`);
    } finally {
      UI.setLoading(els.emailLoader, false);
      UI.setButtonBusy(els.sendEmailBtn, false);
    }
  }

  function init() {
    cacheEls();
    if (!els.copyBtn) return;
    els.copyBtn.addEventListener("click", copyNotes);
    els.pdfBtn.addEventListener("click", () =>
      downloadFile(`/api/export/pdf/${window.AppState.currentMeeting?.id}`, els.pdfBtn, "Preparing...")
    );
    els.docxBtn.addEventListener("click", () =>
      downloadFile(`/api/export/docx/${window.AppState.currentMeeting?.id}`, els.docxBtn, "Preparing...")
    );
    els.txtBtn.addEventListener("click", () =>
      downloadFile(`/api/export/txt/${window.AppState.currentMeeting?.id}`, els.txtBtn, "Preparing...")
    );
    els.openEmailBtn.addEventListener("click", toggleEmailCard);
    els.sendEmailBtn.addEventListener("click", sendEmail);
  }

  document.addEventListener("DOMContentLoaded", init);

  return {};
})();
