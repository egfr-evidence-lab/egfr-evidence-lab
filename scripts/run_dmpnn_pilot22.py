"""M2 1단계 — pilot22 코호트에서 D-MPNN(Chemprop v1.6.1)을 고정 분할로 학습·예측한다.

이 스크립트는 **예측값만** 만든다. 지표 계산과 Dummy·RF 대비 paired 비교는
scripts/score_dmpnn_pilot22.py 가 M1 과 같은 환경(.venv-ml)에서 수행한다.
학습에 필요한 구버전 스택과 M1 의 지표 환경이 다르기 때문이며, 두 환경 사이로는
예측값 CSV 만 건넌다.

지켜야 할 것(configs/dmpnn_pilot22.json 에 고정):
  * M1 이 만든 고정 분할(reports/baseline_pilot_20261020_v2/split_assignments.csv)을 그대로 읽는다.
    다시 나누지 않는다.
  * 검증 자료는 **학습 fold 안에서만** scaffold 단위로 떼어낸다. 평가 fold 는
    학습에도 체크포인트 선택에도 쓰지 않는다.
  * 하이퍼파라미터 탐색 0회. 구조·epoch·배치는 설정값으로 고정한다.

사용(.venv-repro 로 실행):
  .venv-repro/bin/python scripts/run_dmpnn_pilot22.py \
      --config configs/dmpnn_pilot22.json \
      --output-dir artifacts/dmpnn_pilot22_20261021 \
      --report-dir reports/dmpnn_pilot22_20261021
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

POLL_SEC = 2
SHUTDOWN_GRACE_SEC = 120


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_watched(cmd: list[str], log: Path, is_done, label: str) -> dict:
    """프로세스를 띄우고 완료 표식을 감시한다.

    M3 에서 계산 완료 후에도 chemprop 프로세스가 종료되지 않는 결함을 겪었다
    (configs/benchmark_repro_v2.json 의 why_v2_exists 참조). num_workers 0 으로
    해소했지만, 같은 일이 또 나도 파이프라인이 멈추지 않도록 감시를 남긴다.
    완료 표식이 없는 종료는 실패로 처리한다(fail-closed).
    """
    log.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    with log.open("w", encoding="utf-8") as f:
        proc = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, text=True)
        done_at: float | None = None
        while True:
            rc = proc.poll()
            if rc is not None:
                if rc != 0:
                    raise SystemExit(f"[{label}] 실패(returncode={rc}): {log}")
                if not is_done():
                    raise SystemExit(f"[{label}] 프로세스는 끝났으나 완료 표식이 없다: {log}")
                return {"elapsed_sec": round(time.time() - start, 1), "termination": "clean_exit"}

            if done_at is None and is_done():
                done_at = time.time()
            elif done_at is not None and time.time() - done_at > SHUTDOWN_GRACE_SEC:
                proc.terminate()
                try:
                    proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                return {"elapsed_sec": round(time.time() - start, 1),
                        "termination": "completed_then_shutdown_hang_terminated"}
            time.sleep(POLL_SEC)


def carve_validation(train_ids: list[str], scaffold_of: dict[str, str], cfg: dict) -> list[str]:
    """학습 fold 안에서만 scaffold 단위로 검증 분자를 고른다.

    평가 fold 의 분자는 애초에 train_ids 에 없으므로 들어갈 수 없다.
    seed 는 모델 seed 와 분리해 고정한다. 같은 fold 면 seed 가 달라도 같은 검증 구성이다.
    """
    inner = cfg["inner_validation"]
    n_train = len(train_ids)
    groups: dict[str, list[str]] = {}
    for aid in train_ids:
        groups.setdefault(scaffold_of[aid], []).append(aid)

    names = sorted(groups)
    rng = np.random.default_rng(inner["seed"])
    order = rng.permutation(len(names))

    target = math.ceil(0.20 * n_train)
    keep_min = math.ceil(n_train / 2)          # 학습에 최소 절반을 남긴다
    chosen: list[str] = []
    n_val = 0
    for idx in order:
        if n_val >= target:
            break
        members = groups[names[idx]]
        if n_train - (n_val + len(members)) < keep_min:
            continue
        chosen.extend(members)
        n_val += len(members)

    if not chosen:                              # 그룹이 모두 너무 클 때의 안전장치
        smallest = min(names, key=lambda g: (len(groups[g]), g))
        chosen = list(groups[smallest])
    return sorted(chosen)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--report-dir", type=Path, required=True)
    args = ap.parse_args()

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    out, rep = args.output_dir, args.report_dir
    for d in (out, rep):
        if d.exists() and any(d.iterdir()):
            raise SystemExit(f"거부: 출력 폴더가 비어 있지 않다. 새 경로를 지정하라: {d}")
        d.mkdir(parents=True, exist_ok=True)

    # 1) 코호트 확인 — 해시가 다르면 다른 자료다. 임의 대입을 막는다.
    cohort_path = ROOT / cfg["cohort"]["path"]
    if sha256(cohort_path) != cfg["cohort"]["sha256"]:
        raise SystemExit("거부: 코호트 해시가 설정과 다르다")
    frame = pd.read_csv(cohort_path, dtype=str, keep_default_na=False)
    frame = frame.sort_values("activity_id").reset_index(drop=True)
    if len(frame) != cfg["cohort"]["expected_rows"]:
        raise SystemExit(f"거부: 행 수 {len(frame)} != {cfg['cohort']['expected_rows']}")
    if set(frame.assay_chembl_id) != {cfg["cohort"]["expected_assay"]}:
        raise SystemExit("거부: 단일 assay 범위가 다르다")

    # 보류 중인 assay 가 섞여 들어오지 않았는지 확인한다.
    holds = json.loads((ROOT / cfg["cohort"]["source_holds_path"]).read_text(encoding="utf-8"))["holds"]
    if set(frame.assay_chembl_id) & {h["assay_chembl_id"] for h in holds}:
        raise SystemExit("거부: 원문 검토 보류 assay 가 포함돼 있다")

    smiles_of = dict(zip(frame.activity_id, frame[cfg["cohort"]["smiles_column"]]))
    label_of = {a: float(v) for a, v in zip(frame.activity_id, frame[cfg["cohort"]["label_column"]])}

    # 2) M1 이 만든 고정 분할을 그대로 읽는다.
    split = pd.read_csv(ROOT / cfg["split"]["path"], dtype={"activity_id": str})
    scaffold_of = dict(zip(split.activity_id, split.scaffold))

    bin_dir = Path(sys.executable).parent
    chemprop_train = str(bin_dir / "chemprop_train")
    chemprop_predict = str(bin_dir / "chemprop_predict")
    budget = cfg["tuning_budget"]

    rows: list[dict] = []
    fold_log: list[dict] = []

    for scheme in cfg["split"]["schemes"]:
        for fold in sorted(split.loc[split.scheme == scheme, "fold"].unique()):
            sel = split[(split.scheme == scheme) & (split.fold == fold)]
            train_ids = sorted(sel.loc[sel.role == "train", "activity_id"])
            eval_ids = sorted(sel.loc[sel.role == "evaluation", "activity_id"])
            if set(train_ids) & set(eval_ids):
                raise SystemExit(f"거부: {scheme} fold{fold} 에서 학습·평가가 겹친다")

            val_ids = carve_validation(train_ids, scaffold_of, cfg)
            fit_ids = [a for a in train_ids if a not in set(val_ids)]
            if set(val_ids) & set(eval_ids):
                raise SystemExit("거부: 검증 자료에 평가 fold 분자가 들어갔다")

            work = out / f"{scheme}_fold{fold}"
            work.mkdir(parents=True)

            def write_csv(ids: list[str], name: str) -> Path:
                p = work / name
                pd.DataFrame({"smiles": [smiles_of[a] for a in ids],
                              "pIC50": [label_of[a] for a in ids]}).to_csv(p, index=False)
                return p

            fit_p, val_p, eval_p = (write_csv(fit_ids, "fit.csv"),
                                    write_csv(val_ids, "val.csv"),
                                    write_csv(eval_ids, "eval.csv"))

            for seed in cfg["model_seeds"]:
                save_dir = work / f"seed{seed}"
                pred_path = work / f"pred_seed{seed}.csv"
                t = run_watched([
                    chemprop_train,
                    "--dataset_type", "regression",
                    "--data_path", str(fit_p),
                    "--separate_val_path", str(val_p),
                    "--separate_test_path", str(eval_p),
                    "--epochs", str(budget["epochs"]),
                    "--batch_size", str(budget["batch_size"]),
                    "--ensemble_size", str(budget["ensemble_size"]),
                    "--num_workers", str(budget["num_workers"]),
                    "--save_dir", str(save_dir),
                    "--seed", str(seed),
                    # chemprop v1 에서 --seed 는 '데이터 분할' 시드다. 분할 파일을 직접 주는
                    # 이 실험에서는 아무 역할도 하지 않는다. 가중치 초기화는 --pytorch_seed 가
                    # 결정하며 기본값이 0 이라, 이를 빠뜨리면 모든 seed 가 같은 모델이 된다.
                    "--pytorch_seed", str(seed),
                    "--quiet",
                ], rep / f"log_train_{scheme}_f{fold}_s{seed}.txt",
                    lambda d=save_dir: (d / "quiet.log").exists()
                    and "Elapsed time =" in (d / "quiet.log").read_text(encoding="utf-8", errors="replace"),
                    f"train {scheme} f{fold} s{seed}")

                run_watched([
                    chemprop_predict,
                    "--test_path", str(eval_p),
                    "--preds_path", str(pred_path),
                    "--checkpoint_dir", str(save_dir),
                    "--smiles_column", "smiles",
                    "--num_workers", str(budget["num_workers"]),
                ], rep / f"log_pred_{scheme}_f{fold}_s{seed}.txt",
                    lambda p=pred_path, n=len(eval_ids): p.exists()
                    and sum(1 for _ in p.open(encoding="utf-8")) >= n + 1,
                    f"pred {scheme} f{fold} s{seed}")

                pred = pd.read_csv(pred_path)
                if list(pred["smiles"]) != [smiles_of[a] for a in eval_ids]:
                    raise SystemExit(f"거부: 예측 파일의 SMILES 순서가 평가 fold 와 다르다 ({scheme} f{fold} s{seed})")
                for aid, yhat in zip(eval_ids, pred["pIC50"].astype(float)):
                    rows.append({
                        "scheme": scheme, "fold": int(fold), "seed": seed, "model": "DMPNN",
                        "activity_id": aid, "scaffold": scaffold_of[aid],
                        "observed_pIC50": label_of[aid], "predicted_pIC50": float(yhat),
                        "absolute_error": abs(float(yhat) - label_of[aid]),
                    })

                fold_log.append({
                    "scheme": scheme, "fold": int(fold), "seed": seed,
                    "fit_rows": len(fit_ids), "validation_rows": len(val_ids),
                    "evaluation_rows": len(eval_ids),
                    "m1_train_rows_for_same_fold": len(train_ids),
                    "rows_lost_to_validation": len(train_ids) - len(fit_ids),
                    "train_scaffolds": len({scaffold_of[a] for a in fit_ids}),
                    "validation_scaffolds": len({scaffold_of[a] for a in val_ids}),
                    "train_seconds": t["elapsed_sec"], "termination": t["termination"],
                })
                print(f"  {scheme} fold{fold} seed{seed}: 학습 {len(fit_ids)}개 / 검증 {len(val_ids)}개 "
                      f"/ 평가 {len(eval_ids)}개, {t['elapsed_sec']:.0f}초", flush=True)

    predictions = pd.DataFrame(rows)
    predictions.to_csv(rep / "dmpnn_predictions.csv", index=False)

    meta = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "milestone": "M2",
        "stage": "1_training_and_prediction",
        "config_path": str(args.config),
        "config_sha256": sha256(args.config),
        "cohort_sha256": cfg["cohort"]["sha256"],
        "split_sha256": sha256(ROOT / cfg["split"]["path"]),
        "tuning_budget": budget,
        "inner_validation": cfg["inner_validation"],
        "model_seeds": cfg["model_seeds"],
        "environment": {
            "python": platform.python_version(),
            "platform": f"{platform.system()} {platform.machine()}",
            "note": "학습 환경. 지표 계산은 .venv-ml 에서 별도로 수행한다",
        },
        "runs": fold_log,
        "total_rows_predicted": len(predictions),
        "prior_expectation_frozen": cfg["prior_expectation_frozen_before_execution"]["statement"],
        "seed_arguments": {
            "seed": "chemprop --seed (데이터 분할용). 분할 파일을 직접 주므로 이 실험에서는 효과 없음",
            "pytorch_seed": "chemprop --pytorch_seed (가중치 초기화). 모델 간 차이를 만드는 것은 이쪽이다",
            "both_set_to": "model_seeds 의 같은 값",
        },
        "implementation_correction_20261021": {
            "defect": "최초 실행(reports/dmpnn_pilot22_20261021)은 --pytorch_seed 를 넘기지 않아 "
                      "세 seed 가 모두 기본값 0 으로 같은 초기 가중치를 썼다. seed 간 예측 차이가 "
                      "최대 7e-05 로 부동소수점 잡음 수준이었고, 설정에 고정한 "
                      "'seed 간 차이를 분산의 증거로 기록한다'가 실제로는 측정되지 않았다",
            "cause": "chemprop v1 에서 --seed 는 데이터 분할 시드이고 가중치 초기화는 --pytorch_seed 가 맡는다. "
                     "분할 파일을 직접 지정하는 이 실험에서 --seed 는 아무 역할도 하지 않는다",
            "fix": "--pytorch_seed 를 model_seeds 와 같은 값으로 함께 넘긴다",
            "disclosure": "이 수정은 최초 실행의 지표를 본 뒤에 했다. 다만 수정의 근거는 점수가 아니라 "
                          "chemprop 인자 문서와 '세 seed 결과가 동일하다'는 관찰이며, 설정의 요구를 "
                          "충족하기 위한 것이다. 최초 실행 산출물은 지우지 않고 보존하고 두 실행을 함께 보고한다",
            "preserved": "reports/dmpnn_pilot22_20261021/, artifacts/dmpnn_pilot22_20261021/",
        },
        "next_step": "scripts/score_dmpnn_pilot22.py 를 .venv-ml 로 실행해 지표와 paired 비교를 계산한다",
    }
    (rep / "dmpnn_run_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n예측 {len(predictions)}행 저장: {rep / 'dmpnn_predictions.csv'}")
    print(f"실행 기록 저장: {rep / 'dmpnn_run_meta.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
