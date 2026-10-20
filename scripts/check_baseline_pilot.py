"""저장 모델·OOF 예측·라벨·분할·입출력 무결성을 재검증한다."""

from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import sys

import joblib
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    report = ROOT / "reports/baseline_pilot_20261020_v2"
    manifest = json.loads((report / "manifest.json").read_text())
    for field in ("inputs_sha256", "model_files", "report_files"):
        for name, expected in manifest[field].items():
            assert digest(ROOT / name) == expected, name
    assert manifest["purpose"] == "educational_exploratory"
    assert manifest["benchmark_training_cohort_approved"] is False
    source = pd.read_csv(ROOT / "data/interim/cohort_review_20261020/context_pilot.csv", dtype=str, keep_default_na=False)
    source = source.sort_values("activity_id").reset_index(drop=True)
    assert len(source) == 22 and set(source.training_ready) == {"False"}
    features = np.load(ROOT / "artifacts/baseline_pilot_20261020_v2/features.npz")
    y = 9 - np.log10(pd.to_numeric(source.standard_value).to_numpy())
    np.testing.assert_allclose(features["y"], y, rtol=0, atol=1e-12)
    index = {identifier: i for i, identifier in enumerate(source.activity_id)}
    labels = dict(zip(source.activity_id, y))
    pred = pd.read_csv(report / "predictions.csv", dtype={"activity_id": str})
    split = pd.read_csv(report / "split_assignments.csv", dtype={"activity_id": str})
    assert len(pred) == 264 and not pred.duplicated(["scheme", "seed", "model", "activity_id"]).any()
    for (scheme, seed, name), part in pred.groupby(["scheme", "seed", "model"]):
        assert set(part.activity_id) == set(source.activity_id)
    reloaded = 0
    for (scheme, fold, seed, name), part in pred.groupby(["scheme", "fold", "seed", "model"]):
        assignments = split.loc[(split.scheme == scheme) & (split.fold == fold)]
        train = assignments.loc[assignments.role == "train"]
        evaluation = assignments.loc[assignments.role == "evaluation"]
        assert not set(train.activity_id) & set(evaluation.activity_id)
        assert set(part.activity_id) == set(evaluation.activity_id)
        if scheme == "scaffold":
            assert not set(train.scaffold) & set(evaluation.scaffold)
        actual = np.array([labels[i] for i in part.activity_id])
        np.testing.assert_allclose(part.observed_pIC50, actual, atol=1e-12, rtol=0)
        model = joblib.load(ROOT / "artifacts/baseline_pilot_20261020_v2/models" /
                            f"{scheme}_fold{fold}_{name}_seed{seed}.joblib")
        actual_predictions = model.predict(features["X"][[index[i] for i in part.activity_id]])
        np.testing.assert_allclose(actual_predictions, part.predicted_pIC50, atol=1e-12, rtol=0)
        if name == "Dummy":
            train_mean = np.mean([labels[i] for i in train.activity_id])
            np.testing.assert_allclose(actual_predictions, train_mean, atol=1e-12, rtol=0)
        reloaded += 1
    scores = pd.read_csv(report / "metrics.csv")
    for row in scores.to_dict("records"):
        part = pred.loc[(pred.scheme == row["scheme"]) & (pred.seed == row["seed"]) & (pred.model == row["model"])]
        errors = part.predicted_pIC50.to_numpy() - part.observed_pIC50.to_numpy()
        assert abs(np.abs(errors).mean() - row["MAE"]) < 1e-12
        assert abs(np.sqrt((errors**2).mean()) - row["RMSE"]) < 1e-12
    study_dir = ROOT / "data/interim/apsel_review_20261020"
    study = json.loads((study_dir / "manifest.json").read_text())
    for name, expected in study["inputs_sha256"].items():
        assert digest(ROOT / name) == expected
    for name, expected in study["outputs_sha256"].items():
        assert digest(study_dir / name) == expected
    study_rows = pd.read_csv(study_dir / "measurement_review.csv", dtype=str, keep_default_na=False)
    assert len(study_rows) == 209 and set(study_rows.training_approved) == {"False"}
    assert not set(study_rows.activity_id) & set(source.activity_id)
    for package, installed in manifest["runtime"]["versions"].items():
        assert version(package) == installed
    result = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "passed": True,
              "pilot_measurements": 22, "saved_models_reloaded": reloaded, "OOF_prediction_rows": len(pred),
              "all_samples_evaluated_once_per_scheme_seed_model": True, "primary_scaffold_overlap": 0,
              "dummy_uses_training_fold_only": True, "metrics_independently_recomputed": True,
              "apsel_rows_reviewed": 209, "apsel_training_approved": 0, "apsel_in_pilot": 0,
              "original_pilot_training_ready_unchanged": True,
              "python": sys.version, "platform": platform.platform(),
              "freeze_sha256": digest(ROOT / "requirements/ml-py312-macos-arm64.freeze.txt"),
              "baseline_manifest_sha256": digest(report / "manifest.json")}
    (ROOT / "reports/baseline_pilot_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
