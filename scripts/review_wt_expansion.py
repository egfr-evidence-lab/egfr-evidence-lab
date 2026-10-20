"""보류 WT 원문 검토와 ID 기반 수치 대조를 오프라인 산출물로 보존한다."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_DIRS = [ROOT / "data/raw" / name for name in (
    "wt_expansion_20261020_v1", "wt_expansion_20261020_si", "wt_expansion_20261020_addendum")]
EVIDENCE = ROOT / "configs/wt_expansion_evidence.json"
VALUES = ROOT / "configs/wt_expansion_source_values.csv"
AUDIT = ROOT / "data/interim/audit_chembl_full_20261020/activity_audit.csv"
QUEUE = ROOT / "data/interim/cohort_review_20261020/source_expansion_queue.csv"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def checked_sources():
    records = []
    for directory in RAW_DIRS:
        manifest = json.loads((directory / "manifest.json").read_text())
        for record in manifest["sources"]:
            if record.get("path"):
                path = ROOT / record["path"]
                if sha(path) != record["sha256"]:
                    raise ValueError(f"원문 해시 불일치: {path}")
            records.append(record)
    return records


def crosscheck(audit):
    values = read_csv(VALUES)
    rows = []
    for item in values.to_dict("records"):
        asset = RAW_DIRS[2] / item["record_asset"]
        data = json.loads(asset.read_text())
        if data["page_meta"].get("next"):
            raise ValueError("화합물 record 응답에 미수집 다음 페이지가 있습니다.")
        records = [r for r in data["compound_records"]
                   if r["document_chembl_id"] == item["document_chembl_id"]
                   and r["compound_key"] == item["compound_key"]]
        if len(records) != 1:
            raise ValueError(f"화합물 번호 연결이 유일하지 않습니다: {item}")
        record = records[0]
        match = audit.loc[(audit.document_chembl_id == item["document_chembl_id"])
                          & (audit.assay_chembl_id == item["assay_chembl_id"])
                          & (audit.molecule_chembl_id == record["molecule_chembl_id"])]
        if len(match) != 1:
            raise ValueError(f"원 관측 연결이 유일하지 않습니다: {item}")
        measurement = match.iloc[0]
        if measurement.standard_relation != "=" or measurement.standard_units != "nM":
            raise ValueError("정확한 nM 관측이 아닙니다.")
        paper_value = float(item["reported_value"])
        paper_pic50 = paper_value if item["reported_unit"] == "pIC50" else 9 - math.log10(paper_value)
        chembl_pic50 = 9 - math.log10(float(measurement.standard_value))
        difference = abs(paper_pic50 - chembl_pic50)
        rows.append({**item, "record_id": record["record_id"],
                     "molecule_chembl_id": record["molecule_chembl_id"],
                     "activity_id": measurement.activity_id,
                     "chembl_value_nM": measurement.standard_value,
                     "abs_delta_pic50": difference,
                     "numeric_check": "rounding_match" if difference < 1e-4 else "different_estimate_requires_table",
                     "training_approved": False})
    return pd.DataFrame(rows)


def build(out):
    if out.exists():
        raise FileExistsError(f"기존 검토 보호; 새 출력 폴더 필요: {out}")
    sources = checked_sources()
    evidence = json.loads(EVIDENCE.read_text())
    reviews = pd.DataFrame(evidence["assays"])
    if reviews.assay_chembl_id.duplicated().any() or evidence["training_approved"]:
        raise ValueError("검토 ID 중복 또는 미승인 학습 상태 불일치")
    queue, audit = read_csv(QUEUE), read_csv(AUDIT)
    if not set(reviews.assay_chembl_id) <= set(queue.assay_chembl_id):
        raise ValueError("기존 WT 확대 검토 대상에 없는 실험")
    queue = queue.merge(reviews[["assay_chembl_id", "review_state", "decision"]],
                        on="assay_chembl_id", how="left", validate="one_to_one")
    queue["review_state"] = queue.review_state.fillna("not_started")
    queue["decision"] = queue.decision.fillna("hold_not_reviewed")
    queue["training_approved"] = False
    reviewed = audit.loc[audit.assay_chembl_id.isin(reviews.assay_chembl_id)].merge(
        reviews[["assay_chembl_id", "decision", "review_state"]],
        on="assay_chembl_id", validate="many_to_one")
    reviewed["training_approved"] = False
    species_resolved = reviewed.loc[
        reviewed.assay_chembl_id.isin(["CHEMBL2439336", "CHEMBL5638807"])
        & reviewed.screen_reasons.eq("species_unclear")].copy()
    species_resolved["resolved_issue"] = "species_unclear_only; other source review holds remain"
    conflicts = reviewed.loc[reviewed.assay_chembl_id.isin(["CHEMBL5638814", "CHEMBL5638815"])].copy()
    conflicts["readout_chembl"] = "ADP-Glo"
    conflicts["readout_primary_si"] = "Z'-LYTE"
    checked = crosscheck(audit)
    if len(checked) != 11 or checked.numeric_check.eq("rounding_match").sum() != 8 or len(conflicts) != 8:
        raise ValueError("수치 대조 또는 실험법 충돌 건수가 예상 원문 검토와 다릅니다.")
    out.mkdir(parents=True)
    # 원문을 다시 배포하지 않고 URL·해시·검토 메타데이터만 스냅샷으로 연결한다.
    outputs = {"source_expansion_queue_reviewed.csv": queue,
               "assay_conditions_reviewed.csv": reviews,
               "reviewed_measurements.csv": reviewed,
               "species_issue_resolved_review_rows.csv": species_resolved,
               "source_readout_conflicts.csv": conflicts,
               "source_numeric_crosscheck.csv": checked}
    for name, frame in outputs.items():
        frame.to_csv(out / name, index=False)
    evidence_path = out / "evidence_snapshot.json"
    evidence_path.write_bytes(EVIDENCE.read_bytes())
    summary = {"expansion_queue_assays": len(queue),
               "assays_access_or_review_attempted": len(reviews),
               "reviewed_assay_measurements_all_reasons": len(reviewed),
               "species_issue_resolved_seed_rows": len(species_resolved),
               "readout_conflict_assays": 2, "readout_conflict_measurements": len(conflicts),
               "numeric_observations_crosschecked": len(checked),
               "rounding_matches": int(checked.numeric_check.eq("rounding_match").sum()),
               "different_estimates_requiring_main_table": int(checked.numeric_check.ne("rounding_match").sum()),
               "new_training_approved_rows": 0, "new_pooling_approved_pairs": 0,
               "network_requests_recorded": len(sources),
               "scientific_scope": "방법·수치의 부분 확인; 학습 승인 아님"}
    inputs = [EVIDENCE, VALUES, AUDIT, QUEUE, Path(__file__).resolve()]
    inputs += [d / "manifest.json" for d in RAW_DIRS]
    manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "summary": summary,
                "inputs_sha256": {str(p.relative_to(ROOT)): sha(p) for p in inputs},
                "outputs": {name: {"rows": len(frame), "sha256": sha(out / name)}
                            for name, frame in outputs.items()},
                "evidence_snapshot_sha256": sha(evidence_path)}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def verify(out):
    checked_sources()
    manifest = json.loads((out / "manifest.json").read_text())
    for name, digest in manifest["inputs_sha256"].items():
        if sha(ROOT / name) != digest:
            raise ValueError(f"검토 입력 변경: {name}")
    for name, details in manifest["outputs"].items():
        path = out / name
        if sha(path) != details["sha256"] or len(read_csv(path)) != details["rows"]:
            raise ValueError(f"검토 출력 변경: {name}")
    if sha(out / "evidence_snapshot.json") != manifest["evidence_snapshot_sha256"]:
        raise ValueError("검토 근거 스냅샷 변경")
    for name in ("reviewed_measurements.csv", "species_issue_resolved_review_rows.csv", "source_numeric_crosscheck.csv"):
        if set(read_csv(out / name).training_approved) - {"False"}:
            raise ValueError("보류 자료에 학습 승인 표시가 있습니다.")
    print("원문·입출력 해시·행수·보류 상태 검증 통과")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="data/interim/wt_expansion_review_20261020_v1")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    output = ROOT / args.output_dir
    if args.verify_only:
        verify(output)
    else:
        build(output)
        verify(output)
