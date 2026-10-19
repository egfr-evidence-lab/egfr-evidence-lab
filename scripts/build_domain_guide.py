"""Build the Korean study guide; requires reportlab and an embeddable Korean TTF.

Example: python scripts/build_domain_guide.py --font /path/to/Korean.ttf
Font files are not copied into the repository. Source: docs/06_domain_study_guide.md.
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable, PageBreak, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
NAVY = colors.HexColor("#123149")
TEAL = colors.HexColor("#087E8B")
GRAY = colors.HexColor("#526370")


def inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
                  r'<link href="\2" color="#087E8B"><u>\1</u></link>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r'<font color="#123149">\1</font>', text)
    text = re.sub(r"`([^`]+)`", r'<font color="#087E8B">\1</font>', text)
    return text


def build(font_path: Path, output: Path) -> None:
    pdfmetrics.registerFont(TTFont("Korean", str(font_path)))
    pdfmetrics.registerFontFamily("Korean", normal="Korean", bold="Korean", italic="Korean")
    base = dict(fontName="Korean", wordWrap="CJK", textColor=NAVY, alignment=TA_LEFT)
    styles = {
        "body": ParagraphStyle("body", fontSize=10.3, leading=16.5, spaceAfter=8, **base),
        "title": ParagraphStyle("title", fontSize=23, leading=32, spaceAfter=14, **base),
        "cover": ParagraphStyle("cover", fontSize=30, leading=42, spaceAfter=20, **base),
        "h2": ParagraphStyle("h2", fontSize=12.5, leading=19, spaceBefore=12,
                             spaceAfter=7, keepWithNext=True, **base),
        "bullet": ParagraphStyle("bullet", fontSize=10, leading=16.2, leftIndent=10,
                                 firstLineIndent=-7, spaceAfter=6, **base),
        "cell": ParagraphStyle("cell", fontSize=9, leading=14, **base),
        "ref": ParagraphStyle("ref", fontSize=8.4, leading=13, spaceAfter=8, **base),
        "caption": ParagraphStyle("caption", fontSize=8.4, leading=13,
                                  spaceAfter=8, textColor=GRAY, fontName="Korean", wordWrap="CJK"),
    }
    width, height = A4

    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(TEAL)
        canvas.rect(0, height - 11, width, 11, fill=1, stroke=0)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(GRAY)
        canvas.drawString(46, height - 35, "EGFR EVIDENCE LAB  /  DOMAIN STUDY GUIDE")
        canvas.setStrokeColor(colors.HexColor("#D5DFE5"))
        canvas.line(46, 37, width - 46, 37)
        canvas.drawString(46, 23, "2026.10.19  |  Research portfolio learning notes")
        canvas.drawRightString(width - 46, 23, f"{doc.page:02d}")
        canvas.restoreState()

    source = (ROOT / "docs/06_domain_study_guide.md").read_text(encoding="utf-8")
    pages = source.split("<!-- page -->")
    story = []
    for page_num, page in enumerate(pages):
        if page_num:
            story.append(PageBreak())
        else:
            story.append(Spacer(1, 30))
        lines = page.strip().splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            if line.startswith("# "):
                heading = inline(line[2:])
                if page_num == 0:
                    heading = heading.replace(" / ", "<br/>")
                story.append(Paragraph(heading, styles["cover" if page_num == 0 else "title"]))
                story.append(HRFlowable(width="100%", thickness=1, color=TEAL, spaceAfter=12))
            elif line.startswith("## "):
                story.append(Paragraph(inline(line[3:]), styles["h2"]))
            elif line.startswith("| "):
                rows = []
                while i < len(lines) and lines[i].strip().startswith("|"):
                    cells = [x.strip() for x in lines[i].strip().strip("|").split("|")]
                    if not all(re.fullmatch(r"[-: ]+", x) for x in cells):
                        rows.append([Paragraph(inline(x), styles["cell"]) for x in cells])
                    i += 1
                n = len(rows[0])
                ratios = {2: [0.27, 0.73], 3: [0.22, 0.28, 0.50], 4: [0.21, 0.24, 0.27, 0.28]}
                widths = [(width - 92) * r for r in ratios.get(n, [1/n] * n)]
                table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2EFF1")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7F9")]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#D5DFE5")),
                    ("LINEBELOW", (0, 0), (-1, 0), .7, TEAL),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]))
                story.extend([table, Spacer(1, 9)])
                continue
            elif line.startswith("- "):
                story.append(Paragraph("- " + inline(line[2:]), styles["bullet"]))
            elif line.startswith("> "):
                box = Table([[Paragraph(inline(line[2:]), styles["body"])]], colWidths=[width-92])
                box.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EDF6F5")),
                    ("LINEBEFORE", (0, 0), (0, -1), 3, TEAL),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ]))
                story.extend([box, Spacer(1, 10)])
            elif line.startswith("출처:"):
                story.append(Paragraph(inline(line), styles["caption"]))
            else:
                style = styles["ref"] if page_num >= len(pages)-2 else styles["body"]
                story.append(Paragraph(inline(line), style))
            i += 1
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(output), pagesize=A4, leftMargin=46, rightMargin=46,
                            topMargin=60, bottomMargin=51,
                            title="EGFR 화합물 활성 예측을 위한 도메인 학습 가이드",
                            author="EGFR Evidence Lab")
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    print(output)
    print(f"Authored sections: {len(pages)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "output/pdf/egfr_domain_study_guide_ko.pdf")
    options = parser.parse_args()
    build(options.font, options.output)
