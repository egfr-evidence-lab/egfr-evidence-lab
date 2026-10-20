"""저자 CSV의 IC50와 단일 농도 억제율을 분리해 미승인 후보를 보존한다."""

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from prioritize_main_cohort import inspect_structure
from review_main_cohort_sources import parse_measurement


ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source=ROOT/"data/raw/main_cohort_sources_20261020_followup/figshare_39124670.csv"
    crosscheck=ROOT/"data/interim/main_cohort_review_20261020/measurement_source_crosscheck.csv"
    audit_path=ROOT/"data/interim/audit_chembl_full_20261020/activity_audit.csv"
    registry=ROOT/"configs/main_cohort_review.json"
    out=ROOT/"data/interim/furan_candidate_20261020"
    if out.exists():
        raise FileExistsError(f"기존 후보 보호: {out}")
    raw=pd.read_csv(source,dtype=str,keep_default_na=False)
    checked=pd.read_csv(crosscheck,dtype=str,keep_default_na=False)
    checked=checked.loc[checked.assay_chembl_id.eq("CHEMBL5382277")]
    by_key={json.loads(r.source_keys)[0]:r for r in checked.itertuples()}
    audit=pd.read_csv(audit_path,dtype=str,keep_default_na=False).set_index("activity_id")
    rows,non_ic50=[],[]
    for original in raw.to_dict("records"):
        key=original["Comp."]
        text=original["EGFRWT IC50 (nM)"]
        measurement=parse_measurement(text)
        if measurement is None:
            non_ic50.append({"compound_key":key,"source_reported":text,"reason":"single_concentration_inhibition_not_IC50","training_ready":False})
            continue
        if measurement[0]!="=" or measurement[1]<=0:
            raise ValueError("새 원문 관계·범위를 별도로 검토해야 합니다.")
        record=by_key[key]
        if record.source_structure_check!="isomeric_graph_match":
            raise ValueError("원 저자 구조와 DB 구조가 다릅니다.")
        structure=inspect_structure(original["SMILE"])
        if structure is None:
            raise ValueError("파싱 실패·다성분 구조")
        value=measurement[1]
        db_value=float(record.standard_value_nM)
        status="exact_numeric_match" if db_value==value else "compatible_with_integer_rounding_unconfirmed"
        if status!="exact_numeric_match" and not (db_value.is_integer() and abs(db_value-value)<=.5):
            raise ValueError("작은 정밀도 차이 범위를 벗어난 수치")
        row=audit.loc[record.activity_id]
        rows.append({"compound_key":key,"source_smiles":original["SMILE"],"canonical_isomeric_smiles":structure[0],
                     "connectivity_group":structure[1],"scaffold_smiles":structure[2],
                     "activity_id":record.activity_id,"molecule_chembl_id":record.molecule_chembl_id,
                     "assay_chembl_id":"CHEMBL5382277","source_IC50_nM":value,"pIC50_source":9-np.log10(value),
                     "chembl_IC50_nM":db_value,"source_to_db_numeric_check":status,
                     "original_audit_reasons":row.screen_reasons,
                     "training_ready":False,"hold_reason":"human_species_and_referenced_protocol_pending"})
    frame=pd.DataFrame(rows)
    if len(frame)!=45 or len(non_ic50)!=4 or frame.activity_id.nunique()!=45 or frame.canonical_isomeric_smiles.nunique()!=45:
        raise ValueError("원문·DB 연결의 누락·중복")
    counts=frame.drop_duplicates("connectivity_group").scaffold_smiles.value_counts()
    out.mkdir(parents=True)
    frame.to_csv(out/"IC50_candidates_not_training_ready.csv",index=False)
    pd.DataFrame(non_ic50).to_csv(out/"single_concentration_not_IC50.csv",index=False)
    summary={"source_compounds":49,"exact_IC50_rows":45,"single_concentration_rows_excluded":4,
             "unique_isomeric_structures":45,"connectivity_groups":frame.connectivity_group.nunique(),
             "scaffolds":len(counts),"largest_scaffold_connectivity_groups":int(counts.max()),
             "largest_scaffold_fraction_by_connectivity":float(counts.max()/counts.sum()),
             "source_IC50_nM_range":[float(frame.source_IC50_nM.min()),float(frame.source_IC50_nM.max())],
             "source_pIC50_span":float(frame.pIC50_source.max()-frame.pIC50_source.min()),
             "numeric_crosscheck_counts":frame.source_to_db_numeric_check.value_counts().to_dict(),
             "training_ready":False,"model_training_executed":False,
             "scope":"수치·구조 대조 완료 후보; human 종 유래와 인용 실험법 원문 확인 전 학습 미승인"}
    manifest={"created_at_utc":datetime.now(timezone.utc).isoformat(),"summary":summary,
              "inputs_sha256":{str(p.relative_to(ROOT)):digest(p) for p in [source,crosscheck,audit_path,registry,Path(__file__).resolve()]},
              "outputs_sha256":{p.name:digest(p) for p in out.glob("*.csv")}}
    (out/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
