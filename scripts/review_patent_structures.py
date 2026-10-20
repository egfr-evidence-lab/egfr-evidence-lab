"""특허 구조 연결을 원 화합물 키·분석 질량으로 점검한다. 질량 일치만으로 구조 승인하지 않는다."""

from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re

import pandas as pd
from rdkit import Chem
from rdkit.Chem import rdMolDescriptors

from review_patent_assay import TableRows


ROOT=Path(__file__).resolve().parents[1]
PROTON_MASS=1.007276466621
MASS_FLAG_DA=.25  # 원문 1자리 MS의 큰 불일치를 찾는 작업 기준; 구조·MS 정확도 합격선 아님.


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts=[]
    def handle_data(self,text):
        self.parts.append(text)


def plain(html):
    parser=Text()
    parser.feed(html)
    return " ".join(" ".join(parser.parts).split())


def extract_source_masses(html):
    result={}
    for chunk in re.findall(r"<tables\b.*?</tables>",html,re.S):
        parser=TableRows()
        parser.feed(chunk)
        for row in parser.rows:
            if len(row)==7 and re.fullmatch(r"G-\d+",row[1]) and re.fullmatch(r"\d+\.\d+",row[-1]):
                result[row[1]]={"reported_M_plus_H":float(row[-1]),"source_location":"synthetic_table_explicit_G_key"}
    # 연속 합성 문단에는 다른 중간체·예시의 MS가 섞일 수 있어 자동 최종물 연결을 하지 않는다.
    return result


def expected_m_plus_h(smiles):
    mol=Chem.MolFromSmiles(smiles)
    if mol is None or len(Chem.GetMolFrags(mol))!=1 or Chem.GetFormalCharge(mol)!=0:
        raise ValueError("중성 단일 성분의 [M+H]+ 비교 범위를 벗어납니다.")
    return rdMolDescriptors.CalcExactMolWt(mol)+PROTON_MASS


def main():
    source=ROOT/"data/raw/main_cohort_sources_20261020/US11155546B2.html"
    cross=ROOT/"data/interim/main_cohort_review_20261020/measurement_source_crosscheck.csv"
    audit_path=ROOT/"data/interim/audit_chembl_full_20261020/activity_audit.csv"
    out=ROOT/"data/interim/patent_structure_review_20261020_v2"
    if out.exists():
        raise FileExistsError(f"기존 검토 보호: {out}")
    masses=extract_source_masses(source.read_text())
    data=pd.read_csv(cross,dtype=str,keep_default_na=False)
    data=data.loc[data.assay_chembl_id.eq("CHEMBL5737421")]
    audit=pd.read_csv(audit_path,dtype=str,keep_default_na=False).set_index("activity_id")
    rows=[]
    for item in data.itertuples():
        keys=json.loads(item.source_keys)
        smiles=audit.loc[item.activity_id,"canonical_smiles"]
        expected=expected_m_plus_h(smiles)
        comparisons=[{"compound_key":key,**masses[key],"DB_calculated_M_plus_H":expected,
                     "absolute_difference_Da":abs(masses[key]["reported_M_plus_H"]-expected)} for key in keys if key in masses]
        flagged=[entry for entry in comparisons if entry["absolute_difference_Da"]>MASS_FLAG_DA]
        rows.append({"activity_id":item.activity_id,"record_id":item.record_id,
                     "molecule_chembl_id":item.molecule_chembl_id,"record_name":item.record_name,
                     "source_keys":item.source_keys,"canonical_smiles":smiles,"calculated_M_plus_H":expected,
                     "source_mass_comparisons":json.dumps(comparisons,ensure_ascii=False),
                     "source_keys_with_MS":len(comparisons),"large_mass_discrepancy_keys":json.dumps([e["compound_key"] for e in flagged]),
                     "record_alias_ambiguous":len(keys)>1,"full_structure_verified":False,"training_ready":False})
    frame=pd.DataFrame(rows)
    if len(frame)!=64 or frame.activity_id.nunique()!=64:
        raise ValueError("특허 관측 행수·ID 불일치")
    out.mkdir(parents=True)
    frame.to_csv(out/"structure_mass_review.csv",index=False)
    (out/"source_masses.json").write_text(json.dumps(masses,ensure_ascii=False,indent=2)+"\n")
    summary={"observations":64,"observations_with_multiple_original_compound_keys":int(frame.record_alias_ambiguous.sum()),
             "observations_with_any_original_MS":int(frame.source_keys_with_MS.gt(0).sum()),
             "observations_with_any_large_mass_discrepancy":int(frame.large_mass_discrepancy_keys.ne("[]").sum()),
             "mass_flag_tolerance_Da":MASS_FLAG_DA,"full_structure_verified":0,"training_ready":0,
             "claim_limit":"질량 불일치 후보는 구조·키 연결 추가 검토 사유. 질량 일치도 위치·입체·결합 구조의 일치를 보증하지 않음"}
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    inputs=[source,cross,audit_path,Path(__file__).resolve()]
    manifest={"created_at_utc":datetime.now(timezone.utc).isoformat(),"summary":summary,
              "inputs_sha256":{str(p.relative_to(ROOT)):digest(p) for p in inputs},
              "outputs_sha256":{p.name:digest(p) for p in out.iterdir()}}
    (out/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print(frame.loc[frame.large_mass_discrepancy_keys.ne("[]"),["record_name","large_mass_discrepancy_keys"]].to_string(index=False))


if __name__=="__main__":
    main()
