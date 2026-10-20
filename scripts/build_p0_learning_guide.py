"""P0 학습 노트를 PDF로 생성한다. ReportLab과 임베딩 가능한 한글 TTF가 필요하다."""

import argparse
from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable, HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from build_domain_guide import inline

ROOT = Path(__file__).resolve().parents[1]
INK = colors.HexColor("#18364A")
TEAL = colors.HexColor("#087F83")
GRAY = colors.HexColor("#596B78")
PALE = colors.HexColor("#EDF5F5")
LINE = colors.HexColor("#D9E3E8")
WIDTH, HEIGHT = A4
CONTENT_WIDTH = WIDTH - 92


class ConceptFlow(Flowable):
    def __init__(self, labels):
        super().__init__()
        self.labels = labels
        self.width, self.height = CONTENT_WIDTH, 67

    def draw(self):
        c = self.canv
        gap = 17
        box = (self.width - gap * (len(self.labels) - 1)) / len(self.labels)
        for i, label in enumerate(self.labels):
            x = i * (box + gap)
            c.setFillColor(PALE)
            c.setStrokeColor(LINE)
            c.roundRect(x, 13, box, 42, 7, fill=1, stroke=1)
            c.setFillColor(INK)
            c.setFont("Korean", 10)
            c.drawCentredString(x + box / 2, 29, label)
            if i < len(self.labels) - 1:
                start, end = x + box + 3, x + box + gap - 3
                c.setStrokeColor(TEAL)
                c.line(start, 34, end, 34)
                c.line(end - 4, 37, end, 34)
                c.line(end - 4, 31, end, 34)


def build(font_path, output):
    font = TTFont("Korean", str(font_path))
    pdfmetrics.registerFont(font)
    pdfmetrics.registerFontFamily("Korean", normal="Korean", bold="Korean", italic="Korean")
    source = (ROOT / "docs/07_p0_domain_and_tech_notes.md").read_text(encoding="utf-8")
    missing = sorted({c for c in source if not c.isspace() and ord(c) not in font.face.charToGlyph})
    if missing:
        raise ValueError(f"폰트가 지원하지 않는 문자: {missing}")
    common = dict(fontName="Korean", wordWrap="CJK", textColor=INK)
    styles = {
        "cover": ParagraphStyle("cover", fontSize=28, leading=39, spaceAfter=18, **common),
        "title": ParagraphStyle("title", fontSize=21, leading=29, spaceAfter=12, **common),
        "h2": ParagraphStyle("h2", fontSize=12.5, leading=19, spaceBefore=12, spaceAfter=7,
                             keepWithNext=True, **common),
        "body": ParagraphStyle("body", fontSize=10.1, leading=16.1, spaceAfter=8, **common),
        "bullet": ParagraphStyle("bullet", fontSize=10, leading=16, leftIndent=10,
                                 firstLineIndent=-8, spaceAfter=6, **common),
        "cell": ParagraphStyle("cell", fontSize=9.1, leading=14.2, **common),
        "ref": ParagraphStyle("ref", fontSize=9, leading=14.4, spaceAfter=10, **common),
        "caption": ParagraphStyle("caption", fontName="Korean", wordWrap="CJK", fontSize=8,
                                  leading=12, textColor=GRAY, spaceBefore=5, spaceAfter=6),
    }
    pages = source.split("<!-- page -->")
    titles = []
    story = []
    for page_number, page in enumerate(pages):
        if page_number:
            story.append(PageBreak())
        else:
            story.append(Spacer(1, 28))
        lines = page.strip().splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            if line.startswith("# "):
                title = line[2:]
                titles.append(title)
                content = inline(title).replace(" / ", "<br/>") if page_number == 0 else inline(title)
                story.append(Paragraph(content, styles["cover" if page_number == 0 else "title"]))
                story.append(HRFlowable(width="100%", thickness=1.2, color=TEAL, spaceAfter=11))
            elif line.startswith("## "):
                story.append(Paragraph(inline(line[3:]), styles["h2"]))
            elif line.startswith("!flow "):
                story.append(ConceptFlow([t.strip() for t in line[6:].split("|")]))
            elif line.startswith("| "):
                rows = []
                while i < len(lines) and lines[i].strip().startswith("|"):
                    cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                    if not all(re.fullmatch(r"[-: ]+", c) for c in cells):
                        rows.append([Paragraph(inline(c), styles["cell"]) for c in cells])
                    i += 1
                n = len(rows[0])
                if any(len(row) != n for row in rows):
                    raise ValueError("표 열 수가 일치하지 않습니다.")
                ratios = [0.29, 0.71] if n == 2 else [0.28, 0.28, 0.44]
                if page_number == 3 and n == 3:
                    ratios = [0.56, 0.22, 0.22]
                elif page_number == 6 and n == 3:
                    ratios = [0.34, 0.19, 0.47]
                elif page_number == 9 and n == 3:
                    ratios = [0.22, 0.44, 0.34]
                table = Table(rows, colWidths=[CONTENT_WIDTH * r for r in ratios], repeatRows=1,
                              hAlign="LEFT", splitByRow=1)
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDEDEE")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F8FA")]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.8, TEAL),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]))
                story.extend([table, Spacer(1, 9)])
                continue
            elif line.startswith("> "):
                box = Table([[Paragraph(inline(line[2:]), styles["body"])]], colWidths=[CONTENT_WIDTH])
                box.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), PALE),
                    ("LINEBEFORE", (0, 0), (0, -1), 3, TEAL),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ]))
                story.extend([box, Spacer(1, 8)])
            elif line.startswith("- "):
                story.append(Paragraph("- " + inline(line[2:]), styles["bullet"]))
            else:
                style = "caption" if line.startswith("출처:") else ("ref" if page_number >= 14 else "body")
                story.append(Paragraph(inline(line), styles[style]))
            i += 1

    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(TEAL)
        canvas.rect(0, HEIGHT - 10, WIDTH, 10, fill=1, stroke=0)
        canvas.setFont("Korean", 8)
        canvas.setFillColor(GRAY)
        canvas.drawString(46, HEIGHT - 35, "EGFR Evidence Lab  |  P0 도메인·기술 학습 노트")
        canvas.setStrokeColor(LINE)
        canvas.line(46, 38, WIDTH - 46, 38)
        canvas.drawString(46, 24, "2026.10.19  |  소량 API 확인 완료 · 전체 수집·학습 전")
        canvas.drawRightString(WIDTH - 46, 24, f"{doc.page:02d}")
        canvas.restoreState()

    output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(output), pagesize=A4, leftMargin=46, rightMargin=46,
                            topMargin=59, bottomMargin=54,
                            title="EGFR Evidence Lab - 도메인과 기술 학습 노트",
                            author="EGFR Evidence Lab", subject="전체 데이터 수집 전 도메인·IT 기술 이해")
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    print(f"PDF 저장: {output}")
    print(f"설계한 페이지: {len(pages)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, required=True, help="임베딩 가능한 한글 TTF 경로")
    parser.add_argument("--output", type=Path, default=ROOT / "output/pdf/egfr_p0_domain_tech_ko.pdf")
    options = parser.parse_args()
    build(options.font, options.output)
