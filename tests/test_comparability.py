"""실험 간 일치도와 불확실성 때문에 병합을 보류해야 하는 경우를 검사한다."""

import json
from pathlib import Path
import unittest

try:
    from egfr_lab.data.comparability import agreement_metrics, compare_protocols, wilson_interval
    from scripts.review_wt_cohort import source_values
    HAVE_P0 = True
except ImportError:
    HAVE_P0 = False


@unittest.skipUnless(HAVE_P0, "P0 의존성이 필요합니다.")
class ComparabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads((Path(__file__).parents[1] / "configs/cohort_policy.json").read_text())["cross_assay_pooling_requires"]

    def test_missing_protocol_values_are_not_evidence_of_equality(self):
        result = compare_protocols({"atp_uM": None}, {"atp_uM": None}, ["atp_uM"])
        self.assertFalse(result["protocols_complete_and_equal"])
        self.assertEqual(result["missing_fields"], "atp_uM")
        self.assertFalse(compare_protocols({"atp_uM": 5}, {"atp_uM": 10}, ["atp_uM"])["protocols_complete_and_equal"])
        self.assertTrue(compare_protocols({"atp_uM": 5}, {"atp_uM": 5}, ["atp_uM"])["protocols_complete_and_equal"])

    def test_one_shared_control_never_validates_pooling(self):
        result = agreement_metrics([8], [8], self.policy)
        self.assertFalse(result["statistical_gate_passed"])
        self.assertIsNone(result["bias_bootstrap_95_lower"])

    def test_five_perfect_points_still_have_large_uncertainty(self):
        result = agreement_metrics([8] * 5, [8] * 5, self.policy)
        self.assertEqual(result["fraction_within_0_5"], 1)
        self.assertLess(result["agreement_wilson_95_lower"], 0.75)
        self.assertFalse(result["statistical_gate_passed"])

    def test_systematic_bias_cannot_hide_behind_perfect_correlation(self):
        self.assertFalse(agreement_metrics(list(range(20)), list(range(1, 21)), self.policy)["statistical_gate_passed"])
        self.assertTrue(agreement_metrics([8] * 20, [8] * 20, self.policy)["statistical_gate_passed"])

    def test_invalid_pairs_are_rejected(self):
        for left, right in (([1], [1, 2]), ([float("nan")], [1]), ([1], [float("inf")])):
            with self.assertRaises(ValueError):
                agreement_metrics(left, right, self.policy)
        self.assertEqual(wilson_interval(0, 0), (None, None))
        self.assertFalse(agreement_metrics([], [], self.policy)["statistical_gate_passed"])

    def test_cellular_tables_do_not_become_biochemical_source_values(self):
        with self.assertRaises(ValueError):
            source_values("<table><tr><th>Compound</th><th>A549 IC50 (μM)</th></tr><tr><td>2</td><td>0.31</td></tr></table>")

    def test_paper_values_keep_source_compound_keys(self):
        rows = "".join(f"<tr><td>{i}</td><td>6.3 ± 1.0</td></tr>" for i in [2, *range(8, 29)])
        values = source_values("<table><tr><th>Compound</th><th>EGFR WT IC50 (nM)</th></tr>" + rows + "</table>")
        self.assertEqual(len(values), 22)
        self.assertEqual(values["14"], 6.3)


if __name__ == "__main__":
    unittest.main()
