"""Protect label units and evaluation rules that would otherwise corrupt research."""

from copy import deepcopy
from pathlib import Path
import unittest

from egfr_lab.config import load_config, validate_config
from egfr_lab.labels import ic50_to_pic50


class LabelContractTests(unittest.TestCase):
    def test_equivalent_units(self):
        for value, unit in [(10, "nM"), (0.01, "uM"), (0.01, "μM"),
                            (0.01, "µM"), (10000, "pM"), (1e-8, "M")]:
            with self.subTest(unit=unit):
                self.assertAlmostEqual(ic50_to_pic50(value, unit), 8.0)

    def test_invalid_measurements_rejected(self):
        for value in [0, -1, float("nan"), float("inf"), True]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                ic50_to_pic50(value, "nM")
        for relation in [">", "<", ">=", "~"]:
            with self.subTest(relation=relation), self.assertRaises(ValueError):
                ic50_to_pic50(10, "nM", relation)
        with self.assertRaises(ValueError):
            ic50_to_pic50(10, "mg/mL")


class ScopeContractTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "configs" / "project.json"
        self.config = load_config(path)

    def test_scientific_scope_guards(self):
        cases = [("curation", "unknown_variant_is_wild_type", True),
                 ("curation", "pool_cell_and_biochemical_assays", True),
                 ("curation", "pool_ic50_ki_kd", True),
                 ("evaluation", "test_used_for_tuning", True),
                 ("evaluation", "fractions", [0.7, 0.2, 0.2]),
                 ("agent", "llm_may_invent_measurements", True)]
        for section, key, value in cases:
            changed = deepcopy(self.config)
            changed[section][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_config(changed)


if __name__ == "__main__":
    unittest.main()
