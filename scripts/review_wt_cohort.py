"""보관 원문·정책으로 WT 조건 검토, 표 수치 대조, 15개 실험 쌍 검증을 재현한다."""

from html.parser import HTMLParser
from itertools import combinations
import json
from pathlib import Path
import re

import pandas as pd

from egfr_lab.data.comparability import agreement_metrics, compare_protocols
from egfr_lab.data.store import atomic_bytes, atomic_json, digest, utc_now


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "data/interim/audit_chembl_full_20261020"
RAW = ROOT / "data/raw/wt_literature_20261020"
OUTPUT = ROOT / "data/interim/cohort_review_20261020"


class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables, self.table, self.row = [], [], []
        self.depth, self.cell = 0, None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.depth += 1
        if self.depth and tag == "tr":
            self.row = []
        if self.depth and tag in ("th", "td"):
            self.cell = []

    def handle_data(self, text):
        if self.cell is not None:
            self.cell.append(text)

    def handle_endtag(self, tag):
        if self.depth and tag in ("th", "td") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        if self.depth and tag == "tr":
            self.table.append(self.row)
        if tag == "table":
            self.depth -= 1
            if self.depth == 0:
                self.tables.append(self.table)
                self.table = []


def source_values(html):
    parser = Tables()
    parser.feed(html)
    values = {}
    for table in parser.tables:
        if not table or len(table[0]) < 2 or table[0][1] != "EGFR WT IC50 (nM)":
            continue
        for row in table[1:]:
            key = row[0]
            if key in values:
                raise ValueError("원문 화합물 번호가 중복됩니다.")
            values[key] = float(re.match(r"[\d.]+", row[1]).group())
    if set(values) != {"2", *(str(x) for x in range(8, 29))}:
        raise ValueError("원문 Tables 1·3의 WT 농도 22개를 확인하지 못했습니다.")
    return values


def main():
    if OUTPUT.exists():
        raise ValueError("기존 문헌 검토 결과를 보호합니다. 새 실행 폴더를 사용하세요.")
    paths = [AUDIT / "candidate_measurements.csv", AUDIT / "activity_audit.csv", ROOT / "configs/cohort_policy.json",
             ROOT / "configs/wt_assay_evidence.json", RAW / "allenamide_main.html", RAW / "wt_expansion_metadata.json",
             RAW / "allenamide_compound_records.json", RAW / "landrum_curation.ipynb"]
    fetch_manifest_bytes = (RAW / "manifest.json").read_bytes()
    fetch_manifest = json.loads(fetch_manifest_bytes)
    for r in fetch_manifest["records"]:
        path = ROOT / r["path"]
        if digest(path.read_bytes()) != r["sha256"]:
            raise ValueError("문헌 메타데이터 해시가 다릅니다.")
        paths.append(path)
    for r in fetch_manifest["assets"]:
        if r["path"] and digest((ROOT / r["path"]).read_bytes()) != r["sha256"]:
            raise ValueError("보관 부속자료 해시가 다릅니다.")
    inputs = {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in paths}
    policy = json.loads((ROOT / "configs/cohort_policy.json").read_text())
    evidence = json.loads((ROOT / "configs/wt_assay_evidence.json").read_text())
    evidence_map = {r["assay_chembl_id"]: r for r in evidence["assays"]}
    candidates = pd.read_csv(AUDIT / "candidate_measurements.csv", dtype=str, keep_default_na=False)
    wt = candidates[candidates.variant_screen.eq("WT")].copy()
    wt["pIC50_computed"] = pd.to_numeric(wt.pIC50_computed)
    if set(wt.assay_chembl_id) != set(evidence_map):
        raise ValueError("WT 후보와 검토한 문헌 목록이 다릅니다.")
    # 문헌 화합물 번호 → 공식 record ID → 원 활동 ID를 연결한다. 값만 같다고 연결하지 않는다.
    paper_values = source_values((RAW / "allenamide_main.html").read_text())
    records_json = json.loads((RAW / "allenamide_compound_records.json").read_text())
    records = records_json["compound_records"]
    if records_json["page_meta"]["next"] or len(records) != records_json["page_meta"]["total_count"]:
        raise ValueError("compound_record 수집이 미완료입니다.")
    record_map = {r["record_id"]: r for r in records}
    original = ROOT / "data/raw/chembl_full_20261020"
    original_manifest = json.loads((original / "manifest.json").read_text())
    inputs[str((original / "manifest.json").relative_to(ROOT))] = digest((original / "manifest.json").read_bytes())
    anchor = wt[wt.assay_chembl_id.eq("CHEMBL4258549")].copy()
    wanted = set(anchor.activity_id)
    activity_records = {}
    for key, record in original_manifest["requests"].items():
        if not key.startswith("activities_"):
            continue
        path = original / record["file"]
        blob = path.read_bytes()
        if digest(blob) != record["sha256"]:
            raise ValueError("원 활동 응답이 변경됐습니다.")
        for activity in json.loads(blob)["activities"]:
            if str(activity["activity_id"]) in wanted:
                activity_records[str(activity["activity_id"])] = activity
    checks = []
    for row in anchor.to_dict("records"):
        original_row = activity_records[row["activity_id"]]
        record = record_map[original_row["record_id"]]
        if record["document_chembl_id"] != row["document_chembl_id"] or record["molecule_chembl_id"] != row["molecule_chembl_id"]:
            raise ValueError("화합물 record 연결이 다릅니다.")
        compound_key = record["compound_key"]
        measured = float(row["standard_value"])
        expected = paper_values[compound_key]
        if row["standard_units"] != "nM" or abs(measured - expected) > 1e-9:
            raise ValueError("원문 WT 농도와 활동값이 다릅니다.")
        checks.append({"activity_id": row["activity_id"], "record_id": original_row["record_id"],
                       "molecule_chembl_id": row["molecule_chembl_id"], "source_compound_key": compound_key,
                       "source_table": "Table 1" if int(compound_key) < 20 else "Table 3",
                       "source_nM": expected, "chembl_nM": measured, "matched": True})
    if len(checks) != 22 or len({r["source_compound_key"] for r in checks}) != 22:
        raise ValueError("원문 22개 화합물이 일대일로 연결되지 않았습니다.")
    summaries, pairs = [], []
    for assay_id, group in wt.groupby("assay_chembl_id"):
        summaries.append({**evidence_map[assay_id], "measurements": len(group),
                          "structures": group.structure_group.nunique(), "scaffolds": group.scaffold_smiles.nunique(),
                          "pIC50_min": group.pIC50_computed.min(), "pIC50_max": group.pIC50_computed.max(),
                          "pIC50_span": group.pIC50_computed.max() - group.pIC50_computed.min()})
    # 중앙값은 일치도 진단을 위한 대표값일 뿐 최종 학습 라벨 통합이 아니다.
    per_assay = {a: g.groupby("structure_group").pIC50_computed.median() for a, g in wt.groupby("assay_chembl_id")}
    calibration_groups = set()
    gate = policy["cross_assay_pooling_requires"]
    for a, b in combinations(sorted(per_assay), 2):
        common = per_assay[a].index.intersection(per_assay[b].index)
        calibration_groups.update(common)
        metrics = agreement_metrics(per_assay[a].loc[common], per_assay[b].loc[common], gate)
        protocols = compare_protocols(evidence_map[a], evidence_map[b], gate["critical_fields"])
        pairs.append({"assay_a": a, "assay_b": b, **metrics, **protocols,
                      "pooling_allowed": metrics["statistical_gate_passed"] and protocols["protocols_complete_and_equal"]})
    wt["context_decision"] = wt.assay_chembl_id.map({k: r["decision"] for k, r in evidence_map.items()})
    wt["calibration_only_if_used_for_compatibility"] = wt.structure_group.isin(calibration_groups)
    wt["training_ready"] = False
    anchor = wt[wt.assay_chembl_id.eq("CHEMBL4258549")].merge(pd.DataFrame(checks), on=["activity_id", "molecule_chembl_id"], validate="one_to_one")
    notebook = json.loads((RAW / "landrum_curation.ipynb").read_text())
    code = "\n".join("".join(c.get("source", [])) for c in notebook["cells"])
    full_audit = pd.read_csv(AUDIT / "activity_audit.csv", dtype=str, keep_default_na=False)
    expansion = full_audit.loc[full_audit.variant_screen.eq("WT") & full_audit.screen_reasons.eq("species_unclear")].copy()
    expansion["pIC50_computed"] = pd.to_numeric(expansion.pIC50_computed)
    keys = ["assay_chembl_id", "document_chembl_id", "document_doi", "document_pubmed_id"]
    priority = expansion.groupby(keys).agg(measurements=("activity_id", "size"), structures=("structure_group", "nunique"),
                                          scaffolds=("scaffold_smiles", "nunique"), pIC50_min=("pIC50_computed", "min"),
                                          pIC50_max=("pIC50_computed", "max")).reset_index()
    extra_metadata = json.loads((RAW / "wt_expansion_metadata.json").read_text())["resultList"]["result"]
    by_pmid = {r["id"]: r for r in extra_metadata}
    by_doi = {r.get("doi", "").lower(): r for r in extra_metadata}
    access = []
    for row in priority.to_dict("records"):
        meta = by_pmid.get(row["document_pubmed_id"]) or by_doi.get(row["document_doi"].lower())
        if meta and meta.get("doi", "").lower() != row["document_doi"].lower():
            raise ValueError("확장 검토 문헌 DOI가 메타데이터와 다릅니다.")
        access.append({"pmcid": meta.get("pmcid", "") if meta else "", "metadata_found": bool(meta),
                       "primary_methods_reviewed": False,
                       "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/" + meta["pmcid"] + "/" if meta and meta.get("pmcid") else "https://doi.org/" + row["document_doi"]})
    priority = pd.concat([priority, pd.DataFrame(access)], axis=1).sort_values(["structures", "scaffolds", "assay_chembl_id"], ascending=[False, False, True])
    validation = {"source_table_matched_measurements": len(checks), "wt_measurements_preserved": len(wt),
                  "assay_pairs": len(pairs), "max_shared_structures": max(r["shared_structures"] for r in pairs),
                  "pairs_meeting_5_shared_floor": sum(r["shared_structures"] >= 5 for r in pairs),
                  "allowed_pooling_pairs": sum(r["pooling_allowed"] for r in pairs),
                  "primary_methods_reviewed_assays": 1, "primary_methods_unavailable_assays": 5,
                  "source_code_uses_strict_greater_than_minOverlap": "ovl>:minOverlap" in code,
                  "source_code_default_minOverlap_is_5": "minOverlap=5" in code,
                  "context_pilot_measurements": len(anchor), "benchmark_training_ready": False,
                  "calibration_structure_groups": len(calibration_groups),
                  "source_expansion_assays": len(priority), "source_expansion_measurements": len(expansion),
                  "source_expansion_assays_with_pmc": int(priority.pmcid.ne("").sum()),
                  "limits": ["원문 표 수치와 공식 화합물 번호 연결 검증; 합성 구조의 독립 재구성은 미수행",
                             "동일 assay라는 맥락의 파일럿 22건; 실험 간 동질성이나 일반화 성능 검증을 뜻하지 않음",
                             "문헌 검토는 AI 수행이며 사람의 독립 이중 검토를 거치지 않음"]}
    if (RAW / "manifest.json").read_bytes() != fetch_manifest_bytes:
        raise ValueError("검토 도중 문헌 수집 매니페스트가 변경됐습니다.")
    OUTPUT.mkdir(parents=True)
    outputs = {}
    for name, frame in (("assay_conditions", pd.DataFrame(summaries)), ("assay_pair_comparability", pd.DataFrame(pairs)),
                        ("source_table_crosscheck", pd.DataFrame(checks)), ("wt_measurement_decisions", wt), ("context_pilot", anchor),
                        ("source_expansion_queue", priority)):
        path = OUTPUT / (name + ".csv")
        atomic_bytes(path, frame.to_csv(index=False).encode("utf-8-sig"))
        outputs[name] = {"path": str(path.relative_to(ROOT)), "rows": len(frame), "sha256": digest(path.read_bytes())}
    snapshot = OUTPUT / "literature_manifest_snapshot.json"
    atomic_bytes(snapshot, fetch_manifest_bytes)
    outputs["literature_manifest_snapshot"] = {"path": str(snapshot.relative_to(ROOT)), "sha256": digest(snapshot.read_bytes())}
    atomic_json(ROOT / "reports/cohort_review_validation.json", validation)
    atomic_json(OUTPUT / "manifest.json", {"created_at_utc": utc_now(), "policy": policy["version"], "state": "review_complete_training_pending",
                                          "inputs": inputs, "outputs": outputs, "validation": validation,
                                          "code_sha256": {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in (Path(__file__), ROOT / "src/egfr_lab/data/comparability.py")}})
    print(json.dumps(validation, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
