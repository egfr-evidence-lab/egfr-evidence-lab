"""원문 구간·평균과 오차·구조 재계산의 의미를 지키는 회귀 검사."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
try:
    from review_main_cohort_sources import agrees, category_midpoint, parse_measurement
    from prioritize_main_cohort import inspect_structure
except ImportError:
    agrees = None


@unittest.skipIf(agrees is None, "원문 구조 검사에는 P0 패키지가 필요합니다.")
class SourceMeasurementTests(unittest.TestCase):
    def test_interval_midpoints_are_recognized_without_exact_conversion(self):
        for category, value in [("B",55),("C",550),("D",5500)]:
            self.assertTrue(category_midpoint(category,"=",value))
            self.assertIsNone(parse_measurement(category))
        self.assertFalse(category_midpoint("A","=",10))
        self.assertFalse(category_midpoint("B",">",55))

    def test_bounds_and_uncertainty_are_preserved(self):
        self.assertEqual(parse_measurement(">10",1000),(">",10000,None))
        self.assertFalse(agrees(parse_measurement(">10",1000),"=",10000))
        self.assertEqual(parse_measurement("0.67 ± 0.08",1000),("=",670,80))

    def test_single_concentration_inhibition_is_not_an_IC50(self):
        self.assertIsNone(parse_measurement("88.6% @1uM"))
        self.assertIsNone(parse_measurement("0.1% @1uM"))
        self.assertTrue(agrees(parse_measurement("0.0231",1000),"=",23.1))

    def test_connectivity_groups_stereo_without_removing_original_structure(self):
        left=inspect_structure("N[C@H](C)O")
        right=inspect_structure("N[C@@H](C)O")
        self.assertNotEqual(left[0],right[0])
        self.assertEqual(left[1],right[1])
        self.assertEqual(left[2],right[2])
        self.assertIsNone(inspect_structure("CCN.Cl"))


if __name__ == "__main__":
    unittest.main()
