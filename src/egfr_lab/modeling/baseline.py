"""원문 확인 파일럿의 교육·탐색용 Dummy/Morgan-RF 비교. 배포 모델 아님."""

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys
import time

import joblib
import numpy as np
import pandas as pd
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator
from rdkit.Chem.Scaffolds import MurckoScaffold
from scipy.stats import spearmanr
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GroupKFold, KFold


ROOT = Path(__file__).resolve().parents[3]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_pilot(frame, policy):
    """미승인 자료의 일반 학습을 허용하지 않고 고정 파일럿 범위를 검사한다."""
    if policy["purpose"] != "educational_exploratory" or policy["hyperparameter_search"]:
        raise ValueError("이 실행기는 고정 설정의 교육·탐색 실험 전용입니다.")
    if len(frame) != policy["expected_rows"] or set(frame.assay_chembl_id) != {policy["expected_assay"]}:
        raise ValueError("단일 실험 파일럿 범위가 다릅니다.")
    expected = {"target_chembl_id": "CHEMBL203", "standard_type": "IC50", "standard_relation": "=",
                "standard_units": "nM", "variant_screen": "WT", "matched": "True", "screen_reasons": ""}
    for key, value in expected.items():
        if set(frame[key]) != {value}:
            raise ValueError(f"원문 확인 파일럿 조건 불일치: {key}")
    if frame.activity_id.duplicated().any() or frame.structure_group.duplicated().any():
        raise ValueError("중복 관측·구조를 독립 분자로 평가할 수 없습니다.")
    y = 9 - np.log10(pd.to_numeric(frame.standard_value).to_numpy(dtype=float))
    if not np.isfinite(y).all() or not np.allclose(y, pd.to_numeric(frame.pIC50_computed), atol=1e-10, rtol=0):
        raise ValueError("라벨 단위·pIC50 재계산 불일치")
    if not np.allclose(pd.to_numeric(frame.source_nM), pd.to_numeric(frame.standard_value), atol=0, rtol=0):
        raise ValueError("원문 수치와 학습 후보 수치가 다릅니다.")
    return y


def featurize(frame, options):
    generator = rdFingerprintGenerator.GetMorganGenerator(radius=options["radius"], fpSize=options["size"],
                                                          includeChirality=options["include_chirality"])
    X = np.zeros((len(frame), options["size"]), dtype=np.uint8)
    canonical, scaffolds = [], []
    for i, text in enumerate(frame.canonical_isomeric_smiles):
        molecule = Chem.MolFromSmiles(text)
        if molecule is None or len(Chem.GetMolFrags(molecule)) != 1:
            raise ValueError("파싱 실패 또는 다성분 분자")
        canonical.append(Chem.MolToSmiles(molecule, isomericSmiles=True))
        scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=molecule, includeChirality=False)
        # 고리 없는 분자를 한 빈 문자열 그룹으로 합치지 않는다.
        scaffolds.append(scaffold or "acyclic:" + canonical[-1])
        DataStructs.ConvertToNumpyArray(generator.GetFingerprint(molecule), X[i])
    if len(set(canonical)) != len(frame):
        raise ValueError("동일 정규 구조가 서로 다른 ID에 중복되어 있습니다.")
    if list(frame.scaffold_smiles) != scaffolds:
        raise ValueError("기존 감사와 scaffold 계산이 다릅니다.")
    return X, np.array(scaffolds, dtype=object)


def make_splits(X, groups, folds, seed):
    if len(np.unique(groups)) < folds:
        raise ValueError("scaffold 수가 교차검증 fold보다 적습니다.")
    primary = list(GroupKFold(n_splits=folds).split(X, groups=groups))
    secondary = list(KFold(n_splits=folds, shuffle=True, random_state=seed).split(X))
    for train, test in primary:
        if set(groups[train]) & set(groups[test]):
            raise ValueError("학습·평가 scaffold 누출")
    for splits in (primary, secondary):
        indexes = np.concatenate([test for _, test in splits])
        if sorted(indexes.tolist()) != list(range(len(X))):
            raise ValueError("평가 표본의 누락·중복")
    return {"scaffold": primary, "random_molecule": secondary}


def metrics(y, prediction):
    error = np.asarray(prediction) - np.asarray(y)
    rho = None if len(np.unique(prediction)) < 2 or len(np.unique(y)) < 2 else float(spearmanr(y, prediction).statistic)
    return {"MAE": float(np.mean(np.abs(error))), "RMSE": float(np.sqrt(np.mean(error**2))), "Spearman": rho}


def paired_cluster_ci(y, dummy, rf, groups, resamples, seed):
    """고정 OOF 예측의 RF−Dummy MAE 차이를 scaffold 단위로 재표집."""
    y, dummy, rf, groups = map(np.asarray, (y, dummy, rf, groups))
    if not (y.shape == dummy.shape == rf.shape == groups.shape) or len(y) == 0:
        raise ValueError("paired 비교는 동일 순서·표본이 필요합니다.")
    loss_delta = np.abs(rf - y) - np.abs(dummy - y)
    if not np.isfinite(loss_delta).all():
        raise ValueError("비유한 오차")
    unique = np.unique(groups)
    if len(unique) < 2:
        raise ValueError("재표집 가능한 독립 그룹이 부족합니다.")
    indexes = [np.flatnonzero(groups == group) for group in unique]
    rng = np.random.default_rng(seed)
    draws = [float(loss_delta[np.concatenate([indexes[i] for i in rng.integers(0, len(unique), len(unique))])].mean())
             for _ in range(resamples)]
    low, high = np.quantile(draws, [0.025, 0.975])
    return {"RF_minus_Dummy_MAE": float(loss_delta.mean()), "conditional_CI95_low": float(low),
            "conditional_CI95_high": float(high), "scaffold_clusters": len(unique)}


def run(config_path, run_dir, report_dir):
    if run_dir.exists() or report_dir.exists():
        raise FileExistsError("기존 실험 보호: 새 --run-dir와 --report-dir를 지정하세요.")
    policy = json.loads(config_path.read_text())
    source = ROOT / policy["cohort_path"]
    if sha(source) != policy["cohort_sha256"]:
        raise ValueError("고정 파일럿 해시가 다릅니다. 다른 자료를 임의로 대입하지 않습니다.")
    frame = pd.read_csv(source, dtype=str, keep_default_na=False).sort_values("activity_id").reset_index(drop=True)
    holds_path = ROOT / policy["source_holds_path"]
    holds = json.loads(holds_path.read_text())["holds"]
    if set(frame.assay_chembl_id) & {h["assay_chembl_id"] for h in holds}:
        raise ValueError("원문 검토 보류 assay가 포함돼 있습니다.")
    y = validate_pilot(frame, policy)
    X, groups = featurize(frame, policy["fingerprint"])
    splits = make_splits(X, groups, policy["cv"]["folds"], policy["cv"]["split_seed"])
    run_dir.mkdir(parents=True)
    report_dir.mkdir(parents=True)
    model_dir = run_dir / "models"
    model_dir.mkdir()
    (run_dir / "policy_snapshot.json").write_bytes(config_path.read_bytes())
    np.savez_compressed(run_dir / "features.npz", X=X, y=y)
    started = time.monotonic()
    predictions, fold_rows, split_rows, score_rows, comparisons = [], [], [], [], []
    for scheme, partitions in splits.items():
        for fold, (train, test) in enumerate(partitions, 1):
            overlap = len(set(groups[train]) & set(groups[test]))
            for role, indices in (("train", train), ("evaluation", test)):
                split_rows.extend({"scheme": scheme, "fold": fold, "role": role,
                                   "activity_id": frame.iloc[i].activity_id, "scaffold": groups[i]} for i in indices)
            for seed in policy["model_seeds"]:
                models = {"Dummy": DummyRegressor(strategy="mean"),
                          "RandomForest": RandomForestRegressor(random_state=seed, **policy["random_forest"])}
                for name, model in models.items():
                    model.fit(X[train], y[train])
                    prediction = model.predict(X[test])
                    if name == "Dummy" and not np.allclose(prediction, y[train].mean()):
                        raise ValueError("Dummy가 학습 fold 평균을 사용하지 않았습니다.")
                    model_path = model_dir / f"{scheme}_fold{fold}_{name}_seed{seed}.joblib"
                    joblib.dump(model, model_path)
                    if not np.allclose(joblib.load(model_path).predict(X[test]), prediction, atol=0, rtol=0):
                        raise ValueError("저장·재로딩 예측 불일치")
                    fold_rows.append({"scheme": scheme, "fold": fold, "seed": seed, "model": name,
                                      "train_rows": len(train), "evaluation_rows": len(test),
                                      "train_mean_pIC50": float(y[train].mean()), "overlapping_scaffolds": overlap,
                                      **metrics(y[test], prediction)})
                    predictions.extend({"scheme": scheme, "fold": fold, "seed": seed, "model": name,
                                        "activity_id": frame.iloc[i].activity_id,
                                        "compound_key": frame.iloc[i].source_compound_key,
                                        "scaffold": groups[i], "observed_pIC50": float(y[i]),
                                        "predicted_pIC50": float(prediction[j]),
                                        "absolute_error": float(abs(y[i] - prediction[j]))}
                                       for j, i in enumerate(test))
                print(f"{scheme}: fold {fold}, seed {seed}, 학습 {len(train)}·평가 {len(test)}", flush=True)
    pred = pd.DataFrame(predictions)
    for scheme in splits:
        for seed in policy["model_seeds"]:
            subset = pred.loc[(pred.scheme == scheme) & (pred.seed == seed)]
            pivot = subset.pivot(index="activity_id", columns="model", values="predicted_pIC50").loc[frame.activity_id]
            for name in ("Dummy", "RandomForest"):
                score_rows.append({"scheme": scheme, "seed": seed, "model": name, "n": len(y), **metrics(y, pivot[name])})
            comparisons.append({"scheme": scheme, "seed": seed, **paired_cluster_ci(y, pivot.Dummy.to_numpy(),
                pivot.RandomForest.to_numpy(), groups, policy["bootstrap"]["resamples"], policy["bootstrap"]["seed"])})
    outputs = {"predictions.csv": pred, "fold_metrics.csv": pd.DataFrame(fold_rows),
               "split_assignments.csv": pd.DataFrame(split_rows), "metrics.csv": pd.DataFrame(score_rows),
               "paired_comparison.csv": pd.DataFrame(comparisons)}
    for name, table in outputs.items():
        table.to_csv(report_dir / name, index=False)
    plot_predictions(pred, report_dir)
    versions = {p: version(p) for p in ("numpy", "pandas", "scipy", "scikit-learn", "rdkit", "joblib", "matplotlib")}
    inputs = [source, config_path, holds_path, Path(__file__).resolve()]
    manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "state": "complete",
                "purpose": policy["purpose"], "benchmark_training_cohort_approved": False,
                "scope": "22건 단일 assay 탐색·교육용; 209건 포함 안 함",
                "rows": len(frame), "scaffold_groups": len(np.unique(groups)), "label_span": float(np.ptp(y)),
                "schemes": list(splits), "seeds": policy["model_seeds"], "hyperparameter_search": False,
                "independent_final_test": False, "elapsed_seconds": time.monotonic() - started,
                "runtime": {"python": sys.version, "executable": sys.executable, "versions": versions},
                "inputs_sha256": {str(p.relative_to(ROOT)): sha(p) for p in inputs},
                "model_files": {str(p.relative_to(ROOT)): sha(p) for p in model_dir.glob("*.joblib")},
                "report_files": {str(p.relative_to(ROOT)): sha(p) for p in report_dir.iterdir()},
                "uncertainty_scope": "OOF 예측을 고정한 탐색적 CI; 학습·분할·미래 실험 전체의 불확실성이 아님"}
    (report_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(pd.DataFrame(score_rows).to_string(index=False))


def plot_predictions(predictions, out):
    os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "tmp/matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(9, 4), constrained_layout=True)
    for ax, scheme in zip(axes, ("scaffold", "random_molecule")):
        for name, marker in (("Dummy", "x"), ("RandomForest", "o")):
            part = predictions.loc[(predictions.scheme == scheme) & (predictions.seed == 42) & (predictions.model == name)]
            ax.scatter(part.observed_pIC50, part.predicted_pIC50, label=name, marker=marker, s=35, alpha=.8)
        ax.plot([6.7, 8.6], [6.7, 8.6], color="gray", linewidth=1)
        ax.set(xlabel="Observed pIC50", ylabel="Out-of-fold prediction", title=f"{scheme}: pilot n=22", xlim=(6.7, 8.6), ylim=(6.7, 8.6))
        ax.legend(fontsize=8)
    fig.savefig(out / "predictions.png", dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/baseline_pilot.json")
    parser.add_argument("--run-dir", default="artifacts/baseline_pilot_20261020_v2")
    parser.add_argument("--report-dir", default="reports/baseline_pilot_20261020_v2")
    args = parser.parse_args()
    run(ROOT / args.config, ROOT / args.run_dir, ROOT / args.report_dir)
