"""M6 — Cloud Run 추론 서비스 검증.

configs/serving_m6_cloud.json 의 verification_plan 을 실행한다:

  C1 parity          로컬과 같은 입력에 같은 예측값을 내는가
  C2 model identity  /model-info 해시가 고정값과 같은가
  C3 cold start      min-instances 0 에서 첫 요청의 지연
  C4 error handling  오류 10건을 클라우드에서도 같이 처리하는가
  C5 latency         클라이언트 왕복과 서버 처리시간을 **따로** 보고
  C6 usage           실제 사용량. 과금 반영 지연을 감안한다
  C7 logs            요청·오류가 남고 SMILES 는 남지 않는가

인증 토큰은 메모리에만 둔다. 결과 JSON·로그·예외 메시지에 싣지 않는다.

사용:
  PYTHONPATH=src .venv-serve/bin/python scripts/verify_serving_cloud_m6.py \
      --url https://... --service egfr-pilot22-inference \
      --out reports/serving_m6_cloud_20261022
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
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
CLOUD_CONFIG = ROOT / "configs/serving_m6_cloud.json"
LOCAL_CONFIG = ROOT / "configs/serving_m6.json"
LOCAL_BASELINE = ROOT / "reports/serving_m6_20261021/verification.json"

TIMEOUT = 90.0
GCLOUD = "/opt/homebrew/share/google-cloud-sdk/bin/gcloud"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gcloud(*args: str, timeout: int = 180) -> str:
    """gcloud 호출. 실패하면 stderr 앞부분만 올린다(토큰이 섞이지 않게)."""
    exe = GCLOUD if Path(GCLOUD).exists() else "gcloud"
    proc = subprocess.run([exe, *args], capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise SystemExit(f"gcloud {' '.join(args[:3])} 실패: {proc.stderr.strip()[:500]}")
    return proc.stdout


def identity_token() -> str:
    """Cloud Run 호출용 ID 토큰. 반환값을 저장하지 않는다."""
    return gcloud("auth", "print-identity-token").strip()


# --------------------------------------------------------------------------- #

def comparable(result: dict) -> dict:
    """비교 대상만 뽑는다. 처리시간은 당연히 다르므로 뺀다."""
    out = {"status": result["status"]}
    if result["status"] == "ok":
        out["predicted_pIC50"] = result["predicted_pIC50"]
        out["in_applicability_domain"] = result["in_applicability_domain"]
        out["applicability"] = dict(result["applicability"])
        out["n_caveats"] = len(result["caveats"])
        out["source_ids"] = result["source_ids"]
    else:
        out["message"] = result.get("message")
        out["has_value_field"] = "predicted_pIC50" in result
    return out


def run_probes(client: httpx.Client, url: str, probes: list[dict]) -> list[dict]:
    rows = []
    for p in probes:
        r = client.post(f"{url}/predict", json={"smiles": [p["smiles"]]})
        body = r.json() if r.status_code == 200 else {}
        res = (body.get("results") or [None])[0]
        rows.append({
            "id": p["id"], "note": p["note"], "status_code": r.status_code,
            "model_sha256": body.get("model_sha256"),
            "comparable": comparable(res) if res else {"_no_result": True},
        })
    return rows


def run_error_cases(client: httpx.Client, url: str, max_batch: int) -> list[dict]:
    cases: list[dict] = []

    def record(name, expectation, code, passed, detail=None):
        cases.append({"case": name, "expectation": expectation, "status_code": code,
                      "passed": passed, "detail": detail})

    r = client.post(f"{url}/predict", json={"smiles": []})
    record("빈 배열", "422", r.status_code, r.status_code == 422)

    for label, smiles in (("빈 문자열 SMILES", ""), ("해석 불가 문자열", "this-is-not-a-molecule")):
        r = client.post(f"{url}/predict", json={"smiles": [smiles]})
        body = r.json() if r.status_code == 200 else {}
        res = (body.get("results") or [{}])[0]
        ok = (r.status_code == 200 and res.get("status") == "error"
              and "predicted_pIC50" not in res)
        record(label, "status=error 이고 값 필드 없음", r.status_code, ok, {"result": res})

    r = client.post(f"{url}/predict", json={"smiles": ["CCO"] * (max_batch + 1)})
    record(f"max_batch({max_batch}) 초과", "413", r.status_code, r.status_code == 413)

    r = client.post(f"{url}/predict", json={"molecules": ["CCO"]})
    record("smiles 필드 없음", "422", r.status_code, r.status_code == 422)

    r = client.post(f"{url}/predict", content=b"not json at all",
                    headers={"Content-Type": "application/json"})
    record("JSON 아닌 본문", "4xx (500 이면 실패)", r.status_code,
           400 <= r.status_code < 500)

    r = client.post(f"{url}/predict", json={"smiles": "CCO"})
    record("smiles 가 배열이 아님", "422", r.status_code, r.status_code == 422)

    for path in ("/train", "/fit", "/retrain"):
        r = client.post(f"{url}{path}", json={})
        record(f"학습 엔드포인트 {path}", "404", r.status_code, r.status_code == 404)

    return cases


def summarize(xs: list[float]) -> dict:
    s = sorted(xs)
    return {"n": len(s), "p50": round(statistics.median(s), 3),
            "p95": round(s[min(len(s) - 1, int(0.95 * len(s)))], 3),
            "min": round(s[0], 3), "max": round(s[-1], 3),
            "mean": round(statistics.fmean(s), 3)}


def measure_latency(client: httpx.Client, url: str, smiles: str,
                    warmup: int, n: int) -> dict:
    payload = {"smiles": [smiles]}
    for _ in range(warmup):
        client.post(f"{url}/predict", json=payload)

    client_ms: list[float] = []
    server_ms: list[float] = []
    for _ in range(n):
        t0 = time.perf_counter()
        r = client.post(f"{url}/predict", json=payload)
        client_ms.append((time.perf_counter() - t0) * 1000)
        if r.status_code != 200:
            raise SystemExit(f"측정 중 비정상 응답: {r.status_code}")
        if r.headers.get("X-Process-Time-Ms"):
            server_ms.append(float(r.headers["X-Process-Time-Ms"]))

    cs, ss = summarize(client_ms), summarize(server_ms) if server_ms else None
    return {
        "warmup_discarded": warmup,
        "sequential_requests": n,
        "batch_size": 1,
        "client_round_trip_ms": cs,
        "server_process_ms": ss,
        "network_and_overhead_p50_ms": (round(cs["p50"] - ss["p50"], 3) if ss else None),
        "how_to_read": ("client_round_trip_ms 에는 네트워크 왕복·TLS·Cloud Run 프런트엔드가 "
                        "섞여 있다. 서버 성능은 server_process_ms 로 읽는다"),
        "not_claimed": "처리량·동시 부하 성능이 아니다. 순차 요청의 측정이다",
    }


# --------------------------------------------------------------------------- #

def collect_usage(service: str, region: str, project: str,
                  since: datetime) -> dict:
    """사용량·과금. 둘 다 반영 지연이 있어 '미확인'으로 끝날 수 있다."""
    out: dict = {
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "measurement_window_start_utc": since.isoformat(),
        "delay_caveat": ("Cloud Monitoring 지표는 수 분, Cloud Billing 금액은 하루 이상 "
                         "지연된다. 이 실행 직후에 금액이 0 으로 보이는 것은 '과금이 "
                         "없다'는 뜻이 아니라 '아직 반영되지 않았다'는 뜻이다"),
    }
    try:
        rows = gcloud("run", "services", "describe", service, "--region", region,
                      "--format", "value(status.traffic[0].revisionName,"
                                  "status.observedGeneration)")
        out["service_revision"] = rows.strip()
    except SystemExit as exc:
        out["service_revision_error"] = str(exc)[:200]

    # 요청 수는 우리가 보낸 횟수로도 알 수 있지만, 서비스 쪽 집계를 시도한다.
    try:
        logs = gcloud("logging", "read",
                      f'resource.type="cloud_run_revision" '
                      f'resource.labels.service_name="{service}" '
                      f'httpRequest.requestMethod!=""',
                      "--limit", "1000", "--format", "value(httpRequest.status)",
                      timeout=300)
        codes = [c for c in logs.split() if c.isdigit()]
        out["request_log_sample"] = {
            "n_entries_read": len(codes),
            "status_counts": {c: codes.count(c) for c in sorted(set(codes))},
            "note": "최근 1000건만 읽었다. 전체 요청 수가 아니다",
        }
    except SystemExit as exc:
        out["request_log_error"] = str(exc)[:200]

    try:
        billing = gcloud("billing", "projects", "describe", project,
                         "--format", "value(billingEnabled,billingAccountName)")
        out["billing_enabled"] = billing.strip()
    except SystemExit as exc:
        out["billing_error"] = str(exc)[:200]

    out["cost_usd"] = None
    out["cost_status"] = ("이 실행에서는 확인할 수 없다. Cloud Billing 반영에 하루 이상 "
                          "걸린다. 금액을 0 이라고 적지 않는다")
    return out


def check_logs(service: str, region: str, secret_smiles: list[str]) -> dict:
    try:
        raw = gcloud("run", "services", "logs", "read", service, "--region", region,
                     "--limit", "300", timeout=300)
    except SystemExit as exc:
        return {"error": str(exc)[:300], "passed": None}

    lines = raw.splitlines()
    request_lines = [ln for ln in lines if re.search(r"(GET|POST) /\S+ -> \d{3}", ln)]
    timed = [ln for ln in request_lines if re.search(r"\d+\.\d+ms", ln)]
    leaked = [s for s in secret_smiles if s and s in raw]
    return {
        "total_log_lines": len(lines),
        "app_request_lines": len(request_lines),
        "app_request_lines_with_duration": len(timed),
        "sample": request_lines[-3:],
        "smiles_leaked_into_logs": leaked,
        "passed": bool(request_lines) and len(timed) == len(request_lines) and not leaked,
    }


# --------------------------------------------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="Cloud Run 서비스 URL")
    ap.add_argument("--service", default="egfr-pilot22-inference")
    ap.add_argument("--region", default="asia-northeast3")
    ap.add_argument("--project", default="project-eb5a476e-cdcf-4277-997")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--warmup", type=int, default=20)
    ap.add_argument("--requests", type=int, default=200)
    ap.add_argument("--prior-cold-start", type=Path, default=None,
                    help="앞선 실행에서 측정한 콜드 스타트 JSON. 있으면 함께 싣는다")
    args = ap.parse_args()

    if args.out.exists() and any(args.out.iterdir()):
        raise SystemExit(f"거부: 출력 폴더가 비어 있지 않다. 새 경로를 지정하라: {args.out}")

    cloud_cfg = json.loads(CLOUD_CONFIG.read_text(encoding="utf-8"))
    local_cfg = json.loads(LOCAL_CONFIG.read_text(encoding="utf-8"))
    probes = local_cfg["probe_molecules"]
    expected = local_cfg["served_model"]
    max_batch = int(local_cfg["api_contract"]["predict_request"]["max_batch"])
    latency_smiles = next(p["smiles"] for p in probes if p["id"] == "P-in-1")

    baseline = {r["id"]: r["host"] for r in
                json.loads(LOCAL_BASELINE.read_text(encoding="utf-8"))
                ["results"]["V1_parity"]["per_probe"]}

    started = datetime.now(timezone.utc)
    url = args.url.rstrip("/")
    token = identity_token()
    results: dict = {}

    with httpx.Client(timeout=TIMEOUT,
                      headers={"Authorization": f"Bearer {token}"}) as client:
        # --- C3: 콜드 스타트 (가장 먼저. 요청을 보내면 더 이상 콜드가 아니다) --- #
        print("C3 콜드 스타트...")
        t0 = time.perf_counter()
        first = client.get(f"{url}/readyz")
        first_ms = (time.perf_counter() - t0) * 1000
        first_body = first.json() if first.status_code in (200, 503) else {}
        print(f"  첫 요청 {first_ms:.0f}ms, readyz={first.status_code}, "
              f"모델 로딩 {first_body.get('load_seconds')}초")
        results["C3_cold_start"] = {
            "what": cloud_cfg["verification_plan"]["C3_cold_start"]["what"],
            "first_request_round_trip_ms": round(first_ms, 1),
            "readyz_status_code": first.status_code,
            "ready": first_body.get("ready"),
            "model_load_seconds": first_body.get("load_seconds"),
            "limitation": ("배포 직후 첫 요청 1회만 측정했다. 유휴 15분 뒤의 재콜드 "
                           "스타트는 측정하지 않았다. 반복 측정이 아니므로 분포를 "
                           "주장하지 않는다"),
        }
        if args.prior_cold_start and args.prior_cold_start.exists():
            # 첫 실행이 스크립트 버그로 중단됐을 때 얻은 콜드 스타트 값을 버리지 않는다.
            results["C3_cold_start"]["prior_measurement"] = json.loads(
                args.prior_cold_start.read_text(encoding="utf-8"))
        if first.status_code != 200:
            raise SystemExit(f"서비스가 준비되지 않았다: {first.status_code} {first.text[:300]}")

        # --- C2: 모델 동일성 ------------------------------------------------- #
        print("C2 모델 동일성...")
        info = client.get(f"{url}/model-info").json()
        m = info["model"]
        checks = {k: {"expected": expected[k], "actual": m.get(k),
                      "match": expected[k] == m.get(k)}
                  for k in ("model_sha256", "cohort_sha256", "settings_sha256")}
        c2_pass = all(c["match"] for c in checks.values())
        print(f"  해시 3개 일치={c2_pass}")
        results["C2_model_identity"] = {
            "what": cloud_cfg["verification_plan"]["C2_model_identity"]["what"],
            "passed": c2_pass, "hash_checks": checks,
            "n_training_molecules": m.get("n_training_molecules"),
            "n_training_scaffolds": m.get("n_training_scaffolds"),
            "training_label_range": m.get("training_label_range"),
            "runtime": info["runtime"],
            "config_sha256_in_image": info["config"]["sha256"],
            "mandatory_caveats": info["mandatory_caveats"],
            "refused_by_design": info["refused_by_design"],
        }

        # --- C1: 로컬과의 동일성 --------------------------------------------- #
        print("C1 로컬과 예측 동일성...")
        cloud_probes = run_probes(client, url, probes)
        rows = []
        for row in cloud_probes:
            b = baseline[row["id"]]
            identical = b == row["comparable"]
            rows.append({"id": row["id"], "note": row["note"], "identical": identical,
                         "local_host": b, "cloud_run": row["comparable"]})
            print(f"  {row['id']}: 동일={identical}")
        c1_pass = all(r["identical"] for r in rows)
        results["C1_parity"] = {
            "what": cloud_cfg["verification_plan"]["C1_parity_with_local"]["what"],
            "baseline": "reports/serving_m6_20261021/verification.json 의 V1 호스트 결과",
            "passed": c1_pass,
            "n_identical": sum(1 for r in rows if r["identical"]),
            "n_probes": len(rows),
            "per_probe": rows,
            "platform_note": ("로컬 기준값은 macOS arm64 호스트, Cloud Run 은 "
                              "linux/amd64 다. 플랫폼이 다르다"),
        }

        # --- C4: 오류 처리 ---------------------------------------------------- #
        print("C4 오류 처리...")
        cases = run_error_cases(client, url, max_batch)
        n_pass = sum(1 for c in cases if c["passed"])
        print(f"  {n_pass}/{len(cases)} 통과")
        results["C4_error_handling"] = {
            "what": cloud_cfg["verification_plan"]["C4_error_handling"]["what"],
            "passed": n_pass == len(cases),
            "n_passed": n_pass, "n_cases": len(cases),
            "failed": [c["case"] for c in cases if not c["passed"]],
            "cases": cases,
        }

        # --- C5: 지연시간 ----------------------------------------------------- #
        print(f"C5 지연시간 (워밍업 {args.warmup} + 측정 {args.requests})...")
        c5 = measure_latency(client, url, latency_smiles, args.warmup, args.requests)
        print(f"  왕복 p50 {c5['client_round_trip_ms']['p50']}ms / "
              f"서버 처리 p50 {c5['server_process_ms']['p50']}ms")
        results["C5_latency"] = {
            "what": cloud_cfg["verification_plan"]["C5_latency"]["what"],
            "measured_from": "한국(로컬 노트북)에서 asia-northeast3 리전으로",
            **c5,
        }

    # --- C7: 로그 ------------------------------------------------------------ #
    print("C7 로그...")
    c7 = check_logs(args.service, args.region, [p["smiles"] for p in probes])
    print(f"  앱 요청 로그 {c7.get('app_request_lines')}줄, "
          f"SMILES 유출 {len(c7.get('smiles_leaked_into_logs') or [])}건")
    results["C7_logs"] = {"what": cloud_cfg["verification_plan"]["C7_logs"]["what"], **c7}

    # --- C6: 사용량 ---------------------------------------------------------- #
    print("C6 사용량·과금...")
    results["C6_usage_and_cost"] = {
        "what": cloud_cfg["verification_plan"]["C6_usage_and_cost"]["what"],
        "requests_sent_by_this_script": {
            "probes": len(probes) * 2,
            "error_cases": 11,
            "latency": args.warmup + args.requests,
            "note": "스크립트가 보낸 횟수다. 서비스 쪽 집계와 다를 수 있다",
        },
        **collect_usage(args.service, args.region, args.project, started),
    }

    # --- 사전 예상과 대조 ----------------------------------------------------- #
    pre = cloud_cfg["pre_registered_expectations"]
    srv = results["C5_latency"]["server_process_ms"]["p50"]
    rtt = results["C5_latency"]["client_round_trip_ms"]["p50"]
    cold = results["C3_cold_start"]["first_request_round_trip_ms"] / 1000.0
    load = results["C3_cold_start"]["model_load_seconds"]
    missed = []
    if not (10.0 <= srv <= 40.0):
        missed.append(f"서버 처리 p50 예상 10~40ms, 실제 {srv}ms")
    if not (30.0 <= rtt <= 150.0):
        missed.append(f"왕복 p50 예상 30~150ms, 실제 {rtt}ms")
    if not (2.0 <= cold <= 15.0):
        missed.append(f"콜드 스타트 첫 요청 예상 2~15초, 실제 {cold:.2f}초")
    if load is not None and not (0.5 <= float(load) <= 3.0):
        missed.append(f"클라우드 모델 로딩 예상 0.5~3초, 실제 {load}초")
    if not results["C1_parity"]["passed"]:
        missed.append("로컬과 예측 일치를 예상했으나 불일치")

    results["pre_registration_vs_actual"] = {
        "declared_before_measurement": pre,
        "actual": {"server_process_p50_ms": srv, "client_round_trip_p50_ms": rtt,
                   "cold_start_first_request_seconds": round(cold, 2),
                   "model_load_seconds": load,
                   "parity": "일치" if results["C1_parity"]["passed"] else "불일치"},
        "expectations_not_met": missed,
    }

    checked = ["C1_parity", "C2_model_identity", "C4_error_handling", "C7_logs"]
    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "milestone": "M6",
        "stage": "cloud_execution",
        "provider": "Google Cloud Run",
        "region": args.region,
        "project": args.project,
        "service": args.service,
        "service_url": url,
        "config_path": str(CLOUD_CONFIG.relative_to(ROOT)),
        "config_sha256": sha256(CLOUD_CONFIG),
        "authentication": "require_authentication (gcloud ID 토큰으로 호출)",
        "token_handling": "토큰은 메모리에만 두고 이 파일에 싣지 않는다",
        "local_environment": {"python": platform.python_version(),
                              "platform": platform.platform()},
        "verdicts": {k: results[k].get("passed") for k in checked},
        "all_checked_passed": all(results[k].get("passed") for k in checked),
        "not_scored": {
            "C3_cold_start": "1회 측정이라 채점하지 않는다",
            "C5_latency": "합격선을 사전에 정하지 않아 채점하지 않는다",
            "C6_usage_and_cost": "과금 반영 지연으로 금액을 확인할 수 없다",
        },
        "results": results,
    }

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "cloud_verification.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n판정:", json.dumps(summary["verdicts"], ensure_ascii=False))
    print("전체 통과:", summary["all_checked_passed"])
    if missed:
        print("사전 예상과 다른 항목:")
        for item in missed:
            print("  -", item)
    else:
        print("사전 예상 범위를 벗어난 항목 없음")
    print("저장:", args.out / "cloud_verification.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
