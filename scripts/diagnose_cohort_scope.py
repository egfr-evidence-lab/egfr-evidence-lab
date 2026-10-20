"""보류 후보를 포함한 자료·분할·화학 거리 진단. 예측 모델은 학습하지 않는다."""

from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path

import numpy as np
import pandas as pd
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator
from sklearn.model_selection import GroupKFold, KFold

from prioritize_main_cohort import inspect_structure


ROOT=Path(__file__).resolve().parents[1]


def concentration_summary(values):
    values=np.asarray(values,dtype=float)
    if not len(values) or not np.isfinite(values).all() or np.any(values<=0):
        raise ValueError("농도는 양의 유한 수여야 합니다.")
    labels=9-np.log10(values)
    return {"IC50_nM_min":float(values.min()),"IC50_nM_median":float(np.median(values)),
            "IC50_nM_max":float(values.max()),"pIC50_min":float(labels.min()),"pIC50_max":float(labels.max()),
            "pIC50_span":float(np.ptp(labels)),"pIC50_IQR":float(np.subtract(*np.percentile(labels,[75,25]))),
            "pIC50_sample_SD":float(np.std(labels,ddof=1))}


def inverse_simpson(groups):
    _,counts=np.unique(groups,return_counts=True)
    p=counts/counts.sum()
    return float(1/np.sum(p*p))


def prospective_splits(frame,folds,seed):
    scaffold=frame.scaffold.to_numpy()
    connectivity=frame.connectivity.to_numpy()
    primary=list(GroupKFold(n_splits=folds).split(frame,groups=scaffold))
    unique=np.unique(connectivity)
    secondary=[]
    for train_groups,test_groups in KFold(n_splits=folds,shuffle=True,random_state=seed).split(unique):
        train=np.flatnonzero(np.isin(connectivity,unique[train_groups]))
        test=np.flatnonzero(np.isin(connectivity,unique[test_groups]))
        secondary.append((train,test))
    for scheme,splits in [("scaffold",primary),("random_connectivity_grouped",secondary)]:
        assert sorted(np.concatenate([test for _,test in splits]).tolist())==list(range(len(frame)))
        for train,test in splits:
            if set(connectivity[train])&set(connectivity[test]):
                raise ValueError("연결 구조·입체 변형이 학습/평가 양쪽에 있습니다.")
            if scheme=="scaffold" and set(scaffold[train])&set(scaffold[test]):
                raise ValueError("주 진단의 골격 중복")
    return {"scaffold":primary,"random_connectivity_grouped":secondary}


def main():
    config_path=ROOT/"configs/scope_diagnostics.json"
    config=json.loads(config_path.read_text())
    if config["train_models"] or config["assign_training_approval"]:
        raise ValueError("승인·학습을 수행하는 실행기가 아닙니다.")
    out=ROOT/"data/interim/cohort_scope_diagnostics_20261020"
    if out.exists():
        raise FileExistsError(f"기존 진단 보호: {out}")
    paths={key:ROOT/value for key,value in config["inputs"].items()}
    pilot=pd.read_csv(paths["pilot22"],dtype=str,keep_default_na=False)
    furan=pd.read_csv(paths["furan45"],dtype=str,keep_default_na=False)
    review=pd.read_csv(paths["patent50"],dtype=str,keep_default_na=False)
    patent=review.loc[review.assay_chembl_id.eq("CHEMBL5737421")&review.standard_relation.eq("=")]
    audit_path=ROOT/"data/interim/audit_chembl_full_20261020/activity_audit.csv"
    audit=pd.read_csv(audit_path,dtype=str,keep_default_na=False).set_index("activity_id")
    datasets={
        "pilot22":pd.DataFrame({"id":pilot.activity_id,"smiles":pilot.canonical_isomeric_smiles,"nM":pd.to_numeric(pilot.standard_value)}),
        "furan45":pd.DataFrame({"id":furan.activity_id,"smiles":furan.source_smiles,"nM":pd.to_numeric(furan.source_IC50_nM)}),
        "patent50":pd.DataFrame({"id":patent.activity_id.to_numpy(),"smiles":[audit.loc[i,"canonical_smiles"] for i in patent.activity_id],
                                 "nM":pd.to_numeric(patent.standard_value_nM).to_numpy()}),
    }
    metrics,fold_rows,neighbors,assignments=[],[],[],[]
    options=config["fingerprint"]
    generator=rdFingerprintGenerator.GetMorganGenerator(radius=options["radius"],fpSize=options["size"],includeChirality=options["include_chirality"])
    for key,frame in datasets.items():
        frame=frame.sort_values("id").reset_index(drop=True)
        inspected=[inspect_structure(smiles) for smiles in frame.smiles]
        if any(value is None for value in inspected):
            raise ValueError("구조 파싱·단일 성분 범위 실패")
        frame["canonical"]=[value[0] for value in inspected]
        frame["connectivity"]=[value[1] for value in inspected]
        frame["scaffold"]=[value[2] for value in inspected]
        structural=frame.drop_duplicates("connectivity")
        counts=structural.scaffold.value_counts()
        metrics.append({"cohort":key,"measurement_rows":len(frame),"isomeric_structures":frame.canonical.nunique(),
                        "connectivity_groups":len(structural),"scaffolds":len(counts),
                        "largest_scaffold_rows":int(frame.scaffold.value_counts().max()),
                        "largest_scaffold_connectivity_groups":int(counts.max()),
                        "largest_scaffold_fraction_by_connectivity":float(counts.max()/len(structural)),
                        "inverse_simpson_scaffolds_by_connectivity":inverse_simpson(structural.scaffold),
                        "scaffolds_with_one_connectivity_group":int(counts.eq(1).sum()),
                        "independent_documents":1,"independent_assays":1, "training_approved":False,
                        **concentration_summary(frame.nM)})
        fps=[generator.GetFingerprint(Chem.MolFromSmiles(smiles)) for smiles in frame.smiles]
        splits=prospective_splits(frame,config["diagnostic_folds"],config["random_group_split_seed"])
        for scheme,parts in splits.items():
            for fold,(train,test) in enumerate(parts,1):
                train_scaffolds=set(frame.iloc[train].scaffold)
                test_scaffolds=set(frame.iloc[test].scaffold)
                sims=[]
                for index in test:
                    similarities=DataStructs.BulkTanimotoSimilarity(fps[index],[fps[i] for i in train])
                    nearest=int(train[int(np.argmax(similarities))])
                    sims.append(max(similarities))
                    neighbors.append({"cohort":key,"scheme":scheme,"fold":fold,"evaluation_id":frame.iloc[index].id,
                                      "nearest_training_id":frame.iloc[nearest].id,"nearest_training_Tanimoto":max(similarities),
                                      "shares_scaffold_with_training":frame.iloc[index].scaffold in train_scaffolds,
                                      "prospective_only":True})
                for role,indexes in [("train",train),("evaluation",test)]:
                    assignments.extend({"cohort":key,"scheme":scheme,"fold":fold,"role":role,"activity_id":frame.iloc[i].id,
                                        "connectivity":frame.iloc[i].connectivity,"scaffold":frame.iloc[i].scaffold} for i in indexes)
                fold_rows.append({"cohort":key,"scheme":scheme,"fold":fold,"train_rows":len(train),"evaluation_rows":len(test),
                                  "train_connectivity_groups":frame.iloc[train].connectivity.nunique(),
                                  "evaluation_connectivity_groups":frame.iloc[test].connectivity.nunique(),
                                  "overlapping_scaffolds":len(train_scaffolds&test_scaffolds),
                                  "evaluation_rows_with_training_scaffold":sum(frame.iloc[test].scaffold.isin(train_scaffolds)),
                                  "overlapping_connectivity_groups":0,"nearest_training_Tanimoto_min":min(sims),
                                  "nearest_training_Tanimoto_median":float(np.median(sims)),
                                  "nearest_training_Tanimoto_max":max(sims),"prospective_only":True})
    out.mkdir(parents=True)
    for name,table in {"cohort_metrics.csv":metrics,"prospective_fold_metrics.csv":fold_rows,
                       "prospective_neighbors.csv":neighbors,"prospective_assignments.csv":assignments}.items():
        pd.DataFrame(table).to_csv(out/name,index=False)
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    inputs=[*paths.values(),audit_path,config_path,Path(__file__).resolve(),ROOT/"scripts/prioritize_main_cohort.py"]
    manifest={"created_at_utc":datetime.now(timezone.utc).isoformat(),"purpose":config["purpose"],
              "model_training_executed":False,"training_approved":False,"final_test_split":False,
              "runtime":{package:version(package) for package in ["numpy","pandas","rdkit","scikit-learn"]},
              "inputs_sha256":{str(p.relative_to(ROOT)):digest(p) for p in inputs},
              "outputs_sha256":{p.name:digest(p) for p in out.iterdir()}}
    (out/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    print(pd.DataFrame(metrics).to_string(index=False))
    print(pd.DataFrame(fold_rows).to_string(index=False))


if __name__=="__main__":
    main()
