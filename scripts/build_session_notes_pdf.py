"""세션 정리 Markdown 문서를 PDF로 렌더링한다.

ReportLab과 임베딩 가능한 한글 TTF가 필요하다. 제한된 Markdown 부분집합만 처리한다:
  # / ## / ### 제목, 문단, - 불릿, > 인용, | 표 |, --- 구분선, **굵게**, `코드`.

사용 예:
  python scripts/build_session_notes_pdf.py \
      --font /System/Library/Fonts/Supplemental/AppleGothic.ttf \
      --output ~/Desktop/EGFR_기술스택_도메인정리.pdf

  python scripts/build_session_notes_pdf.py \
      --source docs/14_session_20261021_notes_ko.md \
      --header "EGFR Evidence Lab  |  2026-10-21 작업 지표·기술·도메인" \
      --footer "2026.10.21  |  M3 벤치마크 축소 재현 완료 · M2 착수 전" \
      --font /System/Library/Fonts/Supplemental/AppleGothic.ttf \
      --output ~/Desktop/파일명.pdf
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "docs/13_session_tech_domain_notes_ko.md"
DEFAULT_HEADER = "EGFR Evidence Lab  |  기술 스택·도메인 지식 정리"
DEFAULT_FOOTER = "2026.10.20  |  M1 범위 한정 완료 · 벤치마크 재현 착수 전"
DEFAULT_TITLE = "EGFR Evidence Lab - 기술 스택과 도메인 지식 정리"
DEFAULT_SUBJECT = "실제 수행한 기술 스택과 판단에 필요한 도메인 지식"

INK = colors.HexColor("#18364A")
TEAL = colors.HexColor("#087F83")
GRAY = colors.HexColor("#596B78")
PALE = colors.HexColor("#EDF5F5")
LINE = colors.HexColor("#D9E3E8")
WIDTH, HEIGHT = A4
MARGIN = 46
CONTENT_WIDTH = WIDTH - 2 * MARGIN


# 한글 TTF(AppleGothic 등)에 없는 기호를 같은 뜻의 글자로 바꾼다. 의미를 바꾸는 치환은 넣지 않는다.
GLYPH_FALLBACK = {
    "µ": "μ",   # MICRO SIGN -> GREEK SMALL LETTER MU (둘 다 '마이크로'로 읽음)
    "−": "-",        # MINUS SIGN -> HYPHEN-MINUS
    "₀": "0",        # SUBSCRIPT ZERO -> 0  (log10 표기)
}


def normalize_glyphs(text: str) -> str:
    for src, dst in GLYPH_FALLBACK.items():
        text = text.replace(src, dst)
    return text


def inline(text: str) -> str:
    """제한된 인라인 마크업을 ReportLab 태그로 바꾼다."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r'<font color="#087F83">\1</font>', text)
    text = re.sub(r"`(.+?)`", r'<font face="Korean" color="#18364A">\1</font>', text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r"\1", text)
    return text


def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def build(font_path: Path, output: Path, source_path: Path = DEFAULT_SOURCE,
          header_text: str = DEFAULT_HEADER, footer_text: str = DEFAULT_FOOTER,
          title: str = DEFAULT_TITLE, subject: str = DEFAULT_SUBJECT) -> None:
    # header_text/footer_text 는 아래 표 파싱의 지역변수 header 와 이름이 겹치지 않아야 한다.
    # decorate() 가 이 스코프를 닫아 잡으므로, 겹치면 마지막 표의 머리행이 머리글로 들어간다.
    pdfmetrics.registerFont(TTFont("Korean", str(font_path)))
    pdfmetrics.registerFontFamily("Korean", normal="Korean", bold="Korean", italic="Korean")

    source = normalize_glyphs(source_path.read_text(encoding="utf-8"))

    font = pdfmetrics.getFont("Korean").face
    missing = sorted({c for c in source if not c.isspace() and ord(c) not in font.charToGlyph})
    if missing:
        raise SystemExit(f"폰트에 없는 글자: {''.join(missing[:40])}")

    # 굵게 표시는 한 줄 안에서 열고 닫아야 한다. 줄을 걸치면 regex가 잡지 못해
    # PDF에 별표가 그대로 찍힌다. 조용히 넘기지 말고 알린다.
    unbalanced = [i for i, ln in enumerate(source.split("\n"), 1) if ln.count("**") % 2]
    if unbalanced:
        print(f"경고: 굵게(**)가 줄을 걸친 행 {unbalanced} - 해당 줄에서 열고 닫아라")

    common = dict(fontName="Korean", wordWrap="CJK", textColor=INK)
    st = {
        "h1": ParagraphStyle("h1", fontSize=19, leading=27, spaceBefore=4, spaceAfter=12, **common),
        "h2": ParagraphStyle("h2", fontSize=13, leading=20, spaceBefore=14, spaceAfter=7,
                             textColor=TEAL, fontName="Korean", wordWrap="CJK"),
        "h3": ParagraphStyle("h3", fontSize=11, leading=17, spaceBefore=10, spaceAfter=5, **common),
        "body": ParagraphStyle("body", fontSize=9.6, leading=15.4, spaceAfter=7, **common),
        "bullet": ParagraphStyle("bullet", fontSize=9.4, leading=15, leftIndent=12,
                                 bulletIndent=2, spaceAfter=3.5, **common),
        "quote": ParagraphStyle("quote", fontSize=9.3, leading=15, leftIndent=12, rightIndent=8,
                                spaceBefore=5, spaceAfter=8, backColor=PALE,
                                borderPadding=7, textColor=INK, fontName="Korean", wordWrap="CJK"),
        "cell": ParagraphStyle("cell", fontSize=8.5, leading=13, **common),
        "head": ParagraphStyle("head", fontSize=8.5, leading=13, textColor=colors.white,
                               fontName="Korean", wordWrap="CJK"),
    }

    story: list = []
    lines = source.split("\n")
    i = 0
    table_count = 0
    while i < len(lines):
        line = lines[i].rstrip()

        if not line.strip():
            i += 1
            continue

        if line.startswith("|") and i + 1 < len(lines) and set(lines[i + 1].replace("|", "").strip()) <= set("-: "):
            header = split_row(line)
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            data = [[Paragraph(inline(c), st["head"]) for c in header]]
            data += [[Paragraph(inline(c), st["cell"]) for c in r] for r in rows]
            ncol = len(header)
            col_w = [CONTENT_WIDTH / ncol] * ncol
            table = Table(data, colWidths=col_w, repeatRows=1, hAlign="LEFT")
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), TEAL),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
                ("GRID", (0, 0), (-1, -1), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story += [Spacer(1, 4), table, Spacer(1, 9)]
            table_count += 1
            continue

        if line.startswith("### "):
            story.append(Paragraph(inline(line[4:]), st["h3"]))
        elif line.startswith("## "):
            story.append(Paragraph(inline(line[3:]), st["h2"]))
        elif line.startswith("# "):
            if story:
                story.append(PageBreak())
            story.append(Paragraph(inline(line[2:]), st["h1"]))
            story.append(HRFlowable(width="100%", thickness=1.1, color=TEAL, spaceAfter=10))
        elif line.startswith("> "):
            story.append(Paragraph(inline(line[2:]), st["quote"]))
        elif line.startswith("- "):
            story.append(Paragraph(inline(line[2:]), st["bullet"], bulletText="•"))
        elif re.match(r"^\d+\. ", line):
            num, rest = line.split(". ", 1)
            story.append(Paragraph(inline(rest), st["bullet"], bulletText=f"{num}."))
        elif line.strip() == "---":
            story.append(HRFlowable(width="100%", thickness=0.6, color=LINE,
                                    spaceBefore=6, spaceAfter=8))
        else:
            story.append(Paragraph(inline(line), st["body"]))
        i += 1

    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setFont("Korean", 7.6)
        canvas.setFillColor(GRAY)
        canvas.drawString(MARGIN, HEIGHT - 32, header_text)
        canvas.setStrokeColor(LINE)
        canvas.line(MARGIN, 36, WIDTH - MARGIN, 36)
        canvas.drawString(MARGIN, 24, footer_text)
        canvas.drawRightString(WIDTH - MARGIN, 24, f"{doc.page:02d}")
        canvas.restoreState()

    output = output.expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output), pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN, topMargin=52, bottomMargin=50,
        title=title,
        author="EGFR Evidence Lab",
        subject=subject,
    )
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    print(f"PDF 저장: {output}")
    print(f"표 {table_count}개 렌더링")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, required=True, help="임베딩 가능한 한글 TTF 경로")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="렌더링할 Markdown 경로")
    parser.add_argument("--header", default=DEFAULT_HEADER, help="머리글 문구")
    parser.add_argument("--footer", default=DEFAULT_FOOTER, help="바닥글 왼쪽 문구")
    parser.add_argument("--title", default=DEFAULT_TITLE, help="PDF 메타데이터 제목")
    parser.add_argument("--subject", default=DEFAULT_SUBJECT, help="PDF 메타데이터 주제")
    args = parser.parse_args()
    build(args.font, args.output, args.source, args.header, args.footer, args.title, args.subject)
