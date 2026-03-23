from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import os, time

OUTPUT_DIR = "output"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def create_pdf(content):
    file_path = os.path.join(OUTPUT_DIR, f"output_{int(time.time())}.pdf")

    doc = SimpleDocTemplate(file_path)
    styles = getSampleStyleSheet()

    story = []

    story.append(Paragraph("Generated Document", styles['Title']))
    story.append(Spacer(1, 12))

    for line in content.split("\n"):
        story.append(Paragraph(line, styles['Normal']))
        story.append(Spacer(1, 8))

    doc.build(story)

    return file_path