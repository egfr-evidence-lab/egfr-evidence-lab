"""M2 2단계 — D-MPNN 예측을 M1 과 같은 지표로 채점하고 Dummy·RF 와 비교한다.

M1(.venv-ml)과 같은 수치를 보장하려고 지표와 부트스트랩을 **다시 구현하지 않고**
src/egfr_lab/modeling/baseline.py 의 metrics() 와 paired_cluster_ci() 를 그대로 import 한다.
학습은 Chemprop 이 요구하는 구버전 스택(.venv-repro)에서 했고, 두 환경 사이로는
예측값 CSV 만 건넜다.

paired 비교는 **같은 분할·같은 seed 의 같은 분자**끼리 짝지어야 한다.
그래서 M1 의 예측 파일(reports/baseline_pilot_20261020_v2/predictions.csv)에서
Dummy·RF 의 행별 예측을 읽어 activity_id 로 맞춘 뒤 차이를 낸다.

사용(.venv-ml 로 실행):
  .venv-ml/bin/python scripts/score_dmpnn_pilot22.py \
      --config configs/dmpnn_pilot22.json \
      --dmpnn-predictions reports/dmpnn_pilot22_20261021/dmpnn_predictions.csv \
      --baseline-predictions reports/baseline_pilot_20261020_v2/predictions.csv \
      --out-dir reports/dmpnn_pilot22_20261021
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# M1 과 같은 계산을 보장하기 위해 기존 구현을 그대로 쓴다.
from egfr_lab.modeling.baseline import metrics, paired_cluster_ci  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--dmpnn-predictions", type=Path, required=True)
    ap.add_argument("--baseline-predictions", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    boot = cfg["evaluation"]["bootstrap"]

    dm = pd.read_csv(args.dmpnn_predictions, dtype={"activity_id": str})
    base = pd.read_csv(args.baseline_predictions, dtype={"activity_id": str})

    score_rows: list[dict] = []
    paired_rows: list[dict] = []

    for scheme in sorted(dm.scheme.unique()):
        for seed in sorted(dm.seed.unique()):
            d = dm[(dm.scheme == scheme) & (dm.seed == seed)].sort_values("activity_id").reset_index(drop=True)
            # Dummy 는 seed 에 의존하지 않지만, 짝짓기를 틀리지 않도록 같은 seed 행을 쓴다.
            ref = {}
            for model in ("Dummy", "RandomForest"):
                r = base[(base.scheme == scheme) & (base.seed == seed) & (base.model == model)]
                ref[model] = r.sort_values("activity_id").reset_index(drop=True)

            # 세 모델이 같은 분자·같은 순서인지 확인한 뒤에만 비교한다.
            for model, r in ref.items():
                if list(r.activity_id) != list(d.activity_id):
                    raise SystemExit(f"거부: {scheme} seed{seed} 에서 {model} 과 분자 구성이 다르다")
                if not np.allclose(r.observed_pIC50, d.observed_pIC50, atol=0, rtol=0):
                    raise SystemExit(f"거부: {scheme} seed{seed} 에서 {model} 과 관측 라벨이 다르다")

            y = d.observed_pIC50.to_numpy(dtype=float)
            groups = d.scaffold.to_numpy(dtype=object)
            preds = {
                "DMPNN": d.predicted_pIC50.to_numpy(dtype=float),
                "Dummy": ref["Dummy"].predicted_pIC50.to_numpy(dtype=float),
                "RandomForest": ref["RandomForest"].predicted_pIC50.to_numpy(dtype=float),
            }

            for model, p in preds.items():
                score_rows.append({"scheme": scheme, "seed": seed, "model": model, "n": len(y),
                                   **metrics(y, p)})

            # paired_cluster_ci(y, dummy, rf, ...) 는 두 번째 인자를 기준, 세 번째를 비교 대상으로 보고
            # (|세번째 - y| - |두번째 - y|) 의 평균과 구간을 돌려준다. 음수면 세 번째가 더 낫다.
            for baseline_name in ("Dummy", "RandomForest"):
                res = paired_cluster_ci(y, preds[baseline_name], preds["DMPNN"], groups,
                                        boot["resamples"], boot["seed"])
                paired_rows.append({
                    "scheme": scheme, "seed": seed,
                    "comparison": f"DMPNN_minus_{baseline_name}",
                    "DMPNN_minus_baseline_MAE": res["RF_minus_Dummy_MAE"],
                    "conditional_CI95_low": res["conditional_CI95_low"],
                    "conditional_CI95_high": res["conditional_CI95_high"],
                    "scaffold_clusters": res["scaffold_clusters"],
                    "ci_contains_zero": bool(res["conditional_CI95_low"] <= 0 <= res["conditional_CI95_high"]),
                    "direction": ("D-MPNN 오차가 더 작음" if res["RF_minus_Dummy_MAE"] < 0
                                  else "D-MPNN 오차가 더 큼"),
                })

    scores = pd.DataFrame(score_rows)
    paired = pd.DataFrame(paired_rows)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    scores.to_csv(args.out_dir / "dmpnn_metrics.csv", index=False)
    paired.to_csv(args.out_dir / "dmpnn_paired_comparison.csv", index=False)

    # 사전 예상이 맞았는지 기계적으로 판정한다. 서술을 나중에 만들지 않는다.
    primary = cfg["split"]["primary_scheme"]
    vs_dummy = paired[(paired.scheme == primary) & (paired.comparison == "DMPNN_minus_Dummy")]
    worse = int((vs_dummy.DMPNN_minus_baseline_MAE > 0).sum())
    undetermined = int(vs_dummy.ci_contains_zero.sum())

    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "milestone": "M2",
        "stage": "2_scoring",
        "config_sha256": sha256(args.config),
        "dmpnn_predictions_sha256": sha256(args.dmpnn_predictions),
        "baseline_predictions_sha256": sha256(args.baseline_predictions),
        "metric_implementation": "src/egfr_lab/modeling/baseline.py 의 metrics(), paired_cluster_ci() 를 import",
        "metric_environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "bootstrap": boot,
        "mean_MAE_by_model_and_scheme": (
            scores.groupby(["scheme", "model"]).MAE.mean().round(4).unstack().to_dict()
        ),
        "prior_expectation": cfg["prior_expectation_frozen_before_execution"]["statement"],
        "prior_expectation_outcome": {
            "primary_scheme": primary,
            "seeds_where_dmpnn_worse_than_dummy": worse,
            "seeds_total": len(vs_dummy),
            "seeds_where_ci_contains_zero": undetermined,
            "verdict": ("사전 예상대로 D-MPNN 이 Dummy 보다 나빴다" if worse == len(vs_dummy)
                        else "사전 예상과 다르게 나온 seed 가 있다"),
        },
        "must_not_claim": cfg["forbidden"],
    }
    (args.out_dir / "dmpnn_scoring_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    pd.set_option("display.width", 200)
    print("=== 지표 (scheme·seed·model) ===")
    print(scores.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print("\n=== paired 비교 (scaffold 단위 부트스트랩 2000회) ===")
    print(paired[["scheme", "seed", "comparison", "DMPNN_minus_baseline_MAE",
                  "conditional_CI95_low", "conditional_CI95_high", "ci_contains_zero"]]
          .to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print("\n사전 예상 판정:", summary["prior_expectation_outcome"]["verdict"])
    print("저장:", args.out_dir / "dmpnn_scoring_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
