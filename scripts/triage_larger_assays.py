"""기존 감사에서 보류된 대규모 단일 assay의 라벨·출처를 사전 점검한다."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def main():
    audit_path = ROOT / "data/interim/audit_chembl_full_20261020/activity_audit.csv"
    assay_path = ROOT / "data/interim/audit_chembl_full_20261020/assay_review.csv"
    document_path = ROOT / "data/interim/chembl_full_20261020/documents.parquet"
    audit = pd.read_csv(audit_path, dtype=str, keep_default_na=False)
    assays = pd.read_csv(assay_path, dtype=str, keep_default_na=False).set_index("assay_chembl_id")
    documents = pd.read_parquet(document_path).set_index("document_chembl_id")
    out = ROOT / "data/interim/large_assay_triage_20261020"
    if out.exists():
        raise FileExistsError(f"기존 사전 점검 보호: {out}")
    rows = []
    for identifier, group in audit.groupby("assay_chembl_id"):
        if len(group) < 80 or assays.loc[identifier, "variant_screen"] != "unresolved":
            continue
        values = pd.to_numeric(group.standard_value, errors="coerce")
        exact = (group.standard_relation.eq("=") & group.standard_units.eq("nM")
                 & values.gt(0) & np.isfinite(values))
        numeric = values.loc[exact]
        document_id = assays.loc[identifier, "document_chembl_id"]
        doc = documents.loc[document_id]
        rows.append({"assay_chembl_id": identifier, "document_chembl_id": document_id,
                     "document_type": doc.doc_type, "document_title": doc.title,
                     "measurements": len(group), "exact_positive_nM_rows": int(exact.sum()),
                     "unique_exact_numeric_values": int(numeric.nunique()),
                     "non_exact_rows": int(group.standard_relation.ne("=").sum()),
                     "structure_hold_rows": int(group.screen_reasons.str.split(";").apply(lambda r: "structure" in r).sum()),
                     "description": assays.loc[identifier, "description"],
                     "reason": "변이·형식·프로토콜·원 수치·구조의 독립 원문 검토 필요",
                     "training_approved": False})
    frame = pd.DataFrame(rows).sort_values(["exact_positive_nM_rows", "measurements"], ascending=False)
    out.mkdir(parents=True)
    path = out / "large_assay_triage.csv"
    frame.to_csv(path, index=False)
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
                "scope": "최소 80행인 미확정 assay의 검토 우선순위; 원문 승인·학습 적격성 아님",
                "inputs_sha256": {str(p.relative_to(ROOT)): digest(p) for p in (audit_path, assay_path, document_path)},
                "output_sha256": digest(path), "rows": len(frame)}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(frame.drop(columns="description").head(8).to_string(index=False))


if __name__ == "__main__":
    main()
