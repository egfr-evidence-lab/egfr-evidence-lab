"""Agent 정책 인터페이스와 실행기.

정책(policy)은 '다음에 무엇을 할지' 결정하는 부분이고, 실행기(runner)는
예산·종료·오류 처리를 강제하는 부분이다. 둘을 나눈 이유는 LLM 키가 없는 지금
규칙 기반 정책으로 하네스를 검증해 두고, 키가 생기면 **같은 인터페이스로**
LLM 정책을 끼우기 위해서다.

실행기가 강제하는 것(configs/project.json 의 agent 사양):
  * max_tool_calls: 예산을 넘기면 답변을 만들지 않고 budget_exhausted 로 끝낸다
  * max_search_retries: 같은 도구의 재시도 횟수 제한
  * require_source_ids: 수치를 담은 주장에 출처가 없으면 답변을 거절한다
  * llm_may_invent_measurements=false: 도구가 돌려주지 않은 수치를 답변에 넣지 못한다

마지막 두 개가 핵심이다. 정책이 무엇을 하든 실행기가 **출처 없는 수치를 막는다**.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from .tools import ToolResult
from .trace import RunTrace

# 측정값으로 볼 수 있는 '독립된' 수만 뽑는다.
# IC50·pIC50·C797S·CHEMBL4278815 처럼 글자에 붙은 숫자는 식별자의 일부이지 측정값이 아니다.
# 이것을 구분하지 않으면 'IC50 는 22.4 nM 이다' 의 50 까지 날조 수치로 보고
# 정당한 답변을 막는다(거짓 양성). tests/test_agent_runner.py 가 이 경우를 지킨다.
NUMBER = re.compile(r"(?<![A-Za-z])(?<![0-9.])\d+(?:\.\d+)?(?![0-9.])(?![A-Za-z])")


@dataclass
class Action:
    """정책이 내리는 결정. 도구를 부르거나(call) 끝낸다(finish)."""

    kind: str                         # "call" | "finish"
    tool: str | None = None
    arguments: dict = field(default_factory=dict)
    answer: dict | None = None        # kind=="finish" 일 때


@dataclass
class Answer:
    text: str
    claims: list[dict] = field(default_factory=list)   # [{"text":..., "source_ids":[...]}]
    caveats: list[str] = field(default_factory=list)
    insufficient_information: bool = False

    def to_dict(self) -> dict:
        return {"text": self.text, "claims": self.claims, "caveats": self.caveats,
                "insufficient_information": self.insufficient_information}


class Policy(Protocol):
    name: str
    version: str
    model: str | None
    prompt_version: str | None

    def decide(self, question: str, observations: list[dict]) -> Action: ...


class AgentRunner:
    def __init__(self, tools: dict[str, Callable[..., ToolResult]], budget: dict,
                 tools_module: Path):
        self.tools = tools
        self.max_tool_calls = int(budget.get("max_tool_calls", 6))
        self.max_search_retries = int(budget.get("max_search_retries", 2))
        self.require_source_ids = bool(budget.get("require_source_ids", True))
        self.allow_invented = bool(budget.get("llm_may_invent_measurements", False))
        self.tools_module = tools_module

    # -- 출처 검증 ---------------------------------------------------------- #

    def _numbers_from_observations(self, observations: list[dict]) -> set[str]:
        """도구가 실제로 돌려준 수치 문자열 집합. 답변의 수치를 이 안에서만 허용한다."""
        seen: set[str] = set()

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                for v in node.values():
                    walk(v)
            elif isinstance(node, (list, tuple)):
                for v in node:
                    walk(v)
            elif isinstance(node, (int, float)) and not isinstance(node, bool):
                seen.add(f"{float(node):g}")
            elif isinstance(node, str):
                for m in NUMBER.findall(node):
                    seen.add(f"{float(m):g}")

        for obs in observations:
            walk(obs.get("data"))
            walk(obs.get("message"))
            walk(obs.get("caveats"))
        return seen

    def _validate_answer(self, answer: Answer, observations: list[dict]) -> tuple[bool, str]:
        if answer.insufficient_information:
            return True, ""                     # 모른다고 답하는 데는 출처가 필요 없다

        allowed = self._numbers_from_observations(observations)
        for claim in answer.claims:
            text = claim.get("text", "")
            numbers = {f"{float(m):g}" for m in NUMBER.findall(text)}
            if self.require_source_ids and numbers and not claim.get("source_ids"):
                return False, f"출처 없는 수치 주장: {text!r}"
            if not self.allow_invented:
                invented = numbers - allowed
                if invented:
                    return False, f"도구가 돌려주지 않은 수치: {sorted(invented)} in {text!r}"
        return True, ""

    # -- 실행 -------------------------------------------------------------- #

    def run(self, question_id: str, question: str, policy: Policy) -> RunTrace:
        trace = RunTrace(
            question_id=question_id, question=question,
            policy_name=policy.name, policy_version=policy.version,
            model=policy.model, prompt_version=policy.prompt_version,
            budget={"max_tool_calls": self.max_tool_calls,
                    "max_search_retries": self.max_search_retries,
                    "require_source_ids": self.require_source_ids,
                    "llm_may_invent_measurements": self.allow_invented},
        )
        observations: list[dict] = []
        retries: dict[str, int] = {}

        while True:
            if len(trace.calls) >= self.max_tool_calls:
                trace.stop_reason = "budget_exhausted"
                trace.answer = Answer(
                    text="도구 호출 예산을 모두 썼고 근거를 충분히 모으지 못했다.",
                    insufficient_information=True,
                    caveats=[f"도구 호출 {self.max_tool_calls}회 한도에 도달했다"],
                ).to_dict()
                return trace

            try:
                action = policy.decide(question, observations)
            except Exception as exc:                          # noqa: BLE001
                trace.stop_reason = "policy_error"
                trace.answer = Answer(
                    text=f"정책이 결정에 실패했다: {type(exc).__name__}: {exc}",
                    insufficient_information=True).to_dict()
                return trace

            if action.kind == "finish":
                answer = action.answer or Answer(text="", insufficient_information=True)
                if isinstance(answer, dict):
                    answer = Answer(**answer)
                ok, why = self._validate_answer(answer, observations)
                if not ok:
                    trace.stop_reason = "answer_rejected_unsourced"
                    trace.answer = Answer(
                        text=f"답변이 출처 검증을 통과하지 못해 반려됐다: {why}",
                        insufficient_information=True,
                        caveats=["실행기가 출처 없는 수치를 막았다"]).to_dict()
                    return trace
                trace.stop_reason = "answered"
                trace.answer = answer.to_dict()
                return trace

            tool = self.tools.get(action.tool or "")
            if tool is None:
                trace.stop_reason = "unknown_tool"
                trace.answer = Answer(
                    text=f"정책이 없는 도구를 불렀다: {action.tool!r}",
                    insufficient_information=True).to_dict()
                return trace

            t0 = time.time()
            try:
                result = tool(**action.arguments)
            except Exception as exc:                          # noqa: BLE001
                result = ToolResult(action.tool, "error",
                                    message=f"{type(exc).__name__}: {exc}")
            trace.record(action.tool, action.arguments, result, time.time() - t0)
            observations.append({**result.to_dict(), "arguments": action.arguments})

            if result.status == "error":
                retries[action.tool] = retries.get(action.tool, 0) + 1
                if retries[action.tool] > self.max_search_retries:
                    trace.stop_reason = "retry_limit"
                    trace.answer = Answer(
                        text=f"{action.tool} 가 반복 실패해 중단했다.",
                        insufficient_information=True,
                        caveats=[f"{action.tool} 재시도 {self.max_search_retries}회 한도 초과"],
                    ).to_dict()
                    return trace
