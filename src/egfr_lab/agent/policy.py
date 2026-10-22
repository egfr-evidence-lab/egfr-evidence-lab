"""정책 구현.

RulePolicy
    LLM 없이 동작하는 규칙 기반 정책. 지금 키가 없으므로 이것으로 하네스를 검증한다.
    **이것은 LLM Agent 가 아니다.** 결과를 보고할 때 그렇게 쓰지 않는다.
    기준선으로서의 가치는 있다. LLM 정책이 이보다 나은지 같은 질문·같은 채점으로 비교한다.

LLMPolicy
    같은 인터페이스를 따르는 LLM 정책. API 키가 없으면 생성 시점에 명확히 실패한다.
    키가 없는데 조용히 규칙 기반으로 떨어지지 않는다. 무엇을 돌렸는지 흐려지기 때문이다.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

from .runner import Action, Answer

# 질의에서 식별자를 뽑는 정규식
CHEMBL_ID = re.compile(r"\bCHEMBL\d+\b", re.I)
DOI = re.compile(r"\b10\.\d{4,9}/[^\s,;)\]]+")
PMID = re.compile(r"\bPMID[:\s]*(\d{6,9})\b", re.I)
SMILES_HINT = re.compile(r"SMILES[:\s]+(\S+)", re.I)


@dataclass
class RulePolicy:
    """키워드와 식별자로 도구를 고르는 결정적 정책."""

    name: str = "rule_based"
    version: str = "v1"
    model: str | None = None            # LLM 이 아니므로 모델 이름을 만들지 않는다
    prompt_version: str | None = None

    def decide(self, question: str, observations: list[dict]) -> Action:
        q = question.strip()
        done = [o["tool"] for o in observations]

        # 0) 직전 호출이 오류면 다른 도구로 갈아타지 않는다.
        #    입력이 잘못됐다는 뜻이라 재시도해도 같은 결과이고, 무엇보다
        #    사용자가 물은 것과 **다른 질문에 답하게 되기** 때문이다.
        #    (예: ChEMBL 조회가 실패했는데 문헌 검색 결과를 대신 내놓는 일)
        if observations and observations[-1]["status"] == "error":
            last = observations[-1]
            return Action("finish", answer=Answer(
                text=f"{last['tool']} 호출이 실패해 근거를 얻지 못했다: {last['message']}",
                insufficient_information=True,
                caveats=[f"{last['tool']} 가 실패했다. 다른 도구의 결과로 대신 답하지 않는다"],
            ))

        smiles = SMILES_HINT.search(q)
        chembl = CHEMBL_ID.search(q)
        doi = DOI.search(q)
        pmid = PMID.search(q)
        wants_prediction = any(k in q for k in ("예측", "predict", "얼마로 예상", "추정"))
        wants_measured = any(k in q for k in ("실측", "측정값", "보고된", "ChEMBL", "기록"))
        wants_literature = any(k in q for k in ("문헌", "논문", "검색", "찾아", "literature"))
        wants_access = any(k in q for k in ("전문", "본문", "접근", "볼 수 있", "확보"))

        # 1) 서지·접근성 질문: 식별자가 있으면 바로 확인한다
        if (doi or pmid) and "fetch_evidence" not in done:
            ident = doi.group(0) if doi else pmid.group(1)
            return Action("call", "fetch_evidence", {"identifier": ident})

        # 2) 실측값 질문. 문헌 검색보다 먼저 본다.
        #    '찾아줘' 같은 말이 들어가도 ChEMBL·실측을 물으면 조회 도구로 가야 한다.
        #    유효한 ID 가 없으면 질문에서 뽑은 이름을 그대로 넘겨 도구가 오류를 돌려주게 한다.
        #    여기서 임의로 ID 를 지어내지 않는 것이 요점이다.
        if (chembl or wants_measured) and "lookup_measurements" not in done:
            ident = chembl.group(0) if chembl else self._compound_token(q)
            if ident:
                return Action("call", "lookup_measurements", {"molecule_chembl_id": ident})

        # 3) 예측 질문 — SMILES 가 있어야 한다
        if wants_prediction and smiles and "predict_activity" not in done:
            return Action("call", "predict_activity", {"smiles": smiles.group(1)})

        # 4) 예측을 물었는데 SMILES 도 ChEMBL ID 도 없으면 도구를 부르지 않고 모른다고 답한다
        if wants_prediction and not smiles and not chembl and not observations:
            return Action("finish", answer=Answer(
                text="예측에 필요한 분자 구조(SMILES)나 ChEMBL ID 가 질문에 없다. 추정하지 않는다.",
                insufficient_information=True,
                caveats=["질문에 분자 식별 정보가 없어 도구를 호출하지 않았다"],
            ))

        # 5) 문헌 검색
        if (wants_literature or wants_access) and "search_literature" not in done and not (doi or pmid):
            return Action("call", "search_literature", {"query": self._to_query(q)})

        # 5-1) 검색이 0건이면 질의를 넓혀 한 번 더 시도한다.
        #      Europe PMC 는 영어 색인이라 한국어가 섞이면 0건이 나오기 쉽다.
        #      재시도 횟수는 실행기의 max_search_retries 와 별개로 여기서 1회만 쓴다.
        if (sum(1 for t in done if t == "search_literature") == 1
                and observations and observations[-1]["tool"] == "search_literature"
                and observations[-1]["status"] == "not_found"):
            broadened = self._broaden(observations[-1]["arguments"].get("query", ""))
            if broadened and broadened != observations[-1]["arguments"].get("query"):
                return Action("call", "search_literature", {"query": broadened})

        # 6) 모은 관측으로 답을 만든다
        if observations:
            return Action("finish", answer=self._compose(q, observations))

        # 7) 어느 경로에도 해당하지 않으면 모른다고 답한다
        return Action("finish", answer=Answer(
            text="이 질문에 쓸 수 있는 도구를 고르지 못했다. 답을 지어내지 않는다.",
            insufficient_information=True,
            caveats=["질문이 연결된 도구의 범위를 벗어난다"],
        ))

    # -- 답변 구성 ---------------------------------------------------------- #

    @staticmethod
    def _compound_token(question: str) -> str:
        """질문에서 화합물 이름으로 보이는 라틴 문자 토큰을 뽑는다.

        찾지 못하면 빈 문자열을 돌려준다. 억지로 만들지 않는다.
        """
        skip = {"EGFR", "CHEMBL", "IC50", "PIC50", "SMILES", "DNA", "RNA"}
        for tok in re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", question):
            if tok.upper() not in skip:
                return tok
        return ""

    @staticmethod
    def _to_query(question: str) -> str:
        """질문에서 검색어를 만든다.

        Europe PMC 는 영어 색인이라 한국어를 그대로 넣으면 0건이 나온다.
        유전자·변이 표기처럼 라틴 문자·숫자로 된 토큰만 남긴다.
        남는 것이 없으면 원문을 그대로 쓴다(없는 영어를 지어내지 않는다).
        """
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9\-]*\d*|\d+[A-Za-z]+", question)
        drop = {"SMILES"}
        tokens = [t for t in tokens if t.upper() not in drop]
        if tokens:
            return " ".join(tokens)
        return re.sub(r"\s+", " ", re.sub(r"[?？]", " ", question)).strip()

    @staticmethod
    def _broaden(query: str) -> str:
        """0건일 때 질의를 넓힌다. 앞쪽 토큰 2개만 남긴다."""
        tokens = query.split()
        return " ".join(tokens[:2]) if len(tokens) > 2 else ""

    def _compose(self, question: str, observations: list[dict]) -> Answer:
        claims: list[dict] = []
        caveats: list[str] = []
        insufficient = True

        for obs in observations:
            caveats.extend(obs.get("caveats") or [])
            if obs["status"] != "ok":
                continue
            insufficient = False
            tool, data, sids = obs["tool"], obs.get("data"), obs.get("source_ids") or []

            if tool == "predict_activity" and isinstance(data, dict):
                ap = data["applicability"]
                claims.append({
                    "text": f"모델 예측 pIC50 는 {data['predicted_pIC50']} 이다.",
                    "source_ids": sids,
                })
                claims.append({
                    "text": (f"학습 분자와의 최대 Tanimoto 유사도는 {ap['max_tanimoto_to_training']} 이고 "
                             f"scaffold 가 학습 범위에 "
                             f"{'있다' if ap['scaffold_in_training'] else '없다'}."),
                    "source_ids": sids,
                })

            elif tool == "lookup_measurements" and isinstance(data, list) and data:
                for row in data[:3]:
                    claims.append({
                        "text": (f"{row['assay_chembl_id']} 에서 {row['standard_type']} "
                                 f"{row['standard_relation']} {row['standard_value']} "
                                 f"{row['standard_units']} 로 보고됐다."),
                        "source_ids": [f"chembl_activity:{row['activity_id']}"],
                    })

            elif tool == "search_literature" and isinstance(data, list) and data:
                for row in data[:3]:
                    ident = (f"doi:{row['doi']}" if row.get("doi")
                             else f"pmid:{row.get('pmid')}")
                    claims.append({
                        "text": (f"{row['year']}년 {row['journal']} 의 '{(row['title'] or '')[:60]}' "
                                 f"(공개접근 {row['is_open_access']})"),
                        "source_ids": [ident],
                    })

            elif tool == "fetch_evidence" and isinstance(data, dict):
                claims.append({
                    "text": (f"'{(data.get('title') or '')[:60]}' 는 "
                             f"{'공개 접근이다' if data['is_open_access'] else '공개 접근이 아니다'}. "
                             f"전문 상태: {', '.join(data['full_text_availability'])}."),
                    "source_ids": sids,
                })

        if insufficient:
            return Answer(
                text="도구가 근거를 돌려주지 못했다. 답을 지어내지 않는다.",
                insufficient_information=True,
                caveats=sorted(set(caveats)),
            )

        return Answer(
            text="도구가 돌려준 근거로만 구성한 답이다.",
            claims=claims,
            caveats=sorted(set(caveats)),
            insufficient_information=False,
        )


SYSTEM_PROMPT = """\
너는 EGFR 활성 데이터에 대한 질문에 **도구가 돌려준 근거로만** 답하는 보조자다.

쓸 수 있는 도구:
- predict_activity(smiles): pilot22 모델의 pIC50 예측. 적용 범위 판정이 함께 온다.
- lookup_measurements(molecule_chembl_id): ChEMBL 의 실측 활성. ID 는 CHEMBL 로 시작해야 한다.
- search_literature(query): Europe PMC 문헌 검색. 영어 질의가 잘 맞는다.
- fetch_evidence(identifier): DOI 나 PMID 의 서지와 전문 접근 가능성.
- finish(...): 답을 확정하고 끝낸다.

반드시 지켜야 할 규칙:
1. 도구가 돌려주지 않은 수치를 절대 답에 넣지 마라. 기억에 의존해 값을 말하지 마라.
2. 수치를 담은 주장에는 도구가 준 source_ids 를 붙여라. 출처 없는 수치는 거절된다.
3. 근거가 없으면 insufficient_information=true 로 모른다고 답하라. 추측하지 마라.
4. 도구가 실패하면 다른 도구의 결과로 대신 답하지 마라. 실패를 보고하라.
5. 연결된 도구의 범위를 벗어난 질문(임상시험 결과 등)은 도구를 부르지 말고 모른다고 답하라.
6. 도구가 준 caveats 를 답의 caveats 에 옮겨라. 특히 적용 범위 밖·외삽·비공개 접근 경고는 빠뜨리지 마라.
7. 도구 호출 예산이 제한돼 있다. 필요한 만큼만 부르고 끝내라.

finish 의 claims 는 [{"text": 주장, "source_ids": [출처...]}] 형태다.
"""

TOOL_SCHEMA = [
    {"type": "function", "function": {
        "name": "predict_activity",
        "description": "pilot22 모델로 EGFR pIC50 을 예측한다. 적용 범위 판정이 함께 온다.",
        "parameters": {"type": "object", "properties": {
            "smiles": {"type": "string", "description": "분자의 SMILES"}},
            "required": ["smiles"]}}},
    {"type": "function", "function": {
        "name": "lookup_measurements",
        "description": "ChEMBL 에서 분자-EGFR 의 실측 활성을 조회한다.",
        "parameters": {"type": "object", "properties": {
            "molecule_chembl_id": {"type": "string", "description": "CHEMBL 로 시작하는 분자 ID"}},
            "required": ["molecule_chembl_id"]}}},
    {"type": "function", "function": {
        "name": "search_literature",
        "description": "Europe PMC 에서 문헌을 검색한다.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "검색어(영어 권장)"}},
            "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "fetch_evidence",
        "description": "DOI 나 PMID 로 서지와 전문 접근 가능성을 확인한다.",
        "parameters": {"type": "object", "properties": {
            "identifier": {"type": "string", "description": "DOI 또는 PMID"}},
            "required": ["identifier"]}}},
    {"type": "function", "function": {
        "name": "finish",
        "description": "답을 확정하고 끝낸다.",
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string"},
            "claims": {"type": "array", "items": {"type": "object", "properties": {
                "text": {"type": "string"},
                "source_ids": {"type": "array", "items": {"type": "string"}}},
                "required": ["text", "source_ids"]}},
            "caveats": {"type": "array", "items": {"type": "string"}},
            "insufficient_information": {"type": "boolean"}},
            "required": ["text", "insufficient_information"]}}},
]


@dataclass
class OpenAIPolicy:
    """OpenAI Chat Completions 의 function calling 으로 도구를 고르는 정책.

    키가 없으면 생성 시점에 실패한다. 규칙 기반으로 조용히 대체하지 않는다.
    무엇을 돌렸는지 흐려지면 평가 결과를 믿을 수 없기 때문이다.
    """

    model: str = "gpt-4o-mini"
    name: str = "openai"
    version: str = "v1"
    prompt_version: str = "agent-prompt-v1"
    temperature: float = 0.0
    base_url: str = "https://api.openai.com/v1"
    env_var: str = "OPENAI_API_KEY"
    key_file: str = "openai_api_key"
    max_tool_calls: int = 0          # 0 이면 남은 예산을 알리지 않는다

    temperature_dropped: bool = False

    def __post_init__(self) -> None:
        from .credentials import load_key
        self._key = load_key(self.env_var, self.key_file)   # 없으면 여기서 실패한다
        self._messages: list[dict] = []
        self._pending_call_id: str | None = None

    # -- API 호출 ----------------------------------------------------------- #

    def _post_once(self, payload: dict) -> dict:
        import json as _json
        import urllib.error
        import urllib.request

        from .credentials import redact

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=_json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self._key}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return _json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:400]
            raise RuntimeError(
                f"OpenAI 요청 실패 {exc.code}: {redact(body, self._key)}") from None
        except Exception as exc:                              # noqa: BLE001
            raise RuntimeError(
                f"OpenAI 요청 실패: {redact(str(exc), self._key)}") from None

    def _post(self, payload: dict) -> dict:
        """temperature 를 받지 않는 모델이 있다. 거부당하면 빼고 한 번 더 보낸다.

        모델별 지원 여부를 코드에 적어두면 모델이 바뀔 때마다 틀린다.
        API 가 거부하는 것을 보고 판단한다. 뺀 사실은 기록에 남긴다.
        """
        try:
            return self._post_once(payload)
        except RuntimeError as exc:
            if "temperature" in str(exc) and "temperature" in payload:
                payload = {k: v for k, v in payload.items() if k != "temperature"}
                self.temperature_dropped = True
                return self._post_once(payload)
            raise

    # -- 정책 인터페이스 ----------------------------------------------------- #

    def decide(self, question: str, observations: list[dict]) -> Action:
        import json as _json

        # 새 질문이면 대화를 초기화한다(관측이 비어 있는 것이 실행 시작 신호다).
        if not observations:
            self._messages = [{"role": "system", "content": SYSTEM_PROMPT},
                              {"role": "user", "content": question}]
            self._pending_call_id = None

        # 직전 호출의 결과를 OpenAI 규약대로 tool 메시지로 붙인다.
        # user 메시지로 넘기면 모델이 '내가 이미 불렀다'는 것을 알지 못해
        # 같은 호출을 예산이 소진될 때까지 반복한다(실제로 겪었다).
        if observations and self._pending_call_id:
            self._messages.append({
                "role": "tool",
                "tool_call_id": self._pending_call_id,
                "content": _json.dumps(observations[-1], ensure_ascii=False)[:6000],
            })
            self._pending_call_id = None

        # 남은 예산을 알려준다. 모델은 실행기의 한도를 볼 수 없어서,
        # 알려주지 않으면 이미 근거를 얻고도 계속 검색하다 예산을 소진한다(실제로 겪었다).
        if self.max_tool_calls:
            left = self.max_tool_calls - len(observations)
            self._messages.append({"role": "user", "content":
                                   f"[남은 도구 호출: {left}회] 충분한 근거를 이미 얻었다면 "
                                   f"지금 finish 를 불러라. 예산을 모두 쓰면 답하지 못한다."})

        data = self._post({
            "model": self.model,
            "messages": self._messages,
            "tools": TOOL_SCHEMA,
            "tool_choice": "required",
            "temperature": self.temperature,
        })

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        calls = message.get("tool_calls") or []
        if calls:
            # 모델의 발화(도구 호출 포함)를 대화에 남겨야 다음 턴에 맥락이 이어진다.
            self._messages.append({
                "role": "assistant",
                "content": message.get("content"),
                "tool_calls": [calls[0]],
            })
            self._pending_call_id = calls[0].get("id")
        if not calls:
            # 도구를 고르지 않으면 모른다고 답하게 한다. 본문을 답으로 삼지 않는다.
            return Action("finish", answer=Answer(
                text="모델이 도구를 고르지 않았다.", insufficient_information=True,
                caveats=["정책이 도구를 선택하지 못했다"]))

        call = calls[0]["function"]
        try:
            args = _json.loads(call.get("arguments") or "{}")
        except ValueError:
            return Action("finish", answer=Answer(
                text="모델이 올바르지 않은 인자를 돌려줬다.", insufficient_information=True))

        if call["name"] == "finish":
            return Action("finish", answer=Answer(
                text=str(args.get("text", "")),
                claims=list(args.get("claims") or []),
                caveats=list(args.get("caveats") or []),
                insufficient_information=bool(args.get("insufficient_information", False)),
            ))
        return Action("call", call["name"], args)


@dataclass
class AnthropicPolicy:
    """Anthropic 키가 생기면 쓸 자리. 아직 구현하지 않았다."""

    model: str = "claude-sonnet-5-5"
    name: str = "anthropic"
    version: str = "v1"
    prompt_version: str = "agent-prompt-v1"
    env_var: str = "ANTHROPIC_API_KEY"
    key_file: str = "anthropic_api_key"

    def __post_init__(self) -> None:
        from .credentials import load_key
        self._key = load_key(self.env_var, self.key_file)

    def decide(self, question: str, observations: list[dict]) -> Action:  # pragma: no cover
        raise NotImplementedError("Anthropic 호출부는 아직 구현하지 않았다. OpenAIPolicy 를 쓴다.")


# 이전 이름 유지: 키가 없으면 실패한다는 동작은 그대로다.
LLMPolicy = AnthropicPolicy
