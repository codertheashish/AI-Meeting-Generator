"""
Generates downloadable meeting-notes documents: TXT, DOCX, PDF.
Each function returns the absolute path to the generated file.
"""
import os
from datetime import datetime

from docx import Document
from docx.shared import Pt, RGBColor
from fpdf import FPDF


def _build_sections(meeting):
    participants = ", ".join(s["name"] for s in meeting.get("speakers", [])) or "Not detected"
    action_items = meeting.get("action_items", [])
    highlights = meeting.get("key_highlights", [])
    decisions = meeting.get("decisions", [])
    follow_ups = meeting.get("follow_up_points", [])
    return participants, action_items, highlights, decisions, follow_ups


def export_txt(meeting, export_dir):
    os.makedirs(export_dir, exist_ok=True)
    path = os.path.join(export_dir, f"meeting_{meeting['id']}_notes.txt")
    participants, action_items, highlights, decisions, follow_ups = _build_sections(meeting)

    lines = [
        f"MEETING NOTES: {meeting.get('title', 'Untitled Meeting')}",
        f"Date: {meeting.get('date', '')}",
        f"Participants: {participants}",
        "",
        "SUMMARY",
        "-------",
        meeting.get("summary", "") or "N/A",
        "",
        "ACTION ITEMS",
        "------------",
    ]
    if action_items:
        for item in action_items:
            status = "[x]" if item.get("completed") else "[ ]"
            lines.append(
                f"{status} {item.get('task','')} — {item.get('assigned_to','Unassigned')} — "
                f"Due: {item.get('deadline','TBD')} — Priority: {item.get('priority','Medium')}"
            )
    else:
        lines.append("No action items recorded.")

    lines += ["", "KEY HIGHLIGHTS", "--------------"]
    lines += [f"- {h}" for h in highlights] or ["No highlights recorded."]

    lines += ["", "DECISIONS MADE", "--------------"]
    lines += [f"- {d}" for d in decisions] or ["No decisions recorded."]

    lines += ["", "FOLLOW-UP POINTS", "----------------"]
    lines += [f"- {f}" for f in follow_ups] or ["No follow-up points recorded."]

    lines += ["", "FULL TRANSCRIPT", "---------------", meeting.get("transcript", "") or "N/A"]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return path


def export_docx(meeting, export_dir):
    os.makedirs(export_dir, exist_ok=True)
    path = os.path.join(export_dir, f"meeting_{meeting['id']}_notes.docx")
    participants, action_items, highlights, decisions, follow_ups = _build_sections(meeting)

    doc = Document()

    title = doc.add_heading(meeting.get("title", "Untitled Meeting"), level=0)
    title.runs[0].font.color.rgb = RGBColor(0x6D, 0x28, 0xD9)

    meta = doc.add_paragraph()
    meta.add_run(f"Date & Time: ").bold = True
    meta.add_run(f"{meeting.get('date', '')}\n")
    meta.add_run("Participants: ").bold = True
    meta.add_run(participants)

    doc.add_heading("Summary", level=1)
    doc.add_paragraph(meeting.get("summary", "") or "N/A")

    doc.add_heading("Action Items", level=1)
    if action_items:
        for item in action_items:
            status = "Done" if item.get("completed") else "Pending"
            p = doc.add_paragraph(style="List Bullet")
            p.add_run(f"{item.get('task','')} ").bold = True
            p.add_run(
                f"— Assigned to: {item.get('assigned_to','Unassigned')} | "
                f"Deadline: {item.get('deadline','TBD')} | Priority: {item.get('priority','Medium')} | Status: {status}"
            )
    else:
        doc.add_paragraph("No action items recorded.")

    doc.add_heading("Key Highlights", level=1)
    if highlights:
        for h in highlights:
            doc.add_paragraph(h, style="List Bullet")
    else:
        doc.add_paragraph("No highlights recorded.")

    doc.add_heading("Decisions Made", level=1)
    if decisions:
        for d in decisions:
            doc.add_paragraph(d, style="List Bullet")
    else:
        doc.add_paragraph("No decisions recorded.")

    doc.add_heading("Follow-up Points", level=1)
    if follow_ups:
        for f in follow_ups:
            doc.add_paragraph(f, style="List Bullet")
    else:
        doc.add_paragraph("No follow-up points recorded.")

    doc.add_heading("Full Transcript", level=1)
    transcript_para = doc.add_paragraph(meeting.get("transcript", "") or "N/A")
    for run in transcript_para.runs:
        run.font.size = Pt(9)

    doc.save(path)
    return path


class _NotesPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(109, 40, 217)  # purple accent
        self.cell(0, 10, self.title_text, ln=True)
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def section(self, heading, body):
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(76, 29, 149)
        self.cell(0, 8, heading, ln=True)
        self.set_text_color(0, 0, 0)
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 6, body)
        self.ln(2)


def export_pdf(meeting, export_dir):
    os.makedirs(export_dir, exist_ok=True)
    path = os.path.join(export_dir, f"meeting_{meeting['id']}_notes.pdf")
    participants, action_items, highlights, decisions, follow_ups = _build_sections(meeting)

    pdf = _NotesPDF()
    pdf.title_text = _latin1(meeting.get("title", "Untitled Meeting"))
    pdf.add_page()

    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, _latin1(f"Date & Time: {meeting.get('date','')}\nParticipants: {participants}"))
    pdf.ln(2)

    pdf.section("Summary", _latin1(meeting.get("summary", "") or "N/A"))

    action_text = "\n".join(
        f"- {i.get('task','')} | Assigned to: {i.get('assigned_to','Unassigned')} | "
        f"Deadline: {i.get('deadline','TBD')} | Priority: {i.get('priority','Medium')} | "
        f"{'Done' if i.get('completed') else 'Pending'}"
        for i in action_items
    ) or "No action items recorded."
    pdf.section("Action Items", _latin1(action_text))

    pdf.section("Key Highlights", _latin1("\n".join(f"- {h}" for h in highlights) or "No highlights recorded."))
    pdf.section("Decisions Made", _latin1("\n".join(f"- {d}" for d in decisions) or "No decisions recorded."))
    pdf.section("Follow-up Points", _latin1("\n".join(f"- {f}" for f in follow_ups) or "No follow-up points recorded."))
    pdf.section("Full Transcript", _latin1(meeting.get("transcript", "") or "N/A"))

    pdf.output(path)
    return path


def _latin1(text):
    """fpdf2's core fonts only support latin-1; strip anything outside that range."""
    return text.encode("latin-1", "replace").decode("latin-1")
