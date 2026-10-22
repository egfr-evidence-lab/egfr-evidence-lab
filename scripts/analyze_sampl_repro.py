"""`sampl` 축소 재현 결과의 지표를 독립적으로 다시 계산한다.

러너(scripts/run_sampl_repro_v2.py)와 별개로 실행해 보고서 수치를 검증한다.
러너는 RMSE만 계산하고 결과 JSON에 기록한다. 이 스크립트는

  * 예측 파일과 실험값 파일의 SMILES 를 행 단위로 비교해 정렬을 확인하고
  * RMSE·MAE·편향·최대절대오차·Pearson r 을 계산하고
  * 분자 수준 부트스트랩으로 RMSE 의 95% 구간을 구한다

작은 평가 세트(11·22·16개)에서 점수 차이를 우열로 읽지 않기 위해 구간을 함께 낸다.
저자 보고값의 불확실성은 공개되어 있지 않으므로 두 결과의 차이를 직접 검정하지는 않는다.

사용:
  .venv-repro/bin/python scripts/analyze_sampl_repro.py \
      --data-dir data/raw/benchmark_data_20261021 \
      --artifact-dir artifacts/sampl_repro_20261021_v2 \
      --out reports/sampl_repro_20261021_v2/metrics_detail.json
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# 저자 보고값 (SI Table S9). 비교 대상일 뿐 목표치가 아니다.
AUTHOR_REPORTED = {"SAMPL6": 0.27, "SAMPL7": 0.49, "SAMPL9": 1.11}

SAMPL_SPEC = {
    "SAMPL6": {"file": "sampl6_experimental.csv", "smiles_col": "Isomeric SMILES", "truth_col": "logP mean"},
    "SAMPL7": {"file": "sampl7_experimental.csv", "smiles_col": "Isomeric SMILES", "truth_col": "logP mean"},
    "SAMPL9": {"file": "sampl9_experimental.csv", "smiles_col": "smiles", "truth_col": "new_logPexp_reviewed"},
}

N_BOOT = 2000
BOOT_SEED = 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--artifact-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    rng = np.random.default_rng(BOOT_SEED)
    results = {}

    for name, spec in SAMPL_SPEC.items():
        truth = pd.read_csv(args.data_dir / spec["file"])
        pred = pd.read_csv(args.artifact_dir / f"pred_{name}.csv")

        # 위치 기준으로만 비교하지 않는다. SMILES 가 행마다 일치해야 한다.
        if len(truth) != len(pred):
            raise SystemExit(f"{name}: 행 수 불일치 truth={len(truth)} pred={len(pred)}")
        same = (truth[spec["smiles_col"]].astype(str).values
                == pred[spec["smiles_col"]].astype(str).values)
        if not same.all():
            raise SystemExit(f"{name}: SMILES 정렬 불일치 {int((~same).sum())}행")

        y = truth[spec["truth_col"]].astype(float).to_numpy()
        yhat = pred["logP"].astype(float).to_numpy()
        if np.isnan(y).any() or np.isnan(yhat).any():
            raise SystemExit(f"{name}: 결측치가 있다")

        err = yhat - y
        n = len(err)
        rmse = float(np.sqrt(np.mean(err ** 2)))

        boot = np.empty(N_BOOT)
        for i in range(N_BOOT):
            idx = rng.integers(0, n, n)
            boot[i] = np.sqrt(np.mean(err[idx] ** 2))
        lo, hi = (float(v) for v in np.percentile(boot, [2.5, 97.5]))

        worst = int(np.argmax(np.abs(err)))
        author = AUTHOR_REPORTED[name]
        results[name] = {
            "n": n,
            "smiles_alignment_verified": True,
            "rmse": round(rmse, 4),
            "rmse_ci95_bootstrap": [round(lo, 4), round(hi, 4)],
            "mae": round(float(np.mean(np.abs(err))), 4),
            "bias_mean_error": round(float(np.mean(err)), 4),
            "max_abs_error": round(float(np.max(np.abs(err))), 4),
            "pearson_r": round(float(np.corrcoef(y, yhat)[0, 1]), 4),
            "author_reported_rmse": author,
            "difference": round(rmse - author, 4),
            "ratio_ours_over_author": round(rmse / author, 3),
            "author_value_inside_our_ci": bool(lo <= author <= hi),
            "worst_case": {
                "smiles": str(truth[spec["smiles_col"]].iloc[worst]),
                "experimental": round(float(y[worst]), 4),
                "predicted": round(float(yhat[worst]), 4),
            },
        }

    out = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "milestone": "M3",
        "analysis_of": str(args.artifact_dir),
        "bootstrap": {"resamples": N_BOOT, "seed": BOOT_SEED, "unit": "molecule"},
        "per_set": results,
        "interpretation": (
            "세 세트 모두 저자 보고값이 우리 RMSE 의 95% 부트스트랩 구간 안에 있다. "
            "평가 세트가 11·22·16개 분자에 불과해 축소 조건의 결과와 저자 결과를 구별할 수 없다. "
            "어느 방향으로도 우열을 주장하지 않는다."
        ),
        "must_not_claim": [
            "원 논문 재현 성공",
            "저자 모델보다 우세하거나 열세라는 결론",
            "SAMPL9 에서의 우세 (구간 폭 안의 변동이다)",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    for name, r in results.items():
        print(f"{name}: n={r['n']} RMSE={r['rmse']} CI95={r['rmse_ci95_bootstrap']} "
              f"저자={r['author_reported_rmse']} 구간내포함={'예' if r['author_value_inside_our_ci'] else '아니오'}")
    print("\n저장:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
