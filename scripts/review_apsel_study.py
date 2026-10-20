"""Apsel 209건의 원문 근거·라벨·화합물 ID를 검토한다. 학습 승인 안 함."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def main():
    out = ROOT / "data/interim/apsel_review_20261020"
    if out.exists():
        raise FileExistsError(f"기존 검토 보호: {out}")
    audit_path = ROOT / "data/interim/audit_chembl_full_20261020/activity_audit.csv"
    records_path = ROOT / "data/raw/larger_assay_sources_20261020/apsel_records.json"
    values_path = ROOT / "configs/apsel_figure2_values.csv"
    audit = pd.read_csv(audit_path, dtype=str, keep_default_na=False)
    frame = audit.loc[audit.assay_chembl_id.eq("CHEMBL1243977")].copy()
    assert len(frame) == frame.activity_id.nunique() == 209
    records = json.loads(records_path.read_text())
    assert records["page_meta"]["next"] is None
    by_record = {r["record_id"]: r for r in records["compound_records"]}
    raw = []
    input_files = [audit_path, records_path, values_path, Path(__file__).resolve()]
    for path in sorted((ROOT / "data/raw/chembl_full_20261020/responses").glob("activities*.json")):
        matches = [r for r in json.loads(path.read_text()).get("activities", [])
                   if r.get("assay_chembl_id") == "CHEMBL1243977"]
        if matches:
            raw.extend(matches)
            input_files.append(path)
    connection = []
    for activity in raw:
        record = by_record[activity["record_id"]]
        assert record["molecule_chembl_id"] == activity["molecule_chembl_id"]
        assert record["document_chembl_id"] == activity["document_chembl_id"] == "CHEMBL1240340"
        connection.append({"activity_id": str(activity["activity_id"]), "record_id": record["record_id"],
                           "source_compound_key": record["compound_key"]})
    frame = frame.merge(pd.DataFrame(connection), on="activity_id", validate="one_to_one")
    numeric = pd.to_numeric(frame.standard_value, errors="coerce")
    frame["numeric_exact_candidate"] = frame.standard_relation.eq("=") & frame.standard_units.eq("nM") & numeric.gt(0)
    frame["above_main_reported_dose_range"] = frame.numeric_exact_candidate & numeric.gt(50000)
    frame["value_100uM_requires_source_review"] = frame.numeric_exact_candidate & numeric.eq(100000)
    frame["review_decision"] = "hold_species_variant_full_table_and_protocol_unresolved"
    frame["training_approved"] = False
    checked = []
    for item in pd.read_csv(values_path, dtype=str).to_dict("records"):
        match = frame.loc[frame.source_compound_key.eq(item["compound_key"])]
        assert len(match) == 1
        row = match.iloc[0]
        expected_nM = float(item["value_uM"]) * 1000
        assert row.standard_relation == item["relation"]
        assert float(row.standard_value) == expected_nM
        checked.append({**item, "source_locator": "Main Figure 2a, EGFR row, page 693",
                        "record_id": row.record_id, "activity_id": row.activity_id,
                        "molecule_chembl_id": row.molecule_chembl_id,
                        "value_nM": expected_nM, "matched": True, "training_approved": False})
    source_dirs = [ROOT / "data/raw" / d for d in ("larger_assay_sources_20261020", "larger_assay_followup_20261020",
        "apsel_materials_20261020", "apsel_materials_20261020_mirrors", "apsel_materials_20261020_publisher")]
    for directory in source_dirs:
        manifest_path = directory / "manifest.json"
        input_files.append(manifest_path)
        for record in json.loads(manifest_path.read_text())["sources"]:
            if record.get("path"):
                path = ROOT / record["path"]
                assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
    out.mkdir(parents=True)
    frame.to_csv(out / "measurement_review.csv", index=False)
    pd.DataFrame(checked).to_csv(out / "figure2_crosscheck.csv", index=False)
    summary = {"measurements": 209, "numeric_exact_candidates": int(frame.numeric_exact_candidate.sum()),
               "not_exact_or_missing_standard_value": int((~frame.numeric_exact_candidate).sum()),
               "source_figure_observations_matched": len(checked),
               "exact_100uM_values_requiring_source_review": int(frame.value_100uM_requires_source_review.sum()),
               "above_reported_main_dose_range": int(frame.above_main_reported_dose_range.sum()),
               "atp_uM_primary_main": 10, "inhibitor_range_uM_primary_main": [0.001, 50],
               "species_verified": False, "variant_verified": False, "full_SI_table_verified": False,
               "training_approved_rows": 0,
               "decision": "209건 보류; 100uM 값을 부등호나 비활성 sentinel로 임의 변경하지 않음"}
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "summary": summary,
                "inputs_sha256": {str(p.relative_to(ROOT)): digest(p) for p in input_files},
                "outputs_sha256": {p.name: digest(p) for p in out.glob("*.csv")}}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
