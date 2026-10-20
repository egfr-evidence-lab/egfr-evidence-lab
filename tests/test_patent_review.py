import unittest

from scripts.review_patent_assay import classify, exact_number


class PatentSourceReviewTests(unittest.TestCase):
    def test_same_assay_can_contain_different_target_columns(self):
        # 특허 compound 362의 Cot=1 nM와 EGFR=3984 nM를 혼동하지 않는다.
        self.assertEqual(classify("1.0", "=", "1", "3984"), "matches_cot_column_only")
        self.assertEqual(classify("3984.0", "=", "1", "3984"), "matches_explicit_egfr_column")

    def test_equal_values_do_not_identify_a_target_and_bounds_are_not_exact(self):
        self.assertEqual(classify("1", "=", "1", "1"), "matches_both_target_columns_ambiguous")
        self.assertIsNone(exact_number(">10000"))
        self.assertIsNone(exact_number("NA"))
        self.assertEqual(classify("50", "<", "50", "50"), "non_exact_or_non_numeric_requires_review")


if __name__ == "__main__":
    unittest.main()
