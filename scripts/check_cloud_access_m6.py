"""M6 — 클라우드 배포 가능성 점검.

**자원을 만들지 않는다.** 읽기 전용 호출과 권한 시뮬레이션만 한다.
배포를 시도해 보고 중간에 실패하면 어디까지 만들어졌는지 추적하기 어렵고
남은 자원이 과금된다. 그래서 먼저 가능 여부를 확인한다.

M4 에서 쓴 순서와 같다: 접근 가능한지 먼저 확인하고, 안 되면 안 되는 증거를
남긴다. 되는 척하지 않는다.

사용:
  .venv-serve/bin/python scripts/check_cloud_access_m6.py \
      --profile skn33 --region ap-northeast-2 \
      --out reports/serving_m6_20261021
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 배포에 실제로 필요한 동작. 하나라도 막히면 그 단계에서 멈춘다.
NEEDED_ACTIONS = [
    ("ecr:CreateRepository", "ECR 리포지터리 생성"),
    ("ecr:DescribeRepositories", "ECR 리포지터리 조회"),
    ("ecr:GetAuthorizationToken", "docker push 인증"),
    ("ecr:InitiateLayerUpload", "이미지 레이어 업로드"),
    ("ecr:PutImage", "이미지 등록"),
    ("ecr:BatchDeleteImage", "정리: 이미지 삭제"),
    ("ecs:CreateCluster", "ECS 클러스터 생성"),
    ("ecs:RegisterTaskDefinition", "task definition 등록"),
    ("ecs:RunTask", "task 실행"),
    ("ecs:DescribeTasks", "task 상태 조회"),
    ("ecs:StopTask", "정리: task 중지"),
    ("ecs:DeleteCluster", "정리: 클러스터 삭제"),
    ("iam:PassRole", "task execution role 전달 (Fargate 필수)"),
    ("iam:GetRole", "역할 존재 확인"),
    ("logs:CreateLogGroup", "CloudWatch 로그 그룹 생성"),
    ("logs:PutRetentionPolicy", "로그 보존 기간 설정 (비용 통제)"),
    ("logs:GetLogEvents", "컨테이너 로그 수집"),
    ("logs:DeleteLogGroup", "정리: 로그 그룹 삭제"),
    ("ec2:DescribeVpcs", "기본 VPC 확인"),
    ("ec2:DescribeSubnets", "공용 서브넷 확인"),
    ("ec2:CreateSecurityGroup", "보안 그룹 생성"),
    ("ec2:AuthorizeSecurityGroupIngress", "8000 포트 허용"),
    ("ec2:DeleteSecurityGroup", "정리: 보안 그룹 삭제"),
]


def aws(args: list[str], profile: str, region: str, timeout: int = 90) -> dict:
    """AWS CLI 호출. 실패를 예외로 올리지 않고 결과로 돌려준다."""
    cmd = ["aws", *args, "--profile", profile, "--region", region, "--output", "json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "command": " ".join(args[:2])}
    if proc.returncode != 0:
        # 오류 문자열에 계정 ID 외 자격증명이 담기지 않도록 길이를 제한한다.
        return {"ok": False, "returncode": proc.returncode,
                "stderr": proc.stderr.strip()[:600], "command": " ".join(args[:2])}
    try:
        return {"ok": True, "data": json.loads(proc.stdout) if proc.stdout.strip() else {}}
    except json.JSONDecodeError:
        return {"ok": True, "data": {"_raw": proc.stdout[:400]}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="skn33")
    ap.add_argument("--region", default="ap-northeast-2")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    checks: dict = {}

    print("1) 자격증명 확인")
    ident = aws(["sts", "get-caller-identity"], args.profile, args.region)
    checks["caller_identity"] = ident
    if not ident["ok"]:
        print("   실패:", ident.get("stderr", ident.get("error"))[:200])
        summary = {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "milestone": "M6",
            "profile": args.profile,
            "region": args.region,
            "verdict": "blocked_no_credentials",
            "what_this_means": (
                "자격증명이 없어 클라우드 배포를 시작할 수 없다. "
                "`aws login --profile <프로필>` 로 로그인한 뒤 다시 실행한다"),
            "checks": checks,
        }
        args.out.mkdir(parents=True, exist_ok=True)
        path = args.out / "cloud_access_check.json"
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
        print("저장:", path)
        return 2

    arn = ident["data"].get("Arn", "")
    account = ident["data"].get("Account", "")
    print(f"   {arn}")

    print("2) 권한 시뮬레이션 (iam:SimulatePrincipalPolicy)")
    actions = [a for a, _ in NEEDED_ACTIONS]
    sim = aws(["iam", "simulate-principal-policy",
               "--policy-source-arn", arn,
               "--action-names", *actions], args.profile, args.region, timeout=180)
    checks["simulate_principal_policy"] = {"ok": sim["ok"]}
    allowed: dict[str, str] = {}
    if sim["ok"]:
        for r in sim["data"].get("EvaluationResults", []):
            allowed[r["EvalActionName"]] = r["EvalDecision"]
        checks["simulate_principal_policy"]["decisions"] = allowed
        n_allow = sum(1 for v in allowed.values() if v == "allowed")
        print(f"   {n_allow}/{len(actions)} 허용")
    else:
        checks["simulate_principal_policy"]["note"] = (
            "시뮬레이션 자체가 막혔다(iam:SimulatePrincipalPolicy 권한 없음). "
            "개별 읽기 호출로 대체 판단한다")
        checks["simulate_principal_policy"]["stderr"] = sim.get("stderr")
        print("   막힘 — 개별 읽기 호출로 대체")

    print("3) 개별 읽기 호출")
    probes = {
        "ecr_describe_repositories": ["ecr", "describe-repositories", "--max-items", "1"],
        "ecr_get_authorization_token": ["ecr", "get-authorization-token"],
        "ecs_list_clusters": ["ecs", "list-clusters"],
        "logs_describe_log_groups": ["logs", "describe-log-groups", "--limit", "1"],
        "ec2_describe_vpcs": ["ec2", "describe-vpcs", "--filters", "Name=isDefault,Values=true"],
        "iam_get_ecs_task_execution_role": ["iam", "get-role", "--role-name",
                                            "ecsTaskExecutionRole"],
    }
    read_results = {}
    for name, cmd in probes.items():
        res = aws(cmd, args.profile, args.region)
        # 토큰 자체는 저장하지 않는다. 성공 여부만 남긴다.
        if name == "ecr_get_authorization_token" and res["ok"]:
            res = {"ok": True, "data": {"_token_received": True}}
        read_results[name] = res
        mark = "가능" if res["ok"] else "막힘"
        print(f"   {name:36s} {mark}")
        if not res["ok"]:
            read_results[name]["stderr_head"] = (res.get("stderr") or "")[:200]
    checks["read_probes"] = read_results

    # 공용 서브넷 확인 (VPC 조회가 됐을 때만)
    if read_results["ec2_describe_vpcs"]["ok"]:
        vpcs = read_results["ec2_describe_vpcs"]["data"].get("Vpcs", [])
        if vpcs:
            vpc_id = vpcs[0]["VpcId"]
            subs = aws(["ec2", "describe-subnets", "--filters",
                        f"Name=vpc-id,Values={vpc_id}"], args.profile, args.region)
            if subs["ok"]:
                rows = [{"SubnetId": s["SubnetId"], "AvailabilityZone": s["AvailabilityZone"],
                         "MapPublicIpOnLaunch": s.get("MapPublicIpOnLaunch")}
                        for s in subs["data"].get("Subnets", [])]
                checks["default_vpc"] = {"vpc_id": vpc_id, "subnets": rows,
                                         "n_public_on_launch": sum(
                                             1 for r in rows if r["MapPublicIpOnLaunch"])}
                print(f"   기본 VPC {vpc_id}: 서브넷 {len(rows)}개")

    # --- 판정 ----------------------------------------------------------- #
    blocking: list[str] = []
    if allowed:
        for action, why in NEEDED_ACTIONS:
            if allowed.get(action) != "allowed":
                blocking.append(f"{action} ({why}) → {allowed.get(action, '판정 없음')}")
    else:
        for name, res in read_results.items():
            if not res["ok"]:
                blocking.append(f"{name} 호출 실패")

    if not blocking:
        verdict = "ready"
        meaning = "배포에 필요한 동작이 모두 허용된다. 사용자 승인 후 배포를 실행할 수 있다"
    elif len(blocking) >= len(NEEDED_ACTIONS) * 0.5 and allowed:
        verdict = "blocked_insufficient_permissions"
        meaning = ("권한이 부족해 배포할 수 없다. 이 계정으로는 M6 의 클라우드 항목을 "
                   "충족할 수 없고, 권한을 받거나 다른 계정이 필요하다")
    else:
        verdict = "partially_blocked"
        meaning = ("일부 동작이 막혀 있다. 막힌 항목을 우회하지 않고 그대로 보고한다. "
                   "우회 설계가 가능한지는 따로 판단한다")

    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "milestone": "M6",
        "kind": "read_only_access_check",
        "created_no_resources": True,
        "profile": args.profile,
        "region": args.region,
        "account": account,
        "principal_arn": arn,
        "verdict": verdict,
        "what_this_means": meaning,
        "blocking": blocking,
        "n_blocking": len(blocking),
        "needed_actions": [{"action": a, "why": w} for a, w in NEEDED_ACTIONS],
        "checks": checks,
        "note_on_simulation": (
            "simulate-principal-policy 는 정책 평가 결과이고 실제 호출 성공을 보장하지 않는다. "
            "SCP·권한 경계·리소스 정책 때문에 허용으로 보여도 실패할 수 있다"),
    }

    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "cloud_access_check.json"
    if path.exists():
        raise SystemExit(f"거부: 이미 있는 파일을 덮어쓰지 않는다: {path}")
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n판정: {verdict}")
    print(meaning)
    if blocking:
        print(f"막힌 항목 {len(blocking)}개:")
        for b in blocking[:12]:
            print("  -", b)
        if len(blocking) > 12:
            print(f"  ... 외 {len(blocking) - 12}개")
    print("저장:", path)
    return 0 if verdict == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
