"""Agent 의 predict_activity 도구가 쓸 예측기를 만든다.

M1 은 교차검증 fold 별 모델만 저장했다. 조회 도구는 하나의 모델이 필요하므로
**M1 과 같은 고정 설정**으로 22건 전체에 RandomForest 를 적합시켜 저장한다.
하이퍼파라미터·지문 설정은 configs/baseline_pilot.json 을 그대로 읽어 쓰며
새로 고르지 않는다.

함께 저장하는 것(이쪽이 더 중요하다):
  * 학습 분자의 지문과 scaffold — 질의 분자가 **적용 범위 안인지** 판정하는 데 쓴다.
  * M1 에서 측정된 한계 — Dummy 대비 우위 미확정(CI 가 0 포함), 표본 22건,
    scaffold 12개, 단일 문헌, 라벨 폭 1.65 로그 단위.

predict_activity 는 숫자만 돌려주면 안 된다. 이 한계를 함께 돌려주고,
Agent 가 그것을 답변에 옮기는지를 평가한다.

사용:
  .venv-ml/bin/python scripts/build_agent_predictor.py \
      --baseline-config configs/baseline_pilot.json \
      --out artifacts/agent_predictor_20261021
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

from egfr_lab.modeling.baseline import featurize, validate_pilot  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-config", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    if args.out.exists() and any(args.out.iterdir()):
        raise SystemExit(f"거부: 출력 폴더가 비어 있지 않다. 새 경로를 지정하라: {args.out}")

    policy = json.loads(args.baseline_config.read_text(encoding="utf-8"))
    cohort = ROOT / policy["cohort_path"]
    if sha256(cohort) != policy["cohort_sha256"]:
        raise SystemExit("거부: 코호트 해시가 configs/baseline_pilot.json 과 다르다")

    frame = pd.read_csv(cohort, dtype=str, keep_default_na=False)
    frame = frame.sort_values("activity_id").reset_index(drop=True)
    y = validate_pilot(frame, policy)                 # M1 과 같은 범위 검사를 그대로 통과시킨다
    X, scaffolds = featurize(frame, policy["fingerprint"])

    from sklearn.ensemble import RandomForestRegressor
    rf = policy["random_forest"]
    model = RandomForestRegressor(
        n_estimators=rf["n_estimators"], min_samples_leaf=rf["min_samples_leaf"],
        max_features=rf["max_features"], n_jobs=rf["n_jobs"],
        random_state=policy["model_seeds"][0],
    ).fit(X, y)

    args.out.mkdir(parents=True, exist_ok=True)
    import joblib
    model_path = args.out / "rf_pilot22.joblib"
    joblib.dump(model, model_path)

    # 적용 범위 판정에 쓸 학습 지문과 scaffold 를 함께 저장한다.
    np.savez_compressed(args.out / "training_fingerprints.npz", X=X.astype(np.uint8), y=y)
    (args.out / "training_scaffolds.json").write_text(
        json.dumps(sorted(set(scaffolds.tolist())), ensure_ascii=False, indent=1), encoding="utf-8")

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "agent predict_activity 도구용 예측기",
        "scope": "pilot22 (22건·12 scaffold·단일 문헌·단일 assay CHEMBL4258549)",
        "trained_on": "22건 전체 (교차검증 아님). 성능 추정치는 M1 의 교차검증 결과를 쓴다",
        "settings_source": str(args.baseline_config),
        "settings_sha256": sha256(args.baseline_config),
        "cohort_sha256": policy["cohort_sha256"],
        "fingerprint": policy["fingerprint"],
        "random_forest": rf,
        "random_state": policy["model_seeds"][0],
        "model_sha256": sha256(model_path),
        "n_training_molecules": int(len(y)),
        "n_training_scaffolds": int(len(set(scaffolds.tolist()))),
        "label_range": [float(y.min()), float(y.max())],
        "label_std": float(y.std(ddof=1)),
        "measured_limits_from_m1": {
            "source": "reports/baseline_pilot_20261020_v2/ (M1 교차검증)",
            "scaffold_cv_MAE_rf": [0.29497770415614705, 0.30006583884019095, 0.29251061026459263],
            "scaffold_cv_MAE_dummy": 0.3095522524806506,
            "rf_vs_dummy": "3개 seed 모두 차이 구간이 0 을 포함한다. 평균 예측 대비 우위가 확정되지 않았다",
            "dmpnn_note": "M2 에서 D-MPNN 도 Dummy 와 구별되지 않았다(paired 12개 중 11개 구간이 0 포함)",
        },
        "mandatory_caveats": [
            "학습 표본이 22건이고 모두 단일 문헌·단일 실험(CHEMBL4258549)에서 왔다",
            "M1 교차검증에서 이 모델은 평균 예측(Dummy)보다 낫다고 확정되지 않았다",
            "라벨 범위가 pIC50 6.85~8.49(폭 1.65)뿐이라 그 밖의 활성은 예측 근거가 없다",
            "정상형(WT) 생화학 IC50 으로만 학습했다. 변이형·세포 실험·분해제 지표에 쓰지 않는다",
        ],
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
    }
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"예측기 저장: {model_path}")
    print(f"  학습 분자 {manifest['n_training_molecules']}개 / scaffold {manifest['n_training_scaffolds']}개")
    print(f"  라벨 범위 {manifest['label_range'][0]:.2f}~{manifest['label_range'][1]:.2f}")
    print(f"  manifest: {args.out / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
