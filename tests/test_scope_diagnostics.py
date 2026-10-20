"""자료 범위·누출·합성 분석값의 잘못된 연결을 막는 검사."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
try:
    import numpy as np
    import pandas as pd
    from diagnose_cohort_scope import concentration_summary,inverse_simpson,prospective_splits
    from review_patent_structures import extract_source_masses,expected_m_plus_h
except ImportError:
    concentration_summary=None


@unittest.skipIf(concentration_summary is None,"구조·분할 진단에는 ML 환경이 필요합니다.")
class ScopeDiagnosticsTests(unittest.TestCase):
    def test_label_range_is_logarithmic_and_invalid_concentration_fails(self):
        result=concentration_summary([10,100,1000])
        self.assertAlmostEqual(result["pIC50_span"],2)
        self.assertAlmostEqual(result["pIC50_sample_SD"],1)
        for values in ([0,1],[-1,3],[float('nan'),4]):
            with self.assertRaises(ValueError):concentration_summary(values)

    def test_diversity_index_distinguishes_equal_groups_from_concentration(self):
        self.assertAlmostEqual(inverse_simpson(['a','b','c']),3)
        self.assertLess(inverse_simpson(['a']*8+['b','c']),2)

    def test_stereo_and_repeat_groups_do_not_leak_under_either_split(self):
        frame=pd.DataFrame({'connectivity':['a','a','b','c','d','e'],'scaffold':['s1','s1','s1','s2','s3','s4']})
        for scheme,parts in prospective_splits(frame,3,42).items():
            evaluations=[]
            for train,test in parts:
                self.assertFalse(set(frame.iloc[train].connectivity)&set(frame.iloc[test].connectivity))
                if scheme=='scaffold':self.assertFalse(set(frame.iloc[train].scaffold)&set(frame.iloc[test].scaffold))
                evaluations.extend(test)
            self.assertEqual(sorted(evaluations),list(range(len(frame))))

    def test_intermediate_MS_is_not_assigned_to_a_final_compound(self):
        html='<heading>Example 3 Preparation of Compound G-3</heading><div>Intermediate MS(ESI):634.4 [M+H]</div>'
        html+='<tables><tr><td>31</td><td>G-31</td><td>NH</td><td>H</td><td></td><td></td><td>499.2</td></tr></tables>'
        masses=extract_source_masses(html)
        self.assertNotIn('G-3',masses)
        self.assertEqual(masses['G-31']['reported_M_plus_H'],499.2)

    def test_mass_cannot_distinguish_structural_isomers(self):
        self.assertAlmostEqual(expected_m_plus_h('CCO'),expected_m_plus_h('COC'))
        with self.assertRaises(ValueError):expected_m_plus_h('CCN.Cl')
        with self.assertRaises(ValueError):expected_m_plus_h('C[NH3+]')


if __name__=='__main__':unittest.main()
