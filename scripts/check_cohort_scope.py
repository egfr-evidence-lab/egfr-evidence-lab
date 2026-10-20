"""적용 범위 진단·구조 경보·원문 확보 상태를 독립 재검증한다."""

from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from rdkit import Chem,DataStructs
from rdkit.Chem import rdFingerprintGenerator


ROOT=Path(__file__).resolve().parents[1]


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(directory):
    manifest=json.loads((directory/"manifest.json").read_text())
    for name,value in manifest["inputs_sha256"].items():assert digest(ROOT/name)==value,name
    for name,value in manifest["outputs_sha256"].items():assert digest(directory/name)==value,name
    return manifest


def main():
    files=0
    for path in [ROOT/"data/raw/scope_evidence_20261020_v2",ROOT/"data/raw/scope_evidence_20261020_supplement"]:
        for record in json.loads((path/"manifest.json").read_text())["sources"]:
            if record.get("path"):
                file=ROOT/record["path"]
                assert digest(file)==record["sha256"]
                if file.suffix==".png" and record.get("content_candidate"):
                    assert file.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
                files+=1
    datacite=json.loads((ROOT/"data/raw/scope_evidence_20261020_supplement/ref28_datacite.json").read_text())["data"]["attributes"]
    assert datacite["types"]["resourceTypeGeneral"]=="Dataset"
    assert datacite["publisher"]=="BindingDB"
    assert any("chembl" in item["relatedIdentifier"] for item in datacite["relatedIdentifiers"])
    massdir=ROOT/"data/interim/patent_structure_review_20261020_v2"
    mass=verify(massdir)
    m=pd.read_csv(massdir/"structure_mass_review.csv",keep_default_na=False)
    assert len(m)==64 and m.activity_id.nunique()==64 and not m.training_ready.any()
    assert m.source_keys_with_MS.gt(0).sum()==35
    assert m.large_mass_discrepancy_keys.ne("[]").sum()==13
    source_masses=json.loads((massdir/"source_masses.json").read_text())
    assert source_masses["G-33"]["reported_M_plus_H"]==499.2
    assert source_masses["G-41"]["reported_M_plus_H"]==513.2
    assert all(item["source_location"]=="synthetic_table_explicit_G_key" for item in source_masses.values())
    directory=ROOT/"data/interim/cohort_scope_diagnostics_20261020"
    manifest=verify(directory)
    assert not manifest["model_training_executed"] and not manifest["training_approved"] and not manifest["final_test_split"]
    metrics=pd.read_csv(directory/"cohort_metrics.csv")
    assert dict(zip(metrics.cohort,metrics.measurement_rows))=={'pilot22':22,'furan45':45,'patent50':50}
    assignments=pd.read_csv(directory/"prospective_assignments.csv",dtype={'activity_id':str})
    nearest=pd.read_csv(directory/"prospective_neighbors.csv",dtype={'evaluation_id':str,'nearest_training_id':str})
    folds=pd.read_csv(directory/"prospective_fold_metrics.csv")
    assert len(folds)==18 and len(nearest)==234
    for (cohort,scheme,fold),group in assignments.groupby(['cohort','scheme','fold']):
        train=group.loc[group.role.eq('train')]
        test=group.loc[group.role.eq('evaluation')]
        assert not set(train.connectivity)&set(test.connectivity)
        if scheme=='scaffold':assert not set(train.scaffold)&set(test.scaffold)
        nn=nearest.loc[nearest.cohort.eq(cohort)&nearest.scheme.eq(scheme)&nearest.fold.eq(fold)]
        assert set(nn.evaluation_id)==set(test.activity_id)
        assert set(nn.nearest_training_id)<=set(train.activity_id)
    for key,g in assignments.query("role=='evaluation'").groupby(['cohort','scheme']):
        assert g.activity_id.nunique()==len(g)
    assert nearest.nearest_training_Tanimoto.between(0,1).all()
    furan=pd.read_csv(ROOT/"data/interim/furan_candidate_20261020/IC50_candidates_not_training_ready.csv",dtype=str,keep_default_na=False)
    smiles=dict(zip(furan.activity_id,furan.source_smiles))
    generator=rdFingerprintGenerator.GetMorganGenerator(radius=2,fpSize=2048,includeChirality=True)
    fps={key:generator.GetFingerprint(Chem.MolFromSmiles(value)) for key,value in smiles.items()}
    for item in nearest.loc[nearest.cohort.eq('furan45')].itertuples():
        value=DataStructs.TanimotoSimilarity(fps[item.evaluation_id],fps[item.nearest_training_id])
        assert abs(value-item.nearest_training_Tanimoto)<1e-12
        group=assignments.loc[assignments.cohort.eq('furan45')&assignments.scheme.eq(item.scheme)&assignments.fold.eq(item.fold)&assignments.role.eq('train')]
        assert abs(max(DataStructs.TanimotoSimilarity(fps[item.evaluation_id],fps[i]) for i in group.activity_id)-value)<1e-12
    counts=furan.drop_duplicates('connectivity_group').scaffold_smiles.value_counts().to_numpy()
    effective=1/np.sum((counts/counts.sum())**2)
    assert abs(effective-float(metrics.loc[metrics.cohort.eq('furan45'),'inverse_simpson_scaffolds_by_connectivity'].iloc[0]))<1e-12
    project=json.loads((ROOT/'configs/project.json').read_text())
    scope_review=json.loads((ROOT/project['curation']['latest_scope_review_path']).read_text())
    assert scope_review['new_training_approved']==0 and not scope_review['new_model_training_executed']
    assert not scope_review['furan45']['training_ready'] and not scope_review['patent64']['training_ready']
    assert project['target']['training_cohort']=='pending_manual_assay_review_after_automatic_audit'
    result={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'passed':True,'new_source_response_files_hashed':files,
            'prospective_cohorts':3,'prospective_folds':18,'prospective_neighbors':234,
            'furan_nearest_training_similarities_independently_recomputed':90,
            'connectivity_overlap_all_folds':0,'primary_scaffold_overlap':0,
            'ref28_OA_link_is_derived_dataset_not_article':True,
            'patent_source_MS_covered_observations':35,'patent_MS_discrepancy_observations':13,
            'new_training_approved':0,'new_models_trained':0,
            'diagnostics_manifest_sha256':digest(directory/'manifest.json'),'patent_structure_manifest_sha256':digest(massdir/'manifest.json')}
    (ROOT/'reports/cohort_scope_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
