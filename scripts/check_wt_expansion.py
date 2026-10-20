"""확대 검토·원문 무결성·범위 상태를 독립적으로 점검한다. 네트워크 없음."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pandas as pd

from review_wt_expansion import verify


ROOT = Path(__file__).resolve().parents[1]


def main():
    review = ROOT / "data/interim/wt_expansion_review_20261020_v1"
    verify(review)
    source_files = 0
    for directory in ("wt_expansion_20261020_v1", "wt_expansion_20261020_si", "wt_expansion_20261020_addendum",
                      "larger_assay_sources_20261020", "larger_assay_followup_20261020"):
        manifest = json.loads((ROOT / "data/raw" / directory / "manifest.json").read_text())
        for record in manifest["sources"]:
            if record.get("path"):
                assert hashlib.sha256((ROOT / record["path"]).read_bytes()).hexdigest() == record["sha256"]
                source_files += 1
    si_dir = ROOT / "data/raw/wt_expansion_20261020_si"
    si_files = 0
    for path in si_dir.glob("figshare_*.json"):
        metadata = json.loads(path.read_text())
        for item in metadata["files"]:
            file = si_dir / f"figshare_{item['id']}.pdf"
            assert file.read_bytes().startswith(b"%PDF")
            assert hashlib.md5(file.read_bytes()).hexdigest() == item["computed_md5"]
            si_files += 1
    patent_dir = ROOT / "data/interim/patent_target_review_20261020"
    patent_manifest = json.loads((patent_dir / "manifest.json").read_text())
    for name, expected in patent_manifest["inputs_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
    patent_path = patent_dir / "target_column_crosscheck.csv"
    assert hashlib.sha256(patent_path.read_bytes()).hexdigest() == patent_manifest["output_sha256"]
    patent = pd.read_csv(patent_path, dtype=str, keep_default_na=False)
    assert len(patent) == patent.activity_id.nunique() == 981
    assert set(patent.training_approved) == {"False"}
    pair = patent.loc[patent.record_id.eq("4509835")]
    assert set(pair.activity_id) == {"28404131", "28406027"}
    assert set(pair.source_check) == {"matches_cot_column_only", "matches_explicit_egfr_column"}
    triage_dir = ROOT / "data/interim/large_assay_triage_20261020"
    triage_manifest = json.loads((triage_dir / "manifest.json").read_text())
    for name, expected in triage_manifest["inputs_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
    assert hashlib.sha256((triage_dir / "large_assay_triage.csv").read_bytes()).hexdigest() == triage_manifest["output_sha256"]
    original_hashes = {
        "data/interim/audit_chembl_full_20261020/audit_manifest.json": "2b8b8f29895a91ed0eb09f114d54003fd2339fed28398125fba7b5fa8099de80",
        "data/interim/cohort_review_20261020/manifest.json": "d7755b3e54310388b77c6fd775aafcdaaa22b2beee55b9c1596c85880afa4d00",
    }
    for name, expected in original_hashes.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
    scope = json.loads((ROOT / "configs/portfolio_scope.json").read_text())
    ids = [m["id"] for m in scope["milestones"]]
    assert ids == ["M1", "M2", "M3", "M4", "M5", "M6"]
    assert all(set(m["depends_on"]) <= set(ids) for m in scope["milestones"])
    project = json.loads((ROOT / "configs/project.json").read_text())
    assert project["phases"][0]["status"] == "in_progress"
    assert project["phases"][1]["status"] in {"planned", "in_progress"}
    assert all(p["status"] == "planned" for p in project["phases"][2:])
    if project["phases"][1]["status"] == "in_progress":
        assert project["educational_baseline"]["benchmark_training_approved"] is False
    holds = json.loads((ROOT / project["curation"]["source_review_holds_path"]).read_text())["holds"]
    assert len(holds) == 5 and "CHEMBL5736995" in {h["assay_chembl_id"] for h in holds}
    queue = pd.read_csv(review / "source_expansion_queue_reviewed.csv")
    attempted = queue.review_state.ne("not_started")
    result = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "passed": True,
              "source_response_files_hashed": source_files, "si_files_md5_verified": si_files,
              "wt_assays_access_or_review_attempted": int(attempted.sum()),
              "wt_seed_rows_covered": int(queue.loc[attempted, "measurements"].sum()),
              "patent_classification_counts": patent.source_check.value_counts().to_dict(),
              "original_audit_and_cohort_manifests_unchanged": True,
              "portfolio_milestones": ids, "source_hold_assays": len(holds),
              "validation_scope": "wt_expansion_review_not_later_educational_baseline",
              "new_training_approved_rows": 0, "model_training_executed_in_this_wt_review": False}
    (ROOT / "reports/wt_expansion_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
