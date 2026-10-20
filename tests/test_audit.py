"""잘못된 WT 추론·실험 혼합·입체 통합·반복값 소실을 막는 감사 회귀 검사."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    import pandas as pd
    from egfr_lab.data.audit import audit, audit_molecule, build_frames, classify_assay, measurement_screen
    HAVE_P0 = True
except ImportError:
    HAVE_P0 = False


def assay(**changes):
    return {"assay_chembl_id": "A1", "target_chembl_id": "CHEMBL203", "document_chembl_id": "D1",
            "description": "Inhibition of recombinant human wild-type EGFR using ATP as substrate",
            "assay_type": "B", "bao_label": "single protein format", "confidence_score": 9,
            "relationship_type": "D", "assay_organism": "Homo sapiens", "assay_tax_id": 9606,
            "variant_mutation": None, "variant_accession": None, **changes}


def activity(**changes):
    return {"activity_id": 1, "molecule_chembl_id": "M1", "assay_chembl_id": "A1", "document_chembl_id": "D1",
            "standard_type": "IC50", "standard_relation": "=", "standard_value": "10", "standard_units": "nM",
            "data_validity_comment": None, "potential_duplicate": 0, "standard_flag": 1,
            "pchembl_value": "8.00", "assay_variant_mutation": None, "assay_variant_accession": None, **changes}


@unittest.skipUnless(HAVE_P0, "P0 의존성이 필요합니다.")
class AssayAuditTests(unittest.TestCase):
    def test_missing_variant_does_not_imply_wt(self):
        result = classify_assay(assay(description="Inhibition of recombinant EGFR using ATP substrate"))
        self.assertEqual(result["variant_screen"], "unresolved")
        self.assertFalse(result["assay_candidate"])

    def test_explicit_wt_requires_consistent_context(self):
        self.assertTrue(classify_assay(assay())["assay_candidate"])
        for changes in (
            {"variant_mutation": "T790M", "variant_accession": "P00533"},
            {"confidence_score": 8}, {"assay_organism": None},
            {"description": assay()["description"] + " (unknown origin)"},
            {"description": "Inhibition of wild type EGFR T790M mutant by HTRF assay"},
        ):
            with self.subTest(changes=changes):
                self.assertFalse(classify_assay(assay(**changes))["assay_candidate"])

    def test_binding_or_confidence9_does_not_mean_biochemical(self):
        for changes in ({"description": "Inhibition of wild-type EGFR in human A549 cells by HTRF assay"},
                        {"bao_label": "cell-based format"}, {"bao_label": "assay format"},
                        {"description": "Inhibition of wild-type EGFR"}):
            with self.subTest(changes=changes):
                self.assertFalse(classify_assay(assay(**changes))["assay_candidate"])

    def test_variants_are_separate_and_conflicts_held(self):
        result = classify_assay(assay(description="Inhibition of recombinant EGFR T790M/L858R mutant using ATP substrate",
                                      variant_mutation="L858R,T790M", variant_accession="P00533"))
        self.assertEqual(result["variant_screen"], "L858R+T790M")
        self.assertTrue(result["assay_candidate"])
        for changes in ({"variant_mutation": "UNDEFINED MUTATION"}, {"variant_accession": "OTHER"},
                        {"description": "Inhibition of recombinant EGFR C797S mutant using ATP substrate"}):
            row = assay(description="Inhibition of recombinant EGFR L858R mutant using ATP substrate",
                        variant_mutation="L858R", variant_accession="P00533")
            row.update(changes)
            self.assertFalse(classify_assay(row)["assay_candidate"])


@unittest.skipUnless(HAVE_P0, "P0 의존성이 필요합니다.")
class MeasurementAuditTests(unittest.TestCase):
    def test_censored_and_mass_concentrations_never_get_exact_labels(self):
        for changes in ({"standard_relation": ">"}, {"standard_relation": None},
                        {"standard_units": "ug.mL-1"}, {"standard_value": "NaN"},
                        {"standard_value": "0"}, {"standard_type": "Ki"}):
            with self.subTest(changes=changes):
                label, reasons = measurement_screen(activity(**changes))
                self.assertIsNone(label)
                self.assertTrue(reasons)
        self.assertEqual(measurement_screen(activity(standard_value="0.01", standard_units="µM")), (8.0, []))

    def test_quality_and_citation_duplicates_are_held(self):
        for changes in ({"data_validity_comment": "Outside typical range"}, {"potential_duplicate": 1}, {"standard_flag": 0}):
            self.assertTrue(measurement_screen(activity(**changes))[1])

    def test_stereo_and_salt_preserved(self):
        def mol(s):
            return audit_molecule({"canonical_smiles": s, "molecule_type": "Small molecule"})
        left, right = mol("C[C@H](O)c1ccccc1"), mol("C[C@@H](O)c1ccccc1")
        self.assertNotEqual(left["structure_group"], right["structure_group"])
        self.assertEqual(left["connectivity_smiles"], right["connectivity_smiles"])
        salt = mol("C[NH3+].[Cl-]")
        self.assertFalse(salt["structure_candidate"])
        self.assertIn(".", salt["canonical_isomeric_smiles"])
        self.assertFalse(mol("invalid_smiles")["structure_candidate"])
        self.assertEqual(mol("CC(O)c1ccccc1")["unspecified_stereocenters"], 1)
        self.assertEqual(mol("CCO")["scaffold_smiles"], "")
        unknown = audit_molecule({"canonical_smiles": "CCO", "molecule_type": None})
        self.assertFalse(unknown["structure_candidate"])
        self.assertEqual(unknown["structure_status"], "molecule_type_unconfirmed_hold")

    def test_repeats_are_retained_and_contexts_not_pooled(self):
        acts = pd.DataFrame([activity(), activity(activity_id=2, standard_value="100"),
                             activity(activity_id=3, assay_chembl_id="A2", document_chembl_id="D2"),
                             activity(activity_id=4, standard_relation=">")])
        assays = pd.DataFrame([assay(), assay(assay_chembl_id="A2", document_chembl_id="D2")])
        mols = pd.DataFrame([{"molecule_chembl_id": "M1", "canonical_smiles": "Cc1ccccc1", "molecule_type": "Small molecule"}])
        docs = pd.DataFrame([{"document_chembl_id": d, "doi": None, "pubmed_id": "12345", "title": "test"} for d in ("D1", "D2")])
        result = build_frames(acts, assays, mols, docs)
        self.assertEqual(len(result["activity_audit"]), 4)
        self.assertEqual(len(result["candidate_measurements"]), 3)
        repeats = result["repeat_contexts"]
        self.assertEqual(len(repeats), 1)
        self.assertEqual(repeats.iloc[0].measurements, 2)
        self.assertAlmostEqual(repeats.iloc[0].pIC50_span, 1)
        self.assertEqual(result["manual_review_queue"].reviewer.tolist(), ["", ""])

    def test_existing_review_work_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "audit"
            out.mkdir()
            note = out / "manual_review_queue.csv"
            note.write_text("사람이 검토한 기록")
            with self.assertRaisesRegex(ValueError, "보호"), patch("egfr_lab.data.audit.verify_collection") as verify:
                audit(Path(folder) / "raw", output_dir=out, report_dir=Path(folder) / "reports")
            verify.assert_not_called()
            self.assertEqual(note.read_text(), "사람이 검토한 기록")


if __name__ == "__main__":
    unittest.main()
