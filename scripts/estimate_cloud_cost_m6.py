"""M6 — 클라우드 실행 비용 사전 추정.

요율을 손으로 적지 않는다. AWS 공개 가격 API(인증 불필요)에서 받아
응답을 해시와 함께 보존하고 그 값으로 계산한다. 블로그·요약글의 수치를
쓰지 않는 이유는 리전과 시점이 어긋나기 쉽기 때문이다.

이것은 **추정**이다. 실제 비용은 실행 후 Cost Explorer 로만 확인된다.

사용:
  .venv-serve/bin/python scripts/estimate_cloud_cost_m6.py \
      --region ap-northeast-2 --out reports/serving_m6_20261021
"""
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws"

# 받아올 요율. (서비스코드, usagetype 접두, 설명)
# 접두는 리전 코드에 따라 바뀌므로 호출 시 조립한다.
WANTED = [
    # vCPU 요율의 usagetype 에는 ':perCPU' 접미가 붙는다. 접두만 맞추면
    # x86 요율까지 걸리므로 정확한 문자열을 쓴다.
    ("AmazonECS", "Fargate-ARM-vCPU-Hours:perCPU", "Fargate ARM vCPU", "vCPU-hour"),
    ("AmazonECS", "Fargate-ARM-GB-Hours", "Fargate ARM 메모리", "GB-hour"),
    ("AmazonECR", "TimedStorage-ByteHrs", "ECR 이미지 저장", "GB-month"),
    ("AmazonCloudWatch", "DataProcessing-Bytes", "CloudWatch Logs 수집", "GB"),
    ("AmazonCloudWatch", "TimedStorage-ByteHrs", "CloudWatch Logs 저장", "GB-month"),
    ("AmazonVPC", "PublicIPv4:InUseAddress", "공용 IPv4 주소", "hour"),
]

REGION_PREFIX = {"ap-northeast-2": "APN2"}

HOURS_PER_MONTH = 730.0


def fetch(service: str, region: str) -> dict:
    url = f"{BASE}/{service}/current/{region}/index.json"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read()
    return {"url": url, "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw), "payload": json.loads(raw.decode("utf-8"))}


def find_rate(doc: dict, usagetype: str) -> dict | None:
    """usagetype 이 정확히 일치하는 온디맨드 요율을 찾는다.

    여러 개가 나오면(예: Archive 계층) 가장 비싼 값을 쓴다. 추정에서
    낮은 쪽을 고르면 비용을 낮게 보고하게 된다.
    """
    d = doc["payload"]
    found = []
    for sku, product in d["products"].items():
        if product.get("attributes", {}).get("usagetype") != usagetype:
            continue
        for offer in d["terms"].get("OnDemand", {}).get(sku, {}).values():
            for dim in offer["priceDimensions"].values():
                found.append({
                    "sku": sku,
                    "usd": float(dim["pricePerUnit"]["USD"]),
                    "unit": dim["unit"],
                    "description": dim.get("description", ""),
                })
    if not found:
        return None
    found.sort(key=lambda x: x["usd"], reverse=True)
    out = dict(found[0])
    out["n_matching_dimensions"] = len(found)
    out["publication_date"] = d.get("publicationDate")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="ap-northeast-2")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--vcpu", type=float, default=0.25, help="task vCPU")
    ap.add_argument("--memory-gb", type=float, default=0.5, help="task 메모리 GB")
    ap.add_argument("--image-gb", type=float, default=0.81,
                    help="ECR 에 올릴 이미지 크기 GB (829MB = 0.81GiB)")
    ap.add_argument("--log-gb", type=float, default=0.001,
                    help="검증 1회에 쌓일 로그 GB 추정")
    args = ap.parse_args()

    prefix = REGION_PREFIX.get(args.region)
    if not prefix:
        raise SystemExit(f"이 리전의 usagetype 접두를 모른다: {args.region}")

    docs: dict[str, dict] = {}
    rates: dict[str, dict] = {}
    sources = []
    for service, suffix, label, unit in WANTED:
        if service not in docs:
            docs[service] = fetch(service, args.region)
            sources.append({
                "service": service,
                "url": docs[service]["url"],
                "sha256": docs[service]["sha256"],
                "bytes": docs[service]["bytes"],
                "publication_date": docs[service]["payload"].get("publicationDate"),
            })
        usagetype = f"{prefix}-{suffix}"
        rate = find_rate(docs[service], usagetype)
        if rate is None:
            raise SystemExit(f"요율을 찾지 못했다: {service} {usagetype}")
        rates[label] = {"usagetype": usagetype, "billing_unit": unit, **rate}
        print(f"{label:24s} {rate['usd']:.10f} USD / {rate['unit']}")

    r = {k: rates[k]["usd"] for k in rates}
    fargate_hour = args.vcpu * r["Fargate ARM vCPU"] + args.memory_gb * r["Fargate ARM 메모리"]
    ip_hour = r["공용 IPv4 주소"]
    ecr_hour = args.image_gb * r["ECR 이미지 저장"] / HOURS_PER_MONTH
    per_hour = fargate_hour + ip_hour + ecr_hour

    log_ingest_once = args.log_gb * r["CloudWatch Logs 수집"]
    log_store_hour = args.log_gb * r["CloudWatch Logs 저장"] / HOURS_PER_MONTH

    def scenario(name: str, hours: float, note: str) -> dict:
        total = per_hour * hours + log_ingest_once + log_store_hour * hours
        return {
            "name": name,
            "hours": hours,
            "note": note,
            "fargate_usd": round(fargate_hour * hours, 6),
            "public_ipv4_usd": round(ip_hour * hours, 6),
            "ecr_storage_usd": round(ecr_hour * hours, 6),
            "cloudwatch_usd": round(log_ingest_once + log_store_hour * hours, 6),
            "total_usd": round(total, 4),
        }

    scenarios = [
        scenario("검증 1회", 1.0,
                 "배포·확인·측정·정리를 1시간 안에 끝내는 경우. M6 에 필요한 최소 실행"),
        scenario("하루 운용", 24.0, "하루 켜 두는 경우"),
        scenario("한 달 상시", HOURS_PER_MONTH, "상시 운용. 이 프로젝트 범위에서는 필요 없다"),
    ]

    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "milestone": "M6",
        "kind": "pre_execution_estimate",
        "this_is_an_estimate": (
            "추정이다. 실제 과금은 실행 후 Cost Explorer·청구서로만 확인된다. "
            "이 숫자를 '실제 비용'으로 쓰지 않는다"),
        "region": args.region,
        "task_size": {"vcpu": args.vcpu, "memory_gb": args.memory_gb,
                      "architecture": "ARM64 (Graviton)",
                      "why": "추론 1건이 10ms 수준이라 최소 구성으로 충분하다. "
                             "ARM 을 쓰는 이유는 로컬 빌드가 arm64 이고 요율도 x86 보다 낮다"},
        "image_gb": args.image_gb,
        "rates": rates,
        "rate_sources": sources,
        "derived_hourly_usd": {
            "fargate": round(fargate_hour, 8),
            "public_ipv4": round(ip_hour, 8),
            "ecr_storage": round(ecr_hour, 8),
            "total": round(per_hour, 8),
        },
        "scenarios": scenarios,
        "excluded_from_estimate": [
            "인터넷 아웃바운드 전송 — 응답이 수 KB 라 무료 구간 안이라고 보고 뺐다. 빼고 계산했다는 사실을 밝힌다",
            "NAT Gateway — 쓰지 않는 설계다(공용 서브넷 + 공용 IPv4). 쓰면 시간당 요금이 따로 붙는다",
            "로드 밸런서 — 단일 task 에 공용 IP 로 직접 접근하므로 쓰지 않는다",
            "ECR 이미지 스캔(Inspector)·KMS — 기본 설정에서 쓰지 않는다",
            "프리 티어 — 계정이 프리 티어 대상이면 실제 청구는 이보다 낮을 수 있다",
        ],
        "cost_control_rules": [
            "task 를 측정 직후 중지한다. desiredCount 0 또는 task 종료",
            "공용 IPv4 는 task 와 함께 사라진다. Elastic IP 를 따로 만들지 않는다",
            "ECR 이미지는 측정 후 삭제하거나 저장 비용을 감안해 남긴다(0.81GB 당 월 $0.081)",
            "CloudWatch 로그 그룹에 보존 기간을 설정한다. 무기한 보존은 저장 비용이 쌓인다",
        ],
    }

    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "cloud_cost_estimate.json"
    if path.exists():
        raise SystemExit(f"거부: 이미 있는 파일을 덮어쓰지 않는다: {path}")
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n시간당 합계: ${per_hour:.6f} USD")
    for s in scenarios:
        print(f"  {s['name']:10s} {s['hours']:6.0f}h  ${s['total_usd']:.4f}")
    print("저장:", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
