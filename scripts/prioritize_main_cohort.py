"""전체 assay의 주 코호트 검토 우선순위. 구조 재계산은 학습 승인이 아니다."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem.Scaffolds import MurckoScaffold


ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_structure(smiles):
    molecule = Chem.MolFromSmiles(smiles) if smiles else None
    if molecule is None or len(Chem.GetMolFrags(molecule)) != 1:
        return None
    canonical = Chem.MolToSmiles(molecule, isomericSmiles=True)
    # 입체이성질체를 같은 평가 그룹에 두며 분자의 입체정보 자체는 보존한다.
    connectivity = Chem.MolToSmiles(molecule, isomericSmiles=False)
    scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=molecule, includeChirality=False)
    return canonical, connectivity, scaffold or "acyclic:" + connectivity


def run(out):
    if out.exists():
        raise FileExistsError(f"기존 후보 검토 보호: {out}")
    audit_path = ROOT / "data/interim/audit_chembl_full_20261020/activity_audit.csv"
    assay_path = ROOT / "data/interim/audit_chembl_full_20261020/assay_review.csv"
    doc_path = ROOT / "data/interim/chembl_full_20261020/documents.parquet"
    holds_path = ROOT / "configs/source_review_holds.json"
    frame = pd.read_csv(audit_path, dtype=str, keep_default_na=False)
    assays = pd.read_csv(assay_path, dtype=str, keep_default_na=False).set_index("assay_chembl_id")
    docs = pd.read_parquet(doc_path).astype(object).fillna("").set_index("document_chembl_id")
    held = {item["assay_chembl_id"] for item in json.loads(holds_path.read_text())["holds"]}
    held.add("CHEMBL1243977")  # 별도 Apsel 검토에서 이미 전체 보류.
    cache = {text: inspect_structure(text) for text in frame.canonical_smiles.unique()}
    rows = []
    for aid, group in frame.groupby("assay_chembl_id", sort=True):
        assay = assays.loc[aid]
        doc = docs.loc[assay.document_chembl_id]
        numeric = pd.to_numeric(group.standard_value, errors="coerce")
        exact = (group.standard_relation.eq("=") & group.standard_units.eq("nM") & numeric.gt(0) & np.isfinite(numeric))
        values = numeric[exact]
        parsed = [cache[s] for s in group.loc[exact, "canonical_smiles"] if cache[s] is not None]
        canonical = {p[0] for p in parsed}
        grouped = {p[1]: p[2] for p in parsed}
        counts = Counter(grouped.values())
        signature_rows = sorted((r.molecule_chembl_id, r.standard_relation, r.standard_value, r.standard_units)
                                for r in group.itertuples())
        signature = hashlib.sha256(json.dumps([assay.document_chembl_id, signature_rows]).encode()).hexdigest()
        rows.append({"assay_chembl_id": aid, "document_chembl_id": assay.document_chembl_id,
                     "document_type": doc.doc_type, "doi": doc.doi, "pmid": doc.pubmed_id, "title": doc.title,
                     "raw_rows": len(group), "exact_positive_nM_rows": int(exact.sum()),
                     "recomputed_single_component_structures": len(canonical),
                     "connectivity_groups": len(grouped), "recomputed_scaffolds": len(counts),
                     "largest_scaffold_fraction": max(counts.values()) / len(grouped) if grouped else None,
                     "pIC50_min": float(9-np.log10(values.max())) if len(values) else None,
                     "pIC50_max": float(9-np.log10(values.min())) if len(values) else None,
                     "potential_duplicate_rows": int(group.potential_duplicate.eq("1").sum()),
                     "validity_comment_rows": int(group.data_validity_comment.ne("").sum()),
                     "structure_hold_rows": int(group.screen_reasons.str.split(";").apply(lambda x: "structure" in x).sum()),
                     "variant_screen": assay.variant_screen, "format_screen": assay.format_screen,
                     "confidence_score": assay.confidence_score, "assay_hold_reasons": assay.assay_screen_reasons,
                     "description": assay.description, "known_source_hold": aid in held,
                     "same_document_measurement_signature": signature, "training_approved": False})
    table = pd.DataFrame(rows)
    signature_sizes = table.same_document_measurement_signature.value_counts()
    table["identical_document_measurement_blocks"] = table.same_document_measurement_signature.map(signature_sizes)
    table["wt_priority"] = table.variant_screen.eq("WT").astype(int)
    table["biochemical_priority"] = table.format_screen.eq("biochemical_candidate").astype(int)
    table = table.sort_values(["known_source_hold", "wt_priority", "biochemical_priority", "recomputed_single_component_structures"],
                              ascending=[True, False, False, False])
    # 20건은 탐색 표를 줄이는 작업 기준이며 학습 승인 최소 표본 수가 아니다.
    queue = table.loc[table.exact_positive_nM_rows.ge(20) & table.variant_screen.isin(["WT", "unresolved"])].copy()
    out.mkdir(parents=True)
    table.to_csv(out / "all_assay_inventory.csv", index=False)
    queue.to_csv(out / "source_priority_queue.csv", index=False)
    manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
                "scope": "원문 검토 순서; 구조 재계산·표 규모는 과학적 승인 아님",
                "measurements": int(table.raw_rows.sum()), "assays": len(table), "queue_assays": len(queue),
                "new_training_approved": 0,
                "inputs_sha256": {str(p.relative_to(ROOT)): digest(p) for p in [audit_path, assay_path, doc_path, holds_path, Path(__file__).resolve()]},
                "outputs_sha256": {p.name: digest(p) for p in out.glob("*.csv")}}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(queue[["assay_chembl_id", "raw_rows", "exact_positive_nM_rows", "recomputed_single_component_structures", "recomputed_scaffolds", "largest_scaffold_fraction", "known_source_hold"]].head(16).to_string(index=False))
    print(f"전체 {manifest['measurements']}건·{len(table)}실험, 검토 대기 {len(queue)}실험; 신규 학습 승인0")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="data/interim/main_cohort_inventory_20261020")
    run(ROOT / parser.parse_args().output_dir)
