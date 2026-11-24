"""Render LLM Markdown output into a PDF.

ReportLab's `Paragraph` parses its own XML-like markup, so raw LLM text with
`<`, `>` or `&` used to crash generation. All text is escaped first, then a
small, safe subset of Markdown (headings, lists, bold, italics, inline code)
is translated into ReportLab markup.
"""

from __future__ import annotations

import io
import re
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET = re.compile(r"^\s*[-*+]\s+(.*)$")
_NUMBERED = re.compile(r"^\s*\d+[.)]\s+(.*)$")


def _inline(text: str) -> str:
    text = escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
    text = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"<i>\1</i>", text)
    text = re.sub(r"`([^`]+)`", r'<font face="Courier">\1</font>', text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<link href="\2" color="blue">\1</link>', text)
    return text


def markdown_to_pdf(markdown: str, fallback_title: str = "Generated Document") -> bytes:
    styles = getSampleStyleSheet()
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=10.5, leading=15, spaceAfter=6)
    heading_styles = {1: styles["Title"], 2: styles["Heading2"], 3: styles["Heading3"]}

    story: list = []
    pending_list: list[ListItem] = []
    list_kind = "bullet"
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            story.append(Paragraph(_inline(" ".join(paragraph)), body))
            paragraph.clear()

    def flush_list() -> None:
        nonlocal pending_list
        if pending_list:
            kwargs = {"bulletType": "1"} if list_kind == "numbered" else {"bulletType": "bullet", "start": "•"}
            story.append(ListFlowable(pending_list, leftIndent=14, **kwargs))
            story.append(Spacer(1, 4))
            pending_list = []

    lines = markdown.replace("\r\n", "\n").split("\n")
    has_title = any(_HEADING.match(line) and line.startswith("# ") for line in lines)
    if not has_title:
        story.append(Paragraph(escape(fallback_title), styles["Title"]))

    for raw in lines:
        line = raw.rstrip()
        if not line.strip() or re.fullmatch(r"\s*([-*_]\s*){3,}", line):
            flush_paragraph()
            flush_list()
            continue
        if m := _HEADING.match(line):
            flush_paragraph()
            flush_list()
            level = min(len(m.group(1)), 3)
            story.append(Paragraph(_inline(m.group(2)), heading_styles[level]))
            continue
        bullet, numbered = _BULLET.match(line), _NUMBERED.match(line)
        if bullet or numbered:
            flush_paragraph()
            kind = "numbered" if numbered else "bullet"
            if pending_list and kind != list_kind:
                flush_list()
            list_kind = kind
            text = (numbered or bullet).group(1)
            pending_list.append(ListItem(Paragraph(_inline(text), body), leftIndent=14))
            continue
        flush_list()
        paragraph.append(line.strip())

    flush_paragraph()
    flush_list()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
        title=fallback_title,
    )
    doc.build(story)
    return buffer.getvalue()
