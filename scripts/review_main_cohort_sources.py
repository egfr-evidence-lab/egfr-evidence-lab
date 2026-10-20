"""새 주 코호트 후보의 원문 수치·구조·구간값·동일 자료 블록을 대조한다."""

from datetime import datetime, timezone
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re

import pandas as pd
from rdkit import Chem

from review_patent_assay import TableRows


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/raw/main_cohort_sources_20261020"
FOLLOWUP = ROOT / "data/raw/main_cohort_sources_20261020_followup"
ASSAYS = {"CHEMBL5737421", "CHEMBL3705421", "CHEMBL5729820", "CHEMBL5733991",
          "CHEMBL4038017", "CHEMBL5382277", "CHEMBL4041412"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_measurement(text, scale=1):
    """부등호와 ±오차를 보존하며, 비수치·활성 구간을 정확값으로 바꾸지 않는다."""
    match = re.fullmatch(r"\s*([<>≤≥]?)\s*(\d+(?:\.\d+)?)(?:\s*±\s*(\d+(?:\.\d+)?))?\s*", text)
    if not match:
        return None
    return (match[1] or "=", float(match[2])*scale, float(match[3])*scale if match[3] else None)


def agrees(measurement, relation, value):
    return measurement is not None and measurement[0] == relation and math.isclose(measurement[1], float(value), rel_tol=0, abs_tol=1e-8)


def canonical(smiles):
    mol = Chem.MolFromSmiles(smiles) if smiles else None
    return Chem.MolToSmiles(mol, isomericSmiles=True) if mol is not None else ""


def interval_for_category(category):
    return {"A": (None, 10), "B": (10, 100), "C": (100, 1000), "D": (1000, 10000), "E": (10000, None)}.get(category)


def category_midpoint(category, relation, value):
    bounds = interval_for_category(category)
    return bool(bounds and all(v is not None for v in bounds) and relation == "=" and
                math.isclose(float(value), sum(bounds)/2, abs_tol=1e-8))


def table(path, number):
    found = []
    for chunk in re.findall(r"<tables\b.*?</tables>", path.read_text(), re.S):
        parser = TableRows()
        parser.feed(chunk)
        if [f"TABLE {number}"] in parser.rows:
            found.append(parser.rows)
    if len(found) != 1:
        raise ValueError("원문 표 번호 연결이 모호합니다.")
    return found[0]


def read_native(path, key, value, smiles, scale=1, encoding="utf-8-sig", skip=0):
    stream = io.StringIO(path.read_text(encoding=encoding))
    for _ in range(skip):
        next(stream)
    result = {}
    reader = csv.DictReader(stream)
    normalized = lambda text: " ".join(text.replace("\\n", " ").split())
    value_fields = [field for field in reader.fieldnames if normalized(field) == normalized(value)]
    if len(value_fields) != 1:
        raise ValueError("원 저자 CSV의 표적·단위 열이 모호합니다.")
    value = value_fields[0]
    for row in reader:
        name = row[key].strip()
        if not name:
            continue
        if name in result:
            raise ValueError("원 저자 CSV 화합물 키 중복")
        result[name] = {"text": row[value], "measurement": parse_measurement(row[value], scale),
                        "smiles": row[smiles], "canonical": canonical(row[smiles])}
    return result


def main():
    out = ROOT / "data/interim/main_cohort_review_20261020"
    if out.exists():
        raise FileExistsError(f"기존 검토 보호: {out}")
    p64, p173, p246 = [SOURCE / f"{patent}.html" for patent in ["US11155546B2", "US8846699B2", "US9987276B2"]]
    t64, t173, t246 = table(p64, 3), table(p173, 3), table(p246, 16)
    if not any("EGFR WT" in " ".join(row) for row in t64) or not any("HER-1" in row for row in t173):
        raise ValueError("원문 표적 열 확인 실패")
    source64 = {row[i]: row[i+1] for row in t64 for i in range(0, len(row)-1, 2) if re.fullmatch(r"G-\d+", row[i])}
    source173 = {row[0]: row[3] for row in t173 if len(row) == 7 and row[0].isdigit()}
    source246 = {row[1]: row[2] for row in t246 if len(row) == 3 and re.fullmatch(r"I-\d+", row[1])}
    if (len(source64), len(source173), len(source246)) != (64, 173, 245):
        raise ValueError("원문 표 행 수 변경")
    files = [p64, p173, p246, Path(__file__).resolve()]
    native_specs = {
        "CHEMBL4038017": (FOLLOWUP/"figshare_10715485.csv", "Compound_ID", "EGFR IC50 (nM)", "SMILES", 1, "utf-8-sig", 0),
        "CHEMBL5382277": (FOLLOWUP/"figshare_39124670.csv", "Comp.", "EGFRWT IC50 (nM)", "SMILE", 1, "utf-8-sig", 0),
        "CHEMBL4041412": (FOLLOWUP/"figshare_9342517.csv", "Compound", "EGFR-WT IC50 [µM]", "SMILES", 1000, "latin1", 1),
    }
    native = {}
    for aid, spec in native_specs.items():
        native[aid] = read_native(*spec)
        files.append(spec[0])
    records = {}
    for directory in (SOURCE, FOLLOWUP):
        for path in directory.glob("*records_*.json"):
            data = json.loads(path.read_text())
            if data["page_meta"]["next"] or len(data["compound_records"]) != data["page_meta"]["total_count"]:
                raise ValueError("공식 화합물 record 페이지 누락")
            records.update({row["record_id"]: row for row in data["compound_records"]})
            files.append(path)
    observations = []
    for path in (ROOT / "data/raw/chembl_full_20261020/responses").glob("activities*.json"):
        selected = [row for row in json.loads(path.read_text()).get("activities", []) if row["assay_chembl_id"] in ASSAYS]
        if selected:
            observations.extend(selected)
            files.append(path)
    audit_path = ROOT/"data/interim/audit_chembl_full_20261020/activity_audit.csv"
    audit = pd.read_csv(audit_path, dtype=str, keep_default_na=False).set_index("activity_id")
    files.append(audit_path)
    rows = []
    for activity in observations:
        rec = records[activity["record_id"]]
        aid = activity["assay_chembl_id"]
        if rec["document_chembl_id"] != activity["document_chembl_id"] or rec["molecule_chembl_id"] != activity["molecule_chembl_id"]:
            raise ValueError("화합물 record·활동·문헌 연결 불일치")
        name = rec.get("compound_name") or ""
        relation, value = activity["standard_relation"], activity["standard_value"]
        result = {"activity_id": activity["activity_id"], "assay_chembl_id": aid,
                  "document_chembl_id": activity["document_chembl_id"], "record_id": rec["record_id"],
                  "molecule_chembl_id": rec["molecule_chembl_id"], "record_name": name,
                  "standard_relation": relation, "standard_value_nM": value,
                  "source_structure_check": "not_reviewed", "training_approved": False}
        if aid == "CHEMBL5737421":
            keys = re.findall(r"Compound (G-\d+)", name)
            texts = [source64.get(key, "") for key in keys]
            matches = any(agrees(parse_measurement(text), relation, value) for text in texts)
            check = "numeric_relation_match" if matches else "numeric_mismatch_or_unmapped"
        elif aid in {"CHEMBL3705421", "CHEMBL5729820"}:
            keys = re.findall(r"US8846699, (\d+)", name)
            texts = [source173.get(key, "") for key in keys]
            matches = any(agrees(parse_measurement(text, 1000), relation, value) for text in texts)
            check = "numeric_relation_match_source_key_ambiguous" if matches and len(keys)>1 else "numeric_relation_match" if matches else "numeric_mismatch_or_unmapped"
        elif aid == "CHEMBL5733991":
            keys = re.findall(r"US9987276, Compound (I-\d+)", name)
            texts = [source246.get(key, "") for key in keys]
            matches = False
            if any(category_midpoint(text, relation, value) for text in texts):
                check = "source_interval_midpoint_not_exact"
            elif texts and any(text in {"A", "E"} for text in texts) and relation in {"<", ">"}:
                check = "source_bound_category_not_exact"
            else:
                check = "source_category_or_key_requires_review"
            result["source_category_intervals_nM"] = json.dumps([interval_for_category(text) for text in texts])
        else:
            pieces = [p.strip() for p in rec["compound_key"].split(";")]
            keys = [piece for piece in pieces if piece in native[aid]]
            texts = [native[aid][key]["text"] for key in keys]
            matches = any(agrees(native[aid][key]["measurement"], relation, value) for key in keys)
            check = "numeric_relation_match" if matches else "numeric_mismatch_or_unmapped"
            structure = canonical(audit.loc[str(activity["activity_id"]), "canonical_smiles"])
            result["source_structure_check"] = "isomeric_graph_match" if structure and any(native[aid][key]["canonical"] == structure for key in keys) else "graph_difference_or_unmapped_requires_review"
        result.update(source_keys=json.dumps(keys), source_values=json.dumps(texts), source_check=check,
                      numeric_relation_matched=matches, source_table_key_ambiguous=len(keys)>1)
        rows.append(result)
    frame = pd.DataFrame(rows)
    if len(frame) != 787 or frame.activity_id.duplicated().any():
        raise ValueError("관측 ID·행수 불일치")
    alias_ids = {"CHEMBL3705421", "CHEMBL5729820"}
    blocks = []
    for aid in sorted(alias_ids):
        part = frame.loc[frame.assay_chembl_id.eq(aid)]
        blocks.append(sorted((r.molecule_chembl_id, r.standard_relation, r.standard_value_nM) for r in part.itertuples()))
    if blocks[0] != blocks[1]:
        raise ValueError("두 assay ID의 동일 수치 블록 가정 불일치")
    out.mkdir(parents=True)
    frame.to_csv(out/"measurement_source_crosscheck.csv", index=False)
    summary = {"reviewed_observations": len(frame), "assays": len(ASSAYS),
               "per_assay": {aid: {"rows": len(g), "source_checks": g.source_check.value_counts().to_dict(),
                   "structure_checks": g.source_structure_check.value_counts().to_dict()} for aid,g in frame.groupby("assay_chembl_id")},
               "same_source_duplicate_assay_ids": sorted(alias_ids), "duplicate_block_rows_per_assay":173,
               "training_approved":0, "claim_limit":"수치·구조 대조는 조건·표적·주 코호트 승인과 별개"}
    manifest = {"created_at_utc":datetime.now(timezone.utc).isoformat(), "summary":summary,
                "inputs_sha256":{str(p.relative_to(ROOT)):digest(p) for p in set(files)},
                "outputs_sha256":{"measurement_source_crosscheck.csv":digest(out/"measurement_source_crosscheck.csv")}}
    (out/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
