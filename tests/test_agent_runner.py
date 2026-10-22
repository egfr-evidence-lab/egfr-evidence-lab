"""Agent 실행기의 방어장치 검사.

실행기의 존재 이유는 정책이 무엇을 하든 **출처 없는 수치를 막는 것**이다.
정책이 올바르게 동작하는 경우만 시험하면 이 방어장치를 시험한 것이 아니므로,
일부러 수치를 지어내는 정책을 넣어 막히는지 확인한다.

외부 네트워크를 쓰지 않는다. 도구는 가짜로 대체한다.
"""
import unittest
from pathlib import Path

try:
    from egfr_lab.agent.runner import Action, AgentRunner, Answer
    from egfr_lab.agent.tools import ToolResult
    AGENT_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    AGENT_AVAILABLE = False

BUDGET = {"max_tool_calls": 6, "max_search_retries": 2,
          "require_source_ids": True, "llm_may_invent_measurements": False}


def fake_lookup(molecule_chembl_id):
    """IC50 22.4 nM 하나만 돌려주는 가짜 조회 도구."""
    return ToolResult("lookup_measurements", "ok",
                      data=[{"activity_id": 1, "standard_value": 22.4, "standard_units": "nM"}],
                      source_ids=["chembl_activity:1"])


def fake_error(**_kwargs):
    return ToolResult("lookup_measurements", "error", message="의도적 실패")


class ScriptedPolicy:
    """첫 호출은 도구, 다음은 주어진 주장으로 끝내는 정책."""

    name = "scripted"
    version = "test"
    model = None
    prompt_version = None

    def __init__(self, claim, tool="lookup_measurements"):
        self.claim = claim
        self.tool = tool
        self.calls = 0

    def decide(self, question, observations):
        self.calls += 1
        if self.calls == 1:
            return Action("call", self.tool, {"molecule_chembl_id": "CHEMBL1"})
        return Action("finish", answer=Answer(text="답", claims=[self.claim]))


@unittest.skipUnless(AGENT_AVAILABLE, "agent 모듈 없음")
class RunnerGuardTests(unittest.TestCase):
    def setUp(self):
        self.runner = AgentRunner({"lookup_measurements": fake_lookup},
                                  BUDGET, Path(__file__))

    def test_rejects_number_not_returned_by_tools(self):
        """도구가 돌려주지 않은 수치는 출처를 달아도 막는다."""
        policy = ScriptedPolicy({"text": "IC50 는 0.07 nM 이다.", "source_ids": ["chembl:X"]})
        trace = self.runner.run("t", "질문", policy).to_dict()
        self.assertEqual(trace["stop_reason"], "answer_rejected_unsourced")
        self.assertTrue(trace["answer"]["insufficient_information"])

    def test_rejects_unsourced_number(self):
        """도구가 돌려준 수치라도 출처가 없으면 막는다."""
        policy = ScriptedPolicy({"text": "IC50 는 22.4 nM 이다.", "source_ids": []})
        trace = self.runner.run("t", "질문", policy).to_dict()
        self.assertEqual(trace["stop_reason"], "answer_rejected_unsourced")

    def test_accepts_sourced_number_from_tools(self):
        """정당한 주장까지 막으면 안 된다(거짓 양성 검사)."""
        policy = ScriptedPolicy({"text": "IC50 는 22.4 nM 이다.",
                                 "source_ids": ["chembl_activity:1"]})
        trace = self.runner.run("t", "질문", policy).to_dict()
        self.assertEqual(trace["stop_reason"], "answered")
        self.assertFalse(trace["answer"]["insufficient_information"])

    def test_budget_exhaustion_stops_and_declares_insufficient(self):
        class Loop:
            name = "loop"
            version = "test"
            model = None
            prompt_version = None

            def decide(self, question, observations):
                return Action("call", "lookup_measurements", {"molecule_chembl_id": "CHEMBL1"})

        trace = self.runner.run("t", "질문", Loop()).to_dict()
        self.assertEqual(trace["n_calls"], BUDGET["max_tool_calls"])
        self.assertEqual(trace["stop_reason"], "budget_exhausted")
        self.assertTrue(trace["answer"]["insufficient_information"])

    def test_retry_limit_on_repeated_tool_errors(self):
        runner = AgentRunner({"lookup_measurements": fake_error}, BUDGET, Path(__file__))

        class AlwaysCall:
            name = "always"
            version = "test"
            model = None
            prompt_version = None

            def decide(self, question, observations):
                return Action("call", "lookup_measurements", {"molecule_chembl_id": "CHEMBL1"})

        trace = runner.run("t", "질문", AlwaysCall()).to_dict()
        self.assertEqual(trace["stop_reason"], "retry_limit")
        self.assertLessEqual(trace["n_calls"], BUDGET["max_search_retries"] + 1)

    def test_unknown_tool_is_reported_not_guessed(self):
        class Bad:
            name = "bad"
            version = "test"
            model = None
            prompt_version = None

            def decide(self, question, observations):
                return Action("call", "no_such_tool", {})

        trace = self.runner.run("t", "질문", Bad()).to_dict()
        self.assertEqual(trace["stop_reason"], "unknown_tool")
        self.assertTrue(trace["answer"]["insufficient_information"])

    def test_insufficient_answer_needs_no_sources(self):
        class Giveup:
            name = "giveup"
            version = "test"
            model = None
            prompt_version = None

            def decide(self, question, observations):
                return Action("finish", answer=Answer(
                    text="모른다", insufficient_information=True))

        trace = self.runner.run("t", "질문", Giveup()).to_dict()
        self.assertEqual(trace["stop_reason"], "answered")
        self.assertEqual(trace["n_calls"], 0)

    def test_trace_does_not_invent_model_name(self):
        """LLM 이 아닌 정책의 trace 에 모델 이름이 들어가면 안 된다."""
        policy = ScriptedPolicy({"text": "설명만 있는 주장", "source_ids": []})
        trace = self.runner.run("t", "질문", policy).to_dict()
        self.assertIsNone(trace["policy"]["model"])


@unittest.skipUnless(AGENT_AVAILABLE, "agent 모듈 없음")
class PredictorInputTests(unittest.TestCase):
    """빈 SMILES 에 예측값이 나오면 안 된다.

    RDKit 은 빈 문자열을 '원자 0개 분자'로 파싱해 None 을 돌려주지 않는다.
    이것을 거르지 않으면 분자가 없는데도 그럴듯한 숫자가 나온다.
    실제로 LLM 정책이 분자 없이 smiles='' 로 호출했고 pIC50 8.057 이 나왔다.
    """

    def setUp(self):
        from pathlib import Path

        from egfr_lab.agent.tools import ActivityPredictor
        artifact = Path(__file__).resolve().parents[1] / "artifacts/agent_predictor_20261021"
        if not artifact.exists():
            self.skipTest("예측기 산출물 없음")
        self.predictor = ActivityPredictor(artifact)

    def test_empty_smiles_is_error(self):
        for bad in ("", "   ", "\n"):
            with self.subTest(smiles=bad):
                self.assertEqual(self.predictor(bad).status, "error")

    def test_valid_smiles_still_works(self):
        self.assertEqual(self.predictor("CC(=O)Oc1ccccc1C(=O)O").status, "ok")


@unittest.skipUnless(AGENT_AVAILABLE, "agent 모듈 없음")
class LLMPolicyTests(unittest.TestCase):
    def test_llm_policy_fails_loudly_without_key(self):
        """키가 없을 때 조용히 규칙 기반으로 떨어지면 안 된다."""
        import os

        from egfr_lab.agent.policy import AnthropicPolicy as LLMPolicy

        saved = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            with self.assertRaises(RuntimeError):
                LLMPolicy()
        finally:
            if saved is not None:
                os.environ["ANTHROPIC_API_KEY"] = saved


if __name__ == "__main__":
    unittest.main()
