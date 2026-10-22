"""Chemprop `sampl` 벤치마크의 축소 재현(선택 C)을 실행한다.

저자 원본은 chemprop_benchmark commit 247f3ee의 scripts/sampl.sh이며
hyperopt 30회(각 50 epoch) + 앙상블 5개(50 epoch) + production 앙상블 5개(40 epoch)를 돈다.
이 기기(Apple Silicon, CUDA 없음)에서 그 예산은 현실적이지 않아 configs/benchmark_repro.json에
고정한 축소 설정으로 실행한다. **원 논문과 동일 조건 재현이 아니다.**

실행 전에 설정을 고정하고, 실행 후 저자 보고값과의 차이를 표로 남긴다.
저자 스크립트의 명령·인자 구조와 평가 컬럼은 그대로 따른다.

사용:
  .venv-repro/bin/python scripts/run_sampl_repro.py \
      --config configs/benchmark_repro.json \
      --data-dir data/raw/benchmark_data_20261021 \
      --output-dir artifacts/sampl_repro_20261021 \
      --report-dir reports/sampl_repro_20261021
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 저자 보고값 (SI Table S9). 비교 대상일 뿐 목표치가 아니다.
AUTHOR_REPORTED = {
    "SAMPL6": 0.27,
    "SAMPL7": 0.49,
    "SAMPL9": 1.11,
    "random_test_set": 0.53,
}

# 평가 파일별 컬럼 정의는 저자 sampl.sh를 그대로 따른다.
SAMPL_SPEC = {
    "SAMPL6": {"file": "sampl6_experimental.csv", "smiles_col": "Isomeric SMILES", "truth_col": "logP mean"},
    "SAMPL7": {"file": "sampl7_experimental.csv", "smiles_col": "Isomeric SMILES", "truth_col": "logP mean"},
    "SAMPL9": {"file": "sampl9_experimental.csv", "smiles_col": "smiles", "truth_col": "new_logPexp_reviewed"},
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(cmd: list[str], log: Path) -> float:
    log.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    print("  $ " + " ".join(cmd[:6]) + " ...", flush=True)
    with log.open("w", encoding="utf-8") as f:
        proc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, text=True)
    elapsed = time.time() - start
    if proc.returncode != 0:
        raise SystemExit(f"실패(returncode={proc.returncode}): {log}")
    print(f"    완료 {elapsed/60:.1f}분", flush=True)
    return elapsed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--report-dir", type=Path, required=True)
    args = ap.parse_args()

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    red = cfg["reduced_settings"]

    out, rep = args.output_dir, args.report_dir
    for d in (out, rep):
        if d.exists() and any(d.iterdir()):
            raise SystemExit(f"거부: 출력 폴더가 비어 있지 않다. 새 경로를 지정하라: {d}")
        d.mkdir(parents=True, exist_ok=True)

    data = args.data_dir
    train_p, val_p, test_p = data / "train.csv", data / "val.csv", data / "test.csv"
    full_p = data / "logP_without_overlap.csv"
    for p in (train_p, val_p, test_p, full_p):
        if not p.exists():
            raise SystemExit(f"입력 없음: {p}")

    bin_dir = Path(sys.executable).parent
    chemprop_train = str(bin_dir / "chemprop_train")
    chemprop_predict = str(bin_dir / "chemprop_predict")

    timings: dict[str, float] = {}

    # 1) 저자 분할에서의 학습·평가 (hyperopt 없음: 축소 항목)
    split_dir = out / "split_model"
    timings["split_training_sec"] = run([
        chemprop_train,
        "--dataset_type", "regression",
        "--data_path", str(train_p),
        "--separate_val_path", str(val_p),
        "--separate_test_path", str(test_p),
        "--epochs", str(red["epochs_split"]),
        "--aggregation", "norm",
        "--ensemble_size", str(red["ensemble_size"]),
        "--save_dir", str(split_dir),
        "--extra_metrics", "mae",
        "--seed", str(red["seed"]),
        "--quiet",
    ], rep / "log_split_training.txt")

    # 2) production 모델 (전체 자료, 저자와 동일하게 val/test도 같은 파일 지정)
    prod_dir = out / "production_model"
    timings["production_training_sec"] = run([
        chemprop_train,
        "--dataset_type", "regression",
        "--data_path", str(full_p),
        "--separate_val_path", str(full_p),
        "--separate_test_path", str(full_p),
        "--epochs", str(red["epochs_production"]),
        "--aggregation", "norm",
        "--ensemble_size", str(red["ensemble_size"]),
        "--save_dir", str(prod_dir),
        "--seed", str(red["seed"]),
        "--quiet",
    ], rep / "log_production_training.txt")

    # 3) SAMPL6/7/9 예측과 RMSE
    import pandas as pd
    from sklearn.metrics import mean_squared_error

    sampl_results = {}
    for name, spec in SAMPL_SPEC.items():
        truth_path = data / spec["file"]
        pred_path = out / f"pred_{name}.csv"
        timings[f"predict_{name}_sec"] = run([
            chemprop_predict,
            "--test_path", str(truth_path),
            "--preds_path", str(pred_path),
            "--checkpoint_dir", str(prod_dir),
            "--smiles_column", spec["smiles_col"],
        ], rep / f"log_predict_{name}.txt")

        pred = pd.read_csv(pred_path)
        truth = pd.read_csv(truth_path)
        y_pred = pred["logP"].astype(float)
        y_true = truth[spec["truth_col"]].astype(float)
        n = min(len(y_pred), len(y_true))
        rmse = float(mean_squared_error(y_true[:n], y_pred[:n], squared=False))
        sampl_results[name] = {
            "n": int(n),
            "rmse_ours": round(rmse, 4),
            "rmse_author_reported": AUTHOR_REPORTED[name],
            "difference": round(rmse - AUTHOR_REPORTED[name], 4),
        }
        print(f"  {name}: n={n} RMSE={rmse:.4f} (저자 {AUTHOR_REPORTED[name]})", flush=True)

    # 4) 저자 분할 테스트셋 점수 읽기
    split_scores_path = split_dir / "test_scores.csv"
    split_scores = {}
    if split_scores_path.exists():
        df = pd.read_csv(split_scores_path)
        for col in df.columns:
            if col.lower().startswith("mean"):
                split_scores[col] = float(df[col].iloc[0])

    result = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "milestone": "M3",
        "status": "reduced_budget_reproduction_not_equal_condition",
        "config_path": str(args.config),
        "config_sha256": sha256(args.config),
        "reduced_settings": red,
        "author_original_settings": cfg["author_original_settings"],
        "deviations": cfg["deviations"],
        "environment": {
            "python": platform.python_version(),
            "platform": f"{platform.system()} {platform.machine()}",
            "packages": cfg["environment_actual"],
        },
        "input_sha256": {
            "train.csv": sha256(train_p),
            "val.csv": sha256(val_p),
            "test.csv": sha256(test_p),
            "logP_without_overlap.csv": sha256(full_p),
        },
        "timings_sec": {k: round(v, 1) for k, v in timings.items()},
        "author_split_test_scores": split_scores,
        "sampl_results": sampl_results,
        "author_reported": AUTHOR_REPORTED,
        "claim_limits": [
            "하이퍼파라미터 탐색을 생략했고 앙상블 크기를 줄였으므로 원 논문과 동일 조건 비교가 아니다",
            "환경(python/torch/numpy/sklearn)이 저자 환경과 다르다",
            "차이가 작더라도 '재현 성공'이 아니라 '축소 조건에서의 결과'로 서술한다",
        ],
    }
    (rep / "sampl_repro_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n결과 저장:", rep / "sampl_repro_result.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
