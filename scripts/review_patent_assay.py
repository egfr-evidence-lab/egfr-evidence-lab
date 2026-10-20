"""US11066414B2의 원 표적 열과 ChEMBL 관측을 record_id로 대조한다."""

from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


class TableRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            if self.row is not None:
                self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def exact_number(text):
    if not re.fullmatch(r"\d+(?:\.\d+)?", str(text).strip()):
        return None
    return float(text)


def classify(value, relation, cot_text, egfr_text):
    numeric = exact_number(value)
    if relation != "=" or numeric is None:
        return "non_exact_or_non_numeric_requires_review"
    cot, egfr = exact_number(cot_text), exact_number(egfr_text)
    cot_match = cot is not None and math.isclose(numeric, cot)
    egfr_match = egfr is not None and math.isclose(numeric, egfr)
    if cot_match and egfr_match:
        return "matches_both_target_columns_ambiguous"
    if cot_match:
        return "matches_cot_column_only"
    if egfr_match:
        return "matches_explicit_egfr_column"
    return "no_exact_source_column_match"


def main():
    html_path = ROOT / "data/raw/larger_assay_sources_20261020/US11066414B2.html"
    records_path = ROOT / "data/raw/larger_assay_followup_20261020/patent_records.json"
    html = html_path.read_text()
    if 'As shown in Table 3, the compounds of Formula I are inhibitors of Cot' not in html:
        raise ValueError("Table 3의 Cot 표적 문맥을 확인하지 못했습니다.")
    source_tables = {}
    for chunk in re.findall(r"<tables\b.*?</tables>", html, re.S):
        parser = TableRows()
        parser.feed(chunk)
        for number in (3, 4, 5):
            if any(row == [f"TABLE {number}"] for row in parser.rows):
                if number in source_tables:
                    raise ValueError("원 표 중복 연결")
                source_tables[number] = parser.rows
    cot = {r[0]: r[1] for r in source_tables[3] if len(r) == 3 and r[0].isdigit()}
    egfr = {}
    for number in (4, 5):
        for row in source_tables[number]:
            if len(row) == 4 and row[0].isdigit():
                egfr[row[0]] = row[3]
    if cot.get("362") != "1" or egfr.get("362") != "3984":
        raise ValueError("핵심 원 표 대조 불일치")
    data = json.loads(records_path.read_text())
    if data["page_meta"]["next"] or len(data["compound_records"]) != data["page_meta"]["total_count"]:
        raise ValueError("특허 화합물 record 페이지 누락")
    records = {r["record_id"]: r for r in data["compound_records"]}
    raw_paths, observations = [], []
    for path in sorted((ROOT / "data/raw/chembl_full_20261020/responses").glob("activities*.json")):
        matches = [r for r in json.loads(path.read_text()).get("activities", [])
                   if r.get("assay_chembl_id") == "CHEMBL5736995"]
        if matches:
            raw_paths.append(path)
            observations.extend(matches)
    rows = []
    for activity in observations:
        record = records[activity["record_id"]]
        if activity["document_chembl_id"] != record["document_chembl_id"] or activity["molecule_chembl_id"] != record["molecule_chembl_id"]:
            raise ValueError("원 activity·record·분자 연결 불일치")
        key = re.search(r"Compound\s+(\d+)$", record.get("compound_name") or "")
        compound = key.group(1) if key else ""
        cot_value, egfr_value = cot.get(compound, ""), egfr.get(compound, "")
        rows.append({"activity_id": activity["activity_id"], "record_id": activity["record_id"],
                     "molecule_chembl_id": activity["molecule_chembl_id"], "compound_number": compound,
                     "assay_chembl_id": activity["assay_chembl_id"], "standard_value_nM": activity["standard_value"],
                     "standard_relation": activity["standard_relation"], "table3_cot_IC50_nM": cot_value,
                     "tables4_5_egfr_IC50_nM": egfr_value,
                     "source_check": classify(activity["standard_value"], activity["standard_relation"], cot_value, egfr_value),
                     "training_approved": False})
    frame = pd.DataFrame(rows)
    if len(frame) != 981 or frame.activity_id.duplicated().any():
        raise ValueError("원 대규모 실험 ID·행수 불일치")
    out = ROOT / "data/interim/patent_target_review_20261020"
    if out.exists():
        raise FileExistsError(f"기존 검토 보호: {out}")
    out.mkdir(parents=True)
    path = out / "target_column_crosscheck.csv"
    frame.to_csv(path, index=False)
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    summary = {"assay_chembl_id": "CHEMBL5736995", "total_observations": len(frame),
               "source_table3_compounds": len(cot), "explicit_egfr_table_compounds": len(egfr),
               "classification_counts": frame.source_check.value_counts().to_dict(),
               "decision": "quarantine_assay_pending_target_column_and_structure_review",
               "claim_limit": "열 수치 일치와 표적 문맥의 충돌; 모든 관측이 잘못됐다고 단정하지 않음"}
    inputs = [html_path, records_path, Path(__file__).resolve(), *raw_paths]
    manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "summary": summary,
                "inputs_sha256": {str(p.relative_to(ROOT)): digest(p) for p in inputs},
                "output_sha256": digest(path)}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
