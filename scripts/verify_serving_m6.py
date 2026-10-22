"""M6 — 추론 서비스 검증.

configs/serving_m6.json 의 verification_plan 을 그대로 실행한다:

  V1 parity        호스트 프로세스와 컨테이너가 같은 입력에 같은 값을 내는가
  V2 model identity /model-info 의 해시가 고정값과 같은가
  V3 restart       재시작 후 다시 로딩되고 같은 값을 내는가
  V4 error         잘못된 입력을 거부하는가 (500 이 나거나 값을 만들면 실패)
  V5 latency       순차 요청 지연시간
  V6 logging       요청·오류가 남고 SMILES 는 남지 않는가

호스트 서버는 이 스크립트가 띄우고 끝날 때 내린다. 컨테이너는 이미 떠 있어야 한다.

사용:
  PYTHONPATH=src .venv-serve/bin/python scripts/verify_serving_m6.py \
      --container-url http://127.0.0.1:8010 \
      --container-name egfr-serve \
      --out reports/serving_m6_20261021
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/serving_m6.json"

TIMEOUT = 30.0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- #
# 서버 기동·대기
# --------------------------------------------------------------------------- #

def wait_ready(base: str, timeout: float = 90.0) -> dict:
    """/readyz 가 200 이 될 때까지 기다린다. 끝까지 안 되면 마지막 응답을 돌려준다."""
    deadline = time.time() + timeout
    last: dict = {"error": "요청 자체가 실패했다"}
    while time.time() < deadline:
        try:
            r = httpx.get(f"{base}/readyz", timeout=5.0)
            last = r.json()
            last["_status_code"] = r.status_code
            if r.status_code == 200:
                last["_waited_seconds"] = round(timeout - (deadline - time.time()), 2)
                return last
        except Exception as exc:                               # noqa: BLE001
            last = {"error": f"{type(exc).__name__}: {exc}"}
        time.sleep(1.0)
    last["_timed_out"] = True
    return last


def start_host_server(port: int) -> subprocess.Popen:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    env["EGFR_SERVING_CONFIG"] = str(CONFIG)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "--factory",
         "egfr_lab.serving.app:app_from_env",
         "--host", "127.0.0.1", "--port", str(port), "--workers", "1",
         "--log-level", "info"],
        cwd=str(ROOT), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return proc


# --------------------------------------------------------------------------- #
# 호출 보조
# --------------------------------------------------------------------------- #

def model_info(base: str) -> dict:
    r = httpx.get(f"{base}/model-info", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def predict(base: str, smiles: list[str]) -> dict:
    r = httpx.post(f"{base}/predict", json={"smiles": smiles}, timeout=TIMEOUT)
    return {"status_code": r.status_code,
            "body": r.json() if r.headers.get("content-type", "").startswith("application/json")
            else {"_raw": r.text[:400]},
            "server_ms": r.headers.get("X-Process-Time-Ms")}


def comparable(result: dict) -> dict:
    """두 환경을 비교할 때 쓰는 부분만 뽑는다. 처리시간은 당연히 다르므로 뺀다."""
    out = {"status": result["status"]}
    if result["status"] == "ok":
        out["predicted_pIC50"] = result["predicted_pIC50"]
        out["in_applicability_domain"] = result["in_applicability_domain"]
        app = dict(result["applicability"])
        out["applicability"] = app
        out["n_caveats"] = len(result["caveats"])
        out["source_ids"] = result["source_ids"]
    else:
        out["message"] = result.get("message")
        out["has_value_field"] = "predicted_pIC50" in result
    return out


def run_probes(base: str, probes: list[dict]) -> list[dict]:
    """probe 분자를 하나씩 따로 보낸다. 배치로 보내면 어느 분자가 실패했는지 섞인다."""
    rows = []
    for p in probes:
        res = predict(base, [p["smiles"]])
        body = res["body"]
        r0 = body["results"][0] if res["status_code"] == 200 and body.get("results") else None
        rows.append({
            "id": p["id"],
            "note": p["note"],
            "status_code": res["status_code"],
            "model_sha256": body.get("model_sha256"),
            "comparable": comparable(r0) if r0 else {"_no_result": True,
                                                     "_body": body},
        })
    return rows


# --------------------------------------------------------------------------- #
# V4 오류 처리
# --------------------------------------------------------------------------- #

def run_error_cases(base: str, max_batch: int) -> list[dict]:
    cases: list[dict] = []

    def record(name: str, expectation: str, status_code: int, passed: bool,
               detail: object = None) -> None:
        cases.append({"case": name, "expectation": expectation,
                      "status_code": status_code, "passed": passed, "detail": detail})

    r = httpx.post(f"{base}/predict", json={"smiles": []}, timeout=TIMEOUT)
    record("빈 배열", "422", r.status_code, r.status_code == 422)

    r = httpx.post(f"{base}/predict", json={"smiles": [""]}, timeout=TIMEOUT)
    body = r.json() if r.status_code == 200 else {}
    res = (body.get("results") or [{}])[0]
    ok = (r.status_code == 200 and res.get("status") == "error"
          and "predicted_pIC50" not in res)
    record("빈 문자열 SMILES", "status=error 이고 값 필드 없음", r.status_code, ok,
           {"result": res})

    r = httpx.post(f"{base}/predict", json={"smiles": ["this-is-not-a-molecule"]},
                   timeout=TIMEOUT)
    body = r.json() if r.status_code == 200 else {}
    res = (body.get("results") or [{}])[0]
    ok = (r.status_code == 200 and res.get("status") == "error"
          and "predicted_pIC50" not in res)
    record("해석 불가 문자열", "status=error 이고 값 필드 없음", r.status_code, ok,
           {"result": res})

    r = httpx.post(f"{base}/predict", json={"smiles": ["CCO"] * (max_batch + 1)},
                   timeout=TIMEOUT)
    record(f"max_batch({max_batch}) 초과", "413", r.status_code, r.status_code == 413)

    r = httpx.post(f"{base}/predict", json={"molecules": ["CCO"]}, timeout=TIMEOUT)
    record("smiles 필드 없음", "422", r.status_code, r.status_code == 422)

    r = httpx.post(f"{base}/predict", content=b"not json at all",
                   headers={"Content-Type": "application/json"}, timeout=TIMEOUT)
    record("JSON 아닌 본문", "4xx (500 이면 실패)", r.status_code,
           400 <= r.status_code < 500)

    r = httpx.post(f"{base}/predict", json={"smiles": "CCO"}, timeout=TIMEOUT)
    record("smiles 가 배열이 아님", "422", r.status_code, r.status_code == 422)

    for path in ("/train", "/fit", "/retrain"):
        r = httpx.post(f"{base}{path}", json={}, timeout=TIMEOUT)
        record(f"학습 엔드포인트 {path}", "404", r.status_code, r.status_code == 404)

    return cases


# --------------------------------------------------------------------------- #
# V5 지연시간
# --------------------------------------------------------------------------- #

def measure_latency(base: str, smiles: str, warmup: int, n: int) -> dict:
    payload = {"smiles": [smiles]}
    with httpx.Client(timeout=TIMEOUT) as client:
        for _ in range(warmup):
            client.post(f"{base}/predict", json=payload)

        client_ms: list[float] = []
        server_ms: list[float] = []
        for _ in range(n):
            t0 = time.perf_counter()
            r = client.post(f"{base}/predict", json=payload)
            client_ms.append((time.perf_counter() - t0) * 1000)
            if r.status_code != 200:
                raise SystemExit(f"측정 중 비정상 응답: {r.status_code} {r.text[:200]}")
            if r.headers.get("X-Process-Time-Ms"):
                server_ms.append(float(r.headers["X-Process-Time-Ms"]))

    def summarize(xs: list[float]) -> dict:
        xs_sorted = sorted(xs)
        return {
            "n": len(xs),
            "p50": round(statistics.median(xs_sorted), 3),
            "p95": round(xs_sorted[min(len(xs_sorted) - 1, int(0.95 * len(xs_sorted)))], 3),
            "min": round(xs_sorted[0], 3),
            "max": round(xs_sorted[-1], 3),
            "mean": round(statistics.fmean(xs_sorted), 3),
        }

    return {
        "warmup_discarded": warmup,
        "sequential_requests": n,
        "batch_size": 1,
        "client_side_ms": summarize(client_ms),
        "server_side_ms": summarize(server_ms) if server_ms else None,
        "not_claimed": "처리량·동시 부하 성능이 아니다. 순차 요청 1배치의 측정이다",
    }


# --------------------------------------------------------------------------- #
# V3 재시작 · V6 로그
# --------------------------------------------------------------------------- #

def docker(*args: str) -> str:
    out = subprocess.run(["docker", *args], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"docker {' '.join(args)} 실패: {out.stderr[:400]}")
    return out.stdout


def restart_cycles(name: str, base: str, probes: list[dict], baseline: list[dict],
                   cycles: int) -> list[dict]:
    rows = []
    for i in range(1, cycles + 1):
        t0 = time.perf_counter()
        docker("restart", name)
        ready = wait_ready(base)
        wall = time.perf_counter() - t0
        after = run_probes(base, probes)
        same = [a["comparable"] == b["comparable"] for a, b in zip(after, baseline)]
        rows.append({
            "cycle": i,
            "readyz_status_code": ready.get("_status_code"),
            "ready": ready.get("ready"),
            "model_load_seconds": ready.get("load_seconds"),
            "restart_to_ready_wall_seconds": round(wall, 2),
            "hash_checks_all_match": all(
                p["match"] for p in (ready.get("hash_checks") or {}).values()) or False,
            "predictions_identical_to_first_run": all(same),
            "mismatched_probe_ids": [a["id"] for a, ok in zip(after, same) if not ok],
        })
    return rows


def check_logs(name: str, secret_smiles: list[str]) -> dict:
    raw = docker("logs", name)
    lines = raw.splitlines()
    request_lines = [ln for ln in lines if re.search(r"(GET|POST) /\S+ -> \d{3}", ln)]
    timed = [ln for ln in request_lines if re.search(r"\d+\.\d+ms", ln)]
    leaked = [s for s in secret_smiles if s and s in raw]
    return {
        "total_log_lines": len(lines),
        "request_lines": len(request_lines),
        "request_lines_with_duration": len(timed),
        "sample_request_lines": request_lines[-3:],
        "smiles_leaked_into_logs": leaked,
        "passed": bool(request_lines) and len(timed) == len(request_lines) and not leaked,
        "note": "요청 경로·상태코드·처리시간은 남기고 입력 SMILES 는 남기지 않는다",
    }


# --------------------------------------------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--container-url", default="http://127.0.0.1:8010")
    ap.add_argument("--container-name", default="egfr-serve")
    ap.add_argument("--host-port", type=int, default=8011)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--warmup", type=int, default=20)
    ap.add_argument("--requests", type=int, default=200)
    ap.add_argument("--restart-cycles", type=int, default=2)
    args = ap.parse_args()

    if args.out.exists() and any(args.out.iterdir()):
        raise SystemExit(f"거부: 출력 폴더가 비어 있지 않다. 새 경로를 지정하라: {args.out}")

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    probes = cfg["probe_molecules"]
    expected = cfg["served_model"]
    max_batch = int(cfg["api_contract"]["predict_request"]["max_batch"])
    plan = cfg["verification_plan"]
    latency_smiles = next(p["smiles"] for p in probes if p["id"] == "P-in-1")

    host_base = f"http://127.0.0.1:{args.host_port}"
    container_base = args.container_url

    print("호스트 서버 기동...")
    proc = start_host_server(args.host_port)
    results: dict = {}
    try:
        host_ready = wait_ready(host_base)
        if host_ready.get("_status_code") != 200:
            raise SystemExit(f"호스트 서버가 준비되지 않았다: {host_ready}")
        print(f"  준비됨 (모델 로딩 {host_ready['load_seconds']}s)")

        print("컨테이너 상태 확인...")
        cont_ready = wait_ready(container_base)
        if cont_ready.get("_status_code") != 200:
            raise SystemExit(f"컨테이너가 준비되지 않았다: {cont_ready}")
        print(f"  준비됨 (모델 로딩 {cont_ready['load_seconds']}s)")

        # --- V2: 두 환경 모두 고정 해시와 같은가 ----------------------------- #
        print("V2 모델 동일성...")
        v2 = {}
        for label, base in (("host", host_base), ("container", container_base)):
            info = model_info(base)
            m = info["model"]
            checks = {k: {"expected": expected[k], "actual": m.get(k),
                          "match": expected[k] == m.get(k)}
                      for k in ("model_sha256", "cohort_sha256", "settings_sha256")}
            v2[label] = {
                "hash_checks": checks,
                "all_match": all(c["match"] for c in checks.values()),
                "n_training_molecules": m.get("n_training_molecules"),
                "n_training_scaffolds": m.get("n_training_scaffolds"),
                "training_label_range": m.get("training_label_range"),
                "runtime": info["runtime"],
                "config_sha256": info["config"]["sha256"],
                "mandatory_caveats": info["mandatory_caveats"],
            }
            print(f"  {label}: 해시 3개 일치={v2[label]['all_match']}")
        v2["config_sha256_identical"] = (
            v2["host"]["config_sha256"] == v2["container"]["config_sha256"])
        v2["passed"] = v2["host"]["all_match"] and v2["container"]["all_match"]
        results["V2_model_identity"] = {"what": plan["V2_model_identity"]["what"], **v2}

        # --- V1: parity ----------------------------------------------------- #
        print("V1 호스트/컨테이너 동일성...")
        host_probes = run_probes(host_base, probes)
        cont_probes = run_probes(container_base, probes)
        rows = []
        for h, c in zip(host_probes, cont_probes):
            identical = h["comparable"] == c["comparable"]
            rows.append({
                "id": h["id"], "note": h["note"], "identical": identical,
                "host": h["comparable"], "container": c["comparable"],
            })
            print(f"  {h['id']}: 동일={identical}")
        v1_pass = all(r["identical"] for r in rows)
        results["V1_parity"] = {
            "what": plan["V1_parity"]["what"],
            "pass_rule": plan["V1_parity"]["pass_rule"],
            "passed": v1_pass,
            "n_probes": len(rows),
            "n_identical": sum(1 for r in rows if r["identical"]),
            "per_probe": rows,
            "runtime_diff_host_vs_container": {
                k: [v2["host"]["runtime"].get(k), v2["container"]["runtime"].get(k)]
                for k in sorted(set(v2["host"]["runtime"]) | set(v2["container"]["runtime"]))
                if v2["host"]["runtime"].get(k) != v2["container"]["runtime"].get(k)
            },
        }

        # --- V4: 오류 처리 --------------------------------------------------- #
        print("V4 오류 처리...")
        v4 = {}
        for label, base in (("host", host_base), ("container", container_base)):
            cases = run_error_cases(base, max_batch)
            v4[label] = {"cases": cases,
                         "n_passed": sum(1 for c in cases if c["passed"]),
                         "n_cases": len(cases),
                         "failed": [c["case"] for c in cases if not c["passed"]]}
            print(f"  {label}: {v4[label]['n_passed']}/{v4[label]['n_cases']} 통과")
        v4["passed"] = all(v4[l]["n_passed"] == v4[l]["n_cases"]
                           for l in ("host", "container"))
        results["V4_error_handling"] = {"what": plan["V4_error_handling"]["what"], **v4}

        # --- V5: 지연시간 ---------------------------------------------------- #
        print(f"V5 지연시간 (워밍업 {args.warmup} + 측정 {args.requests})...")
        v5 = {"measured_on": plan["V5_latency"]["measured_on"],
              "procedure": plan["V5_latency"]["procedure"],
              "host_measurement_note": "호스트 서버는 macOS 에서 직접 실행한 uvicorn 프로세스다",
              "probe_molecule": "P-in-1"}
        for label, base in (("host", host_base), ("container", container_base)):
            v5[label] = measure_latency(base, latency_smiles, args.warmup, args.requests)
            print(f"  {label}: p50 {v5[label]['client_side_ms']['p50']}ms "
                  f"p95 {v5[label]['client_side_ms']['p95']}ms")
        hp = v5["host"]["client_side_ms"]["p50"]
        cp = v5["container"]["client_side_ms"]["p50"]
        v5["container_over_host_p50_ratio"] = round(cp / hp, 3) if hp else None
        results["V5_latency"] = v5

        # --- V3: 재시작 ------------------------------------------------------ #
        print(f"V3 재시작 {args.restart_cycles}회...")
        v3 = restart_cycles(args.container_name, container_base, probes,
                            cont_probes, args.restart_cycles)
        for row in v3:
            print(f"  {row['cycle']}회차: readyz={row['readyz_status_code']} "
                  f"예측동일={row['predictions_identical_to_first_run']} "
                  f"로딩 {row['model_load_seconds']}s")
        results["V3_restart"] = {
            "what": plan["V3_restart"]["what"],
            "procedure": plan["V3_restart"]["procedure"],
            "passed": all(r["readyz_status_code"] == 200
                          and r["predictions_identical_to_first_run"]
                          and r["hash_checks_all_match"] for r in v3),
            "cycles": v3,
        }

        # --- V6: 로그 -------------------------------------------------------- #
        print("V6 로그...")
        v6 = check_logs(args.container_name, [p["smiles"] for p in probes])
        print(f"  요청 로그 {v6['request_lines']}줄, SMILES 유출 "
              f"{len(v6['smiles_leaked_into_logs'])}건, 통과={v6['passed']}")
        results["V6_logging"] = {"what": plan["V6_logging"]["what"], **v6}

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)

    # --- 사전 예상과 실제 ---------------------------------------------------- #
    pre = cfg["pre_registered_expectations"]
    image = json.loads(docker("image", "inspect", "egfr-pilot22-inference:v1"))[0]
    image_mb = round(image["Size"] / (1024 * 1024), 1)
    comparison = {
        "declared_before_measurement": pre,
        "actual": {
            "host_p50_ms": results["V5_latency"]["host"]["client_side_ms"]["p50"],
            "container_p50_ms": results["V5_latency"]["container"]["client_side_ms"]["p50"],
            "container_vs_host": ("컨테이너가 더 느림"
                                  if results["V5_latency"]["container_over_host_p50_ratio"] > 1
                                  else "컨테이너가 같거나 더 빠름"),
            "model_load_seconds_container": results["V2_model_identity"]["container"]
            and cont_ready["load_seconds"],
            "model_load_seconds_host": host_ready["load_seconds"],
            "parity": "일치" if results["V1_parity"]["passed"] else "불일치",
            "image_size_mb": image_mb,
        },
        "expectations_not_met": [],
    }
    if not (1.0 <= float(host_ready["load_seconds"]) <= 5.0):
        comparison["expectations_not_met"].append(
            f"모델 로딩 예상 1~5초, 호스트 실제 {host_ready['load_seconds']}초")
    if not (1.0 <= float(cont_ready["load_seconds"]) <= 5.0):
        comparison["expectations_not_met"].append(
            f"모델 로딩 예상 1~5초, 컨테이너 실제 {cont_ready['load_seconds']}초")
    hp50 = comparison["actual"]["host_p50_ms"]
    cp50 = comparison["actual"]["container_p50_ms"]
    if not (5.0 <= hp50 <= 30.0):
        comparison["expectations_not_met"].append(f"호스트 p50 예상 5~30ms, 실제 {hp50}ms")
    if not (10.0 <= cp50 <= 60.0):
        comparison["expectations_not_met"].append(f"컨테이너 p50 예상 10~60ms, 실제 {cp50}ms")
    if not (600.0 <= image_mb <= 1400.0):
        comparison["expectations_not_met"].append(f"이미지 예상 600~1400MB, 실제 {image_mb}MB")
    results["pre_registration_vs_actual"] = comparison

    # --- 저장 ---------------------------------------------------------------- #
    checked = ["V1_parity", "V2_model_identity", "V3_restart",
               "V4_error_handling", "V6_logging"]
    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "milestone": "M6",
        "scope": "컨테이너까지. 클라우드 실행은 이 실행에 포함되지 않는다",
        "config_path": str(CONFIG.relative_to(ROOT)),
        "config_sha256": sha256(CONFIG),
        "image": {
            "tag": "egfr-pilot22-inference:v1",
            "id": image["Id"],
            "size_mb": image_mb,
            "architecture": image.get("Architecture"),
            "os": image.get("Os"),
            "base_image_digest_pinned": True,
        },
        "environment": {
            "host_python": platform.python_version(),
            "host_platform": platform.platform(),
            "docker_server_version": docker("version", "--format", "{{.Server.Version}}").strip(),
        },
        "port_note": ("컨테이너를 127.0.0.1:8010 에 묶었다. 8000 은 다른 프로세스가 "
                      "IPv4 로 점유 중이어서 127.0.0.1:8000 요청이 그 프로세스로 갔다. "
                      "/model-info 해시 확인으로 올바른 서비스를 때리는지 검증한다"),
        "verdicts": {k: results[k].get("passed") for k in checked},
        "all_checked_passed": all(results[k].get("passed") for k in checked),
        "latency_is_a_measurement_not_a_verdict": (
            "V5 는 통과·실패로 채점하지 않는다. 합격선을 미리 정하지 않았기 때문이다"),
        "cloud_execution": cfg["cloud_execution"],
        "results": results,
    }

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "verification.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n판정:", json.dumps(summary["verdicts"], ensure_ascii=False))
    print("전체 통과:", summary["all_checked_passed"])
    if comparison["expectations_not_met"]:
        print("사전 예상과 다른 항목:")
        for item in comparison["expectations_not_met"]:
            print("  -", item)
    else:
        print("사전 예상 범위를 벗어난 항목 없음")
    print("저장:", args.out / "verification.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
