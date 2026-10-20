"""새 코호트 후보 검토와 원문·원 관측 보존을 오프라인으로 검증한다."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_manifest(directory):
    manifest=json.loads((directory/"manifest.json").read_text())
    for name,expected in manifest["inputs_sha256"].items():
        assert digest(ROOT/name)==expected,name
    for name,expected in manifest["outputs_sha256"].items():
        assert digest(directory/name)==expected,name
    return manifest


def main():
    source_count=0
    provider_count=0
    for suffix in ["", "_followup", "_maintext", "_reference"]:
        directory=ROOT/f"data/raw/main_cohort_sources_20261020{suffix}"
        manifest=json.loads((directory/"manifest.json").read_text())
        for entry in manifest["sources"]:
            if entry.get("path"):
                path=ROOT/entry["path"]
                assert digest(path)==entry["sha256"]
                source_count+=1
                if entry.get("provider_md5") and entry.get("http_status")==200:
                    assert hashlib.md5(path.read_bytes()).hexdigest()==entry["provider_md5"]
                    if path.suffix==".pdf":
                        assert path.read_bytes().startswith(b"%PDF")
                    provider_count+=1
    inventory=ROOT/"data/interim/main_cohort_inventory_20261020"
    inv=check_manifest(inventory)
    all_assays=pd.read_csv(inventory/"all_assay_inventory.csv")
    assert all_assays.raw_rows.sum()==26600 and len(all_assays)==2425
    assert not all_assays.training_approved.any()
    directory=ROOT/"data/interim/main_cohort_review_20261020"
    review=check_manifest(directory)
    data=pd.read_csv(directory/"measurement_source_crosscheck.csv",dtype=str,keep_default_na=False)
    assert len(data)==data.activity_id.nunique()==787 and set(data.training_approved)=={"False"}
    assert sum(data.source_check.eq("source_interval_midpoint_not_exact"))==180
    for aid in ["CHEMBL3705421","CHEMBL5729820"]:
        assert len(data.loc[data.assay_chembl_id.eq(aid)])==173
    w=data.loc[data.assay_chembl_id.eq("CHEMBL5737421")]
    assert len(w)==64 and w.numeric_relation_matched.eq("True").all()
    assert sum(w.standard_relation.eq("="))==50 and sum(w.standard_relation.eq(">"))==14
    candidate_dir=ROOT/"data/interim/furan_candidate_20261020"
    candidate=check_manifest(candidate_dir)
    c=pd.read_csv(candidate_dir/"IC50_candidates_not_training_ready.csv",dtype=str,keep_default_na=False)
    excluded=pd.read_csv(candidate_dir/"single_concentration_not_IC50.csv")
    assert len(c)==c.activity_id.nunique()==c.canonical_isomeric_smiles.nunique()==45
    assert set(c.training_ready)=={"False"} and len(excluded)==4
    np.testing.assert_allclose(pd.to_numeric(c.pIC50_source),9-np.log10(pd.to_numeric(c.source_IC50_nM)),atol=1e-12)
    assert set(c.loc[c.source_to_db_numeric_check.ne("exact_numeric_match"),"compound_key"])=={"36","56"}
    assert float(c.loc[c.compound_key.eq("36"),"source_IC50_nM"].iloc[0])==25.3
    assert float(c.loc[c.compound_key.eq("56"),"source_IC50_nM"].iloc[0])==24.9
    assert digest(ROOT/"data/interim/audit_chembl_full_20261020/audit_manifest.json")=="2b8b8f29895a91ed0eb09f114d54003fd2339fed28398125fba7b5fa8099de80"
    assert digest(ROOT/"data/interim/cohort_review_20261020/manifest.json")=="d7755b3e54310388b77c6fd775aafcdaaa22b2beee55b9c1596c85880afa4d00"
    assert digest(ROOT/"reports/baseline_pilot_20261020_v2/manifest.json")=="b8e15d1fcef2b2754994d8a39c0169ee0f69f3901cd611fe1a6e29a62f105530"
    assert not (ROOT/"data/raw/main_cohort_sources_20261020_reference/ref28.pdf").read_bytes().startswith(b"%PDF")
    result={"checked_at_utc":datetime.now(timezone.utc).isoformat(),"passed":True,
            "source_response_files_hashed":source_count,"provider_md5_files_checked":provider_count,
            "inventory_measurements":26600,"inventory_assays":2425,"priority_assays":inv["queue_assays"],
            "new_source_crosschecked_observations":787,"source_interval_midpoints_not_exact":180,
            "same_source_173_row_alias_block":True,"WT_patent_numeric_relation_matches":64,
            "furan_IC50_candidates":45,"single_concentration_measurements_separate":4,
            "original_audit_cohort_baseline_manifests_unchanged":True,
            "new_training_approved":0,"new_model_training_executed":False,
            "review_manifest_sha256":digest(directory/"manifest.json"),
            "candidate_manifest_sha256":digest(candidate_dir/"manifest.json")}
    (ROOT/"reports/main_cohort_acquisition_validation.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
