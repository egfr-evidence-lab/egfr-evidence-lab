import unittest

try:
    import numpy as np
    import pandas as pd
    from egfr_lab.modeling.baseline import make_splits, metrics, paired_cluster_ci, validate_pilot
    ML_AVAILABLE = True
except ModuleNotFoundError as exc:
    if exc.name not in {"sklearn", "scipy", "numpy", "pandas", "rdkit", "joblib"}:
        raise
    ML_AVAILABLE = False


@unittest.skipUnless(ML_AVAILABLE, "ML 검사는 .venv-ml 환경에서 실행")
class BaselineTests(unittest.TestCase):
    def frame_and_policy(self):
        rows = [{"activity_id": str(i), "structure_group": str(i), "assay_chembl_id": "A",
                 "target_chembl_id": "CHEMBL203", "standard_type": "IC50", "standard_relation": "=",
                 "standard_units": "nM", "variant_screen": "WT", "matched": "True", "screen_reasons": "",
                 "standard_value": str(v), "source_nM": str(v), "pIC50_computed": str(9-np.log10(v))}
                for i, v in enumerate((10, 100))]
        policy = {"purpose": "educational_exploratory", "hyperparameter_search": False,
                  "expected_rows": 2, "expected_assay": "A"}
        return pd.DataFrame(rows), policy

    def test_large_scaffold_stays_in_one_evaluation_fold(self):
        groups = np.array(["large"] * 7 + ["b", "c", "d", "e"])
        splits = make_splits(np.zeros((11, 4)), groups, 3, 42)["scaffold"]
        held_out = []
        for train, test in splits:
            self.assertFalse(set(groups[train]) & set(groups[test]))
            held_out.extend(test)
        self.assertEqual(sorted(held_out), list(range(11)))

    def test_non_exact_values_and_source_mismatches_fail(self):
        frame, policy = self.frame_and_policy()
        frame.loc[0, "standard_relation"] = ">"
        with self.assertRaises(ValueError):
            validate_pilot(frame, policy)
        frame.loc[0, "standard_relation"] = "="
        frame.loc[0, "source_nM"] = "11"
        with self.assertRaises(ValueError):
            validate_pilot(frame, policy)

    def test_education_does_not_authorize_benchmark_or_duplicate_structures(self):
        frame, policy = self.frame_and_policy()
        policy["purpose"] = "benchmark"
        with self.assertRaises(ValueError):
            validate_pilot(frame, policy)
        policy["purpose"] = "educational_exploratory"
        frame.loc[1, "structure_group"] = frame.loc[0, "structure_group"]
        with self.assertRaises(ValueError):
            validate_pilot(frame, policy)

    def test_identical_predictions_have_zero_paired_difference(self):
        result = paired_cluster_ci([1, 2, 3], [2, 2, 2], [2, 2, 2], ["a", "a", "b"], 100, 42)
        self.assertEqual(result["RF_minus_Dummy_MAE"], 0)
        self.assertEqual(result["conditional_CI95_low"], 0)
        self.assertEqual(result["conditional_CI95_high"], 0)

    def test_unpaired_and_nonfinite_errors_rejected(self):
        with self.assertRaises(ValueError):
            paired_cluster_ci([1, 2], [1], [1, 2], ["a", "b"], 10, 42)
        with self.assertRaises(ValueError):
            paired_cluster_ci([1, 2], [1, 2], [np.nan, 2], ["a", "b"], 10, 42)

    def test_constant_float_predictions_have_no_rank_correlation(self):
        self.assertIsNone(metrics([1, 2, 3], [7.777777777] * 3)["Spearman"])


if __name__ == "__main__":
    unittest.main()
