"""M5 — Agent 평가 하네스.

configs/agent_eval.json 의 질문 집합을 돌려 5개 축으로 채점하고,
호출 trace 와 모델·prompt·출처 버전을 남긴다.

개발(dev)과 최종(final) 질문은 따로 돌린다. 최종은 한 번만 돌리고 결과를 그대로 싣는다.

사용:
  .venv-ml/bin/python scripts/run_agent_eval.py --split dev \
      --config configs/agent_eval.json \
      --predictor artifacts/agent_predictor_20261021 \
      --out reports/agent_eval_20261021_dev
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from egfr_lab.agent import tools as tools_mod                      # noqa: E402
from egfr_lab.agent.policy import AnthropicPolicy, OpenAIPolicy, RulePolicy   # noqa: E402
from egfr_lab.agent.runner import AgentRunner                      # noqa: E402
from egfr_lab.agent.trace import environment_record                # noqa: E402

# 채점도 실행기와 같은 규칙을 써야 한다. 식별자 속 숫자(IC50, C797S)를 측정값으로 세지 않는다.
NUMBER = re.compile(r"(?<![A-Za-z])(?<![0-9.])\d+(?:\.\d+)?(?![0-9.])(?![A-Za-z])")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score(question: dict, trace: dict) -> dict:
    """5개 축을 통과/실패로만 채점한다. 부분 점수를 주지 않는다."""
    used = trace["tools_used"]
    answer = trace.get("answer") or {}
    caveats = " ".join(answer.get("caveats") or [])
    claims = answer.get("claims") or []

    expected = question.get("expected_tools", [])
    forbidden = question.get("forbidden_tools", [])
    tool_ok = all(t in used for t in expected) and not any(t in used for t in forbidden)

    # 수치를 담은 주장마다 출처가 있어야 한다. 주장이 없으면 해당 없음으로 통과.
    numeric_claims = [c for c in claims if NUMBER.search(c.get("text", ""))]
    citation_ok = all(c.get("source_ids") for c in numeric_claims)

    # 정당한 행동이 둘인 질문은 양쪽을 허용한다(질문별로 명시한 경우에만).
    if question.get("insufficient_either_ok"):
        insufficient_ok = True
    else:
        insufficient_ok = bool(answer.get("insufficient_information")) == bool(
            question.get("must_be_insufficient"))

    # 오류·미발견이 있었다면 수치 주장을 만들지 않았어야 한다.
    had_failure = any(c["status"] in ("error", "not_found") for c in trace["calls"])
    error_ok = (not had_failure) or (not numeric_claims) or bool(
        answer.get("insufficient_information")) or citation_ok

    termination_ok = (trace["n_calls"] <= question.get("max_calls", 6)
                      and trace["stop_reason"] in
                      ("answered", "retry_limit", "budget_exhausted"))

    # 필수 고지 문구가 답변의 caveat 에 들어 있는가
    required = question.get("required_caveat_keywords", [])
    missing = [k for k in required if k not in caveats]
    caveat_ok = not missing

    axes = {
        "tool_selection": tool_ok,
        "citation": citation_ok,
        "insufficient_information": insufficient_ok,
        "error_handling": error_ok,
        "termination": termination_ok,
        "required_caveats": caveat_ok,
    }
    return {
        "question_id": question["id"],
        "probes": question.get("probes", ""),
        "tools_used": used,
        "n_calls": trace["n_calls"],
        "stop_reason": trace["stop_reason"],
        "insufficient": bool(answer.get("insufficient_information")),
        "n_claims": len(claims),
        "n_numeric_claims": len(numeric_claims),
        "missing_caveats": missing,
        "axes": axes,
        "all_passed": all(axes.values()),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "final"], required=True)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--predictor", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--policy", choices=["rule", "openai", "anthropic"], default="rule")
    ap.add_argument("--model", default=None, help="LLM 정책의 모델 이름")
    args = ap.parse_args()

    if args.out.exists() and any(args.out.iterdir()):
        raise SystemExit(f"거부: 출력 폴더가 비어 있지 않다. 새 경로를 지정하라: {args.out}")

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    questions = cfg[f"{args.split}_questions"]

    # LLM 정책은 키가 없으면 여기서 실패한다. 규칙 기반으로 조용히 대체하지 않는다.
    if args.policy == "openai":
        policy = OpenAIPolicy(max_tool_calls=int(cfg["budget"]["max_tool_calls"]),
                              **({"model": args.model} if args.model else {}))
    elif args.policy == "anthropic":
        policy = AnthropicPolicy(**({"model": args.model} if args.model else {}))
    else:
        policy = RulePolicy()
    is_llm = args.policy != "rule"

    predictor = tools_mod.ActivityPredictor(args.predictor)
    tool_map = {
        "predict_activity": lambda smiles: predictor(smiles),
        "lookup_measurements": tools_mod.lookup_measurements,
        "search_literature": tools_mod.search_literature,
        "fetch_evidence": tools_mod.fetch_evidence,
    }
    runner = AgentRunner(tool_map, cfg["budget"], Path(tools_mod.__file__))

    traces, scores = [], []
    for q in questions:
        trace = runner.run(q["id"], q["question"], policy).to_dict()
        traces.append(trace)
        s = score(q, trace)
        scores.append(s)
        mark = "통과" if s["all_passed"] else "실패"
        failed = [k for k, v in s["axes"].items() if not v]
        print(f"  {q['id']}: {mark}  호출 {s['n_calls']}회 {s['tools_used']} "
              f"종료={s['stop_reason']}" + (f"  미통과축={failed}" if failed else ""))

    axes_names = list(scores[0]["axes"]) if scores else []
    per_axis = {a: sum(1 for s in scores if s["axes"][a]) for a in axes_names}

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "traces.json").write_text(
        json.dumps(traces, ensure_ascii=False, indent=1), encoding="utf-8")

    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "milestone": "M5",
        "split": args.split,
        "policy": {"name": policy.name, "version": policy.version,
                   "model": policy.model, "prompt_version": policy.prompt_version},
        "policy_is_llm": is_llm,
        "temperature_dropped_by_api": bool(getattr(policy, "temperature_dropped", False)),
        "temperature_note": ("일부 모델은 temperature 지정을 거부해 기본값(1)만 쓴다. "
                             "API 가 거부하면 인자를 빼고 재요청하며 그 사실을 여기 기록한다"),
        "policy_note": (f"LLM 정책({args.policy}, model={policy.model})" if is_llm else
                        "LLM 정책이 아니다. 규칙 기반 결정적 정책의 결과이며 "
                        "'LLM Agent 를 평가했다'고 서술하지 않는다"),
        "config_sha256": sha256(args.config),
        "budget": cfg["budget"],
        "environment": environment_record(
            Path(tools_mod.__file__), args.predictor / "manifest.json"),
        "n_questions": len(scores),
        "n_all_passed": sum(1 for s in scores if s["all_passed"]),
        "per_axis_passed": per_axis,
        "per_question": scores,
        "forbidden": cfg["forbidden"],
    }
    (args.out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n전체 통과: {summary['n_all_passed']}/{summary['n_questions']}")
    print("축별 통과:", ", ".join(f"{k} {v}/{len(scores)}" for k, v in per_axis.items()))
    print("저장:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
