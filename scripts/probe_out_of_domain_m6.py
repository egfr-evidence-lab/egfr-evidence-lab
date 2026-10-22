"""M6 — 적용 범위 밖 분자의 예측 분포 확인 (사후 관찰).

configs/serving_m6.json 의 verification_plan 에 없던 조사다. V1 검증 중
아스피린(8.055)과 에탄올(8.054)의 예측값이 0.001 차이로 나온 것을 보고
추가로 확인했다. **사전에 고정한 항목이 아니므로 통과·실패로 채점하지 않는다.**

확인하려는 것: 적용 범위 밖에서 이 모델이 입력에 따라 값을 바꾸는가,
아니면 사실상 상수를 돌려주는가.

사용:
  PYTHONPATH=src .venv-serve/bin/python scripts/probe_out_of_domain_m6.py \
      --out reports/serving_m6_20261021
"""
from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/agent_predictor_20261021"

# EGFR 저해제가 아닌, 서로 구조가 크게 다른 흔한 분자들.
# 활성 예측이 목적이 아니다. 모델이 입력 차이에 반응하는지만 본다.
MOLECULES = [
    ("아스피린", "CC(=O)Oc1ccccc1C(=O)O"),
    ("에탄올", "CCO"),
    ("메탄올", "CO"),
    ("벤젠", "c1ccccc1"),
    ("카페인", "Cn1cnc2c1c(=O)n(C)c(=O)n2C"),
    ("포도당", "OCC1OC(O)C(O)C(O)C1O"),
    ("이부프로펜", "CC(C)Cc1ccc(C(C)C(=O)O)cc1"),
    ("파라세타몰", "CC(=O)Nc1ccc(O)cc1"),
    ("니코틴", "CN1CCCC1c1cccnc1"),
    ("콜레스테롤 골격", "CC(C)CCCC(C)C1CCC2C1(C)CCC1C2CC=C2CC(O)CCC12C"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from egfr_lab.agent.tools import ActivityPredictor

    predictor = ActivityPredictor(ARTIFACT)
    manifest = predictor.manifest
    label_std = float(manifest["label_std"])
    lo, hi = manifest["label_range"]

    rows = []
    for name, smiles in MOLECULES:
        res = predictor(smiles)
        if res.status != "ok":
            rows.append({"name": name, "smiles": smiles, "status": res.status,
                         "message": res.message})
            continue
        d = res.data
        app = d["applicability"]
        rows.append({
            "name": name,
            "smiles": smiles,
            "status": "ok",
            "predicted_pIC50": d["predicted_pIC50"],
            "implied_IC50_nM": round(10 ** (9 - d["predicted_pIC50"]), 2),
            "max_tanimoto_to_training": app["max_tanimoto_to_training"],
            "scaffold_in_training": app["scaffold_in_training"],
            "n_caveats": len(res.caveats),
        })
        print(f"{name:16s} pIC50={d['predicted_pIC50']:.3f} "
              f"maxTanimoto={app['max_tanimoto_to_training']:.3f}")

    ok = [r for r in rows if r["status"] == "ok"]
    values = [r["predicted_pIC50"] for r in ok]
    pred_std = statistics.pstdev(values)
    spread = max(values) - min(values)

    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "milestone": "M6",
        "kind": "post_hoc_observation",
        "not_in_frozen_plan": (
            "configs/serving_m6.json 의 verification_plan 에 없는 조사다. "
            "V1 결과를 보고 추가했으므로 통과·실패로 채점하지 않는다"),
        "question": "적용 범위 밖에서 이 모델은 입력에 따라 값을 바꾸는가",
        "artifact": str(ARTIFACT.relative_to(ROOT)),
        "model_sha256": manifest["model_sha256"],
        "n_molecules": len(ok),
        "all_outside_applicability_domain": all(
            not r["scaffold_in_training"] for r in ok),
        "max_tanimoto_range": [min(r["max_tanimoto_to_training"] for r in ok),
                               max(r["max_tanimoto_to_training"] for r in ok)],
        "prediction_min": min(values),
        "prediction_max": max(values),
        "prediction_spread": round(spread, 4),
        "prediction_std": round(pred_std, 5),
        "observed_label_std_in_training": round(label_std, 4),
        "prediction_std_over_label_std": round(pred_std / label_std, 4),
        "training_label_range": [lo, hi],
        "molecules": rows,
        "reading": (
            f"구조가 전혀 다른 분자 {len(ok)}개의 예측값이 "
            f"{min(values):.3f}~{max(values):.3f}(폭 {spread:.3f}) 안에 모였다. "
            f"예측 표준편차 {pred_std:.4f} 는 학습 라벨 표준편차 {label_std:.4f} 의 "
            f"{pred_std / label_std * 100:.0f}% 다. 적용 범위 밖에서 이 모델은 "
            "입력에 거의 반응하지 않고 사실상 상수를 돌려준다"),
        "why_it_matters": (
            "숫자만 돌려주는 API 라면 포도당에 pIC50 8.05(IC50 약 9nM)가 나온다. "
            "적용 범위 판정과 고지를 응답에서 뺄 수 없게 만든 이유가 이것이다"),
        "same_pattern_as_M2": (
            "M2 에서 D-MPNN 도 상수 붕괴를 보였다(예측 표준편차 0.011~0.036 대 관측 0.377). "
            "모델 종류의 문제가 아니라 22건·12 scaffold 라는 학습 규모의 문제로 보인다"),
        "not_claimed": [
            "이 분자들의 실제 EGFR 활성을 주장하지 않는다. 실측값을 조회하지 않았다",
            "'RF 가 나쁘다'는 결론이 아니다. 적용 범위 밖에서 외삽이 되지 않는다는 관찰이다",
            "상수 붕괴의 원인을 규모 하나로 단정하지 않는다. 특징 표현·하이퍼파라미터도 후보다",
        ],
    }

    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "out_of_domain_observation.json"
    if path.exists():
        raise SystemExit(f"거부: 이미 있는 파일을 덮어쓰지 않는다: {path}")
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n예측 폭 {spread:.4f} / 표준편차 {pred_std:.5f}")
    print(f"학습 라벨 표준편차 {label_std:.4f} 의 {pred_std / label_std * 100:.0f}%")
    print("저장:", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
