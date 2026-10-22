"""Agent 호출 trace 기록.

M5 완료 조건 4번이 '호출 trace 와 모델·prompt·출처 버전 기록'이다.
나중에 남이 같은 실행을 검증하려면 **무엇을 썼는지**가 결과만큼 중요하다.

기록하는 것:
  * 실행 단위: 정책 이름·버전, prompt 버전(있으면), 모델 이름(LLM 정책일 때),
    도구 모듈 해시, 예측기 모델 해시, 예산 설정
  * 호출 단위: 순번, 도구, 인자, 결과 status, 출처 id, caveat 수, 소요 시간, 오류 메시지
  * 종료: 종료 사유(답변·예산 소진·정보 부족·오류), 최종 답변과 인용

LLM 을 쓰지 않은 실행에서 모델 이름을 지어내지 않는다. `model` 은 None 으로 남긴다.
"""
from __future__ import annotations

import hashlib
import json
import platform
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass
class CallRecord:
    index: int
    tool: str
    arguments: dict
    status: str
    source_ids: list[str]
    caveat_count: int
    elapsed_sec: float
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "index": self.index, "tool": self.tool, "arguments": self.arguments,
            "status": self.status, "source_ids": self.source_ids,
            "caveat_count": self.caveat_count, "elapsed_sec": round(self.elapsed_sec, 3),
            "message": self.message,
        }


@dataclass
class RunTrace:
    question_id: str
    question: str
    policy_name: str
    policy_version: str
    model: str | None = None            # LLM 정책이 아니면 None 으로 남긴다
    prompt_version: str | None = None
    budget: dict = field(default_factory=dict)
    calls: list[CallRecord] = field(default_factory=list)
    answer: dict | None = None
    stop_reason: str = ""
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    _t0: float = field(default_factory=time.time, repr=False)

    def record(self, tool: str, arguments: dict, result, elapsed: float) -> None:
        self.calls.append(CallRecord(
            index=len(self.calls) + 1, tool=tool, arguments=arguments,
            status=result.status, source_ids=list(result.source_ids),
            caveat_count=len(result.caveats), elapsed_sec=elapsed, message=result.message,
        ))

    @property
    def tools_used(self) -> list[str]:
        return [c.tool for c in self.calls]

    def to_dict(self) -> dict:
        return {
            "question_id": self.question_id,
            "question": self.question,
            "policy": {"name": self.policy_name, "version": self.policy_version,
                       "model": self.model, "prompt_version": self.prompt_version},
            "budget": self.budget,
            "calls": [c.to_dict() for c in self.calls],
            "n_calls": len(self.calls),
            "tools_used": self.tools_used,
            "answer": self.answer,
            "stop_reason": self.stop_reason,
            "started_at": self.started_at,
            "total_elapsed_sec": round(time.time() - self._t0, 3),
        }


def environment_record(tool_module: Path, predictor_manifest: Path | None) -> dict:
    """출처·버전 기록. 도구 코드 자체의 해시도 남긴다."""
    rec = {
        "python": platform.python_version(),
        "platform": f"{platform.system()} {platform.machine()}",
        "tools_module_sha256": sha256_file(tool_module),
        "external_sources": {
            "chembl": "https://www.ebi.ac.uk/chembl/api/data (버전 비고정: 조회 시점의 릴리스)",
            "europe_pmc": "https://www.ebi.ac.uk/europepmc/webservices/rest (버전 비고정)",
        },
        "external_version_note": (
            "ChEMBL·Europe PMC 는 호출 시점의 내용을 돌려준다. 같은 질의가 나중에 다른 결과를 "
            "줄 수 있으므로 trace 의 시각과 반환된 출처 id 를 함께 봐야 한다"
        ),
    }
    if predictor_manifest and predictor_manifest.exists():
        m = json.loads(predictor_manifest.read_text(encoding="utf-8"))
        rec["predictor"] = {
            "model_sha256": m.get("model_sha256"),
            "cohort_sha256": m.get("cohort_sha256"),
            "scope": m.get("scope"),
            "n_training_molecules": m.get("n_training_molecules"),
        }
    return rec
