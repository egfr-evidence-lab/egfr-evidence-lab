"""Chemprop `sampl` 벤치마크의 축소 재현(선택 C) — v2 실행.

v1(scripts/run_sampl_repro.py)과 무엇이 다른가
----------------------------------------------
1) 데이터로더 워커 수를 설정에서 읽어 명시적으로 지정한다(v2 설정: 0).
   v1 설정(저자 기본값 8)에서는 계산을 끝낸 뒤 chemprop_train 프로세스가
   종료되지 않아 파이프라인이 약 2시간 정지했다. 멈춘 위치는 macOS `sample`
   네이티브 스택으로 확정했다:

       Py_Exit -> Py_FinalizeEx -> finalize_modules -> _PyModule_ClearDict
         -> method_dealloc -> subtype_dealloc -> slot_tp_finalize
           -> os_waitpid -> __wait4        (영구 블록)

   학습 코드가 아니라 인터프리터 종료 처리 중 자식 프로세스 대기에서 멈춘 것이다.
   근거와 통제 비교는 configs/benchmark_repro_v2.json 의 why_v2_exists 에 있다.

2) 단계마다 종료 감시(watchdog)를 둔다. 완료 표식을 확인한 뒤에도 유예 시간
   안에 프로세스가 종료하지 않으면 종료 전용 멈춤으로 판정해 정리하고 그 사실을
   결과에 기록한다. 완료 표식이 없는 종료는 실패로 처리하고 결과를 쓰지 않는다.

저자 코드(chemprop v1.6.1)는 수정하지 않는다. 호출 인자 구조와 평가 컬럼은
저자 scripts/sampl.sh 를 그대로 따른다. **원 논문과 동일 조건 재현이 아니다.**

사용:
  .venv-repro/bin/python scripts/run_sampl_repro_v2.py \
      --config configs/benchmark_repro_v2.json \
      --data-dir data/raw/benchmark_data_20261021 \
      --output-dir artifacts/sampl_repro_20261021_v2 \
      --report-dir reports/sampl_repro_20261021_v2
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

# 평가 파일별 컬럼 정의는 저자 sampl.sh 를 그대로 따른다.
SAMPL_SPEC = {
    "SAMPL6": {"file": "sampl6_experimental.csv", "smiles_col": "Isomeric SMILES", "truth_col": "logP mean"},
    "SAMPL7": {"file": "sampl7_experimental.csv", "smiles_col": "Isomeric SMILES", "truth_col": "logP mean"},
    "SAMPL9": {"file": "sampl9_experimental.csv", "smiles_col": "smiles", "truth_col": "new_logPexp_reviewed"},
}

POLL_SEC = 5


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_watched(cmd: list[str], log: Path, is_done, label: str, grace_sec: int) -> dict:
    """프로세스를 띄우고 완료 표식을 감시한다.

    is_done(): 단계의 계산이 끝났음을 디스크 상태로 판정한다.
    완료 표식 확인 후 grace_sec 안에 종료하지 않으면 종료 전용 멈춤으로 보고 정리한다.
    """
    log.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    print(f"[{label}] 시작", flush=True)
    with log.open("w", encoding="utf-8") as f:
        proc = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, text=True)

        done_at: float | None = None
        while True:
            rc = proc.poll()
            if rc is not None:
                elapsed = time.time() - start
                if rc != 0:
                    raise SystemExit(f"[{label}] 실패(returncode={rc}): {log}")
                if not is_done():
                    raise SystemExit(f"[{label}] 프로세스는 끝났으나 완료 표식이 없다: {log}")
                print(f"[{label}] 정상 종료, {elapsed/60:.1f}분", flush=True)
                return {
                    "label": label,
                    "elapsed_sec": round(elapsed, 1),
                    "termination": "clean_exit",
                    "returncode": rc,
                    "compute_done_at_sec": round(done_at - start, 1) if done_at else None,
                }

            if done_at is None and is_done():
                done_at = time.time()
                print(f"[{label}] 계산 완료 표식 확인 ({(done_at-start)/60:.1f}분). "
                      f"정상 종료를 최대 {grace_sec}초 기다린다", flush=True)
            elif done_at is not None and time.time() - done_at > grace_sec:
                proc.terminate()
                try:
                    proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                elapsed = time.time() - start
                print(f"[{label}] 종료 전용 멈춤으로 판정해 프로세스를 정리했다 "
                      f"(계산 완료 {(done_at-start)/60:.1f}분)", flush=True)
                return {
                    "label": label,
                    "elapsed_sec": round(elapsed, 1),
                    "termination": "completed_then_shutdown_hang_terminated",
                    "returncode": None,
                    "compute_done_at_sec": round(done_at - start, 1),
                    "note": "계산과 산출물 기록이 끝난 뒤 인터프리터 종료 처리에서 멈춘 것을 "
                            "유예 시간 경과 후 정리했다. 계산 결과에는 영향이 없다",
                }

            time.sleep(POLL_SEC)


def marker_training(save_dir: Path):
    """chemprop_train 의 마지막 출력은 quiet.log 의 `Elapsed time =` 이다."""
    def check() -> bool:
        q, s = save_dir / "quiet.log", save_dir / "test_scores.csv"
        if not (q.exists() and s.exists()):
            return False
        try:
            return "Elapsed time =" in q.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
    return check


def marker_predict(pred_path: Path, expect_rows: int):
    """예측 파일에 헤더 1줄 + 기대 행 수가 기록됐는지 본다."""
    def check() -> bool:
        if not pred_path.exists():
            return False
        try:
            with pred_path.open("r", encoding="utf-8") as f:
                return sum(1 for _ in f) >= expect_rows + 1
        except OSError:
            return False
    return check


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--report-dir", type=Path, required=True)
    args = ap.parse_args()

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    red = cfg["reduced_settings"]
    grace = int(cfg.get("safety", {}).get("shutdown_grace_sec", 180))

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

    # 설정에 num_workers 가 있으면 명시 지정한다. 없으면 저자처럼 지정하지 않는다.
    worker_args: list[str] = []
    if "num_workers" in red:
        worker_args = ["--num_workers", str(red["num_workers"])]

    stages: list[dict] = []

    # 1) 저자 분할에서의 학습·평가 (hyperopt 없음: 축소 항목)
    split_dir = out / "split_model"
    stages.append(run_watched([
        chemprop_train,
        "--dataset_type", "regression",
        "--data_path", str(train_p),
        "--separate_val_path", str(val_p),
        "--separate_test_path", str(test_p),
        "--epochs", str(red["epochs_split"]),
        "--aggregation", red["aggregation"],
        "--ensemble_size", str(red["ensemble_size"]),
        "--save_dir", str(split_dir),
        "--extra_metrics", "mae",
        "--seed", str(red["seed"]),
        "--quiet",
        *worker_args,
    ], rep / "log_split_training.txt", marker_training(split_dir), "split_training", grace))

    # 2) production 모델 (전체 자료, 저자와 동일하게 val/test 도 같은 파일 지정)
    prod_dir = out / "production_model"
    stages.append(run_watched([
        chemprop_train,
        "--dataset_type", "regression",
        "--data_path", str(full_p),
        "--separate_val_path", str(full_p),
        "--separate_test_path", str(full_p),
        "--epochs", str(red["epochs_production"]),
        "--aggregation", red["aggregation"],
        "--ensemble_size", str(red["ensemble_size"]),
        "--save_dir", str(prod_dir),
        "--seed", str(red["seed"]),
        "--quiet",
        *worker_args,
    ], rep / "log_production_training.txt", marker_training(prod_dir), "production_training", grace))

    # 3) SAMPL6/7/9 예측과 RMSE
    import pandas as pd
    from sklearn.metrics import mean_squared_error

    sampl_results = {}
    for name, spec in SAMPL_SPEC.items():
        truth_path = data / spec["file"]
        pred_path = out / f"pred_{name}.csv"
        truth = pd.read_csv(truth_path)
        stages.append(run_watched([
            chemprop_predict,
            "--test_path", str(truth_path),
            "--preds_path", str(pred_path),
            "--checkpoint_dir", str(prod_dir),
            "--smiles_column", spec["smiles_col"],
            *worker_args,
        ], rep / f"log_predict_{name}.txt", marker_predict(pred_path, len(truth)), f"predict_{name}", grace))

        pred = pd.read_csv(pred_path)
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
    split_scores = {}
    split_scores_path = split_dir / "test_scores.csv"
    if split_scores_path.exists():
        df = pd.read_csv(split_scores_path)
        for col in df.columns:
            if col.lower().startswith("mean"):
                split_scores[col] = float(df[col].iloc[0])

    result = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "milestone": "M3",
        "status": "reduced_budget_reproduction_not_equal_condition",
        "run_version": "v2",
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
        "stages": stages,
        "author_split_test_scores": split_scores,
        "sampl_results": sampl_results,
        "author_reported": AUTHOR_REPORTED,
        "v1_run_for_comparison": cfg["evaluation"]["v1_split_result_for_comparison"],
        "v1_incident": cfg["why_v2_exists"]["incident"],
        "claim_limits": [
            "하이퍼파라미터 탐색을 생략했고 앙상블 크기를 줄였으므로 원 논문과 동일 조건 비교가 아니다",
            "환경(python/torch/numpy/sklearn)이 저자 환경과 다르다",
            "데이터로더 워커 수를 저자 기본값 8에서 0으로 바꿨다. 종료되지 않는 결함 때문이며 배치 구성·난수 소비 순서가 달라진다",
            "차이가 작더라도 '재현 성공'이 아니라 '축소 조건에서의 결과'로 서술한다",
        ],
    }
    (rep / "sampl_repro_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n결과 저장:", rep / "sampl_repro_result.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
