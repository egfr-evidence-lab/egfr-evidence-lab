"""중단·누락·중복·변조 시 전체 수집 성공을 잘못 보고하지 않는지 검사한다."""

import json
from pathlib import Path
import tempfile
import unittest

try:
    import httpx
    import pandas as pd
    from egfr_lab.data.chembl import ChEMBLClient, BASE, url_for
    from egfr_lab.data.collection import collect, verify_collection
    from egfr_lab.data.store import CollectionError, RunStore, atomic_json, digest, exclusive_run
    HAVE_P0 = True
except ImportError:
    HAVE_P0 = False


class FakeChEMBL:
    def __init__(self):
        self.calls = []
        self.failures = 0
        self.duplicate = False
        self.missing = False
        self.changed_release = False
        self.bad_next = False
        self.bad_count = False
        self.status_calls = 0
        self.activities = [
            {"activity_id": i, "molecule_chembl_id": "CHEMBL1" if i < 30 else "CHEMBL2",
             "assay_chembl_id": "CHEMBL11" if i < 30 else "CHEMBL12",
             "document_chembl_id": "CHEMBL21" if i < 30 else None,
             "target_chembl_id": "CHEMBL203", "target_organism": "Homo sapiens", "standard_type": "IC50",
             "standard_relation": relation, "standard_value": value, "standard_units": "nM"}
            for i, relation, value in [(10, "=", "10"), (20, ">", "1000"), (30, None, None)]]
        self.assays = [{"assay_chembl_id": key, "target_chembl_id": "CHEMBL203", "description": "합성 실험",
                        "document_chembl_id": doc, "variant_sequence": None, "confidence_score": 9}
                       for key, doc in [("CHEMBL11", "CHEMBL21"), ("CHEMBL12", "CHEMBL22")]]
        self.molecules = [{"molecule_chembl_id": key, "molecule_structures": {"canonical_smiles": smi},
                           "molecule_hierarchy": {"parent_chembl_id": key}}
                          for key, smi in [("CHEMBL1", "CCO"), ("CHEMBL2", "c1ccccc1")]]
        self.documents = [{"document_chembl_id": key, "title": "합성 자료", "year": 2020,
                           "pubmed_id": 12345 if key == "CHEMBL21" else None}
                          for key in ("CHEMBL21", "CHEMBL22")]

    def __call__(self, request):
        self.calls.append(str(request.url))
        path = request.url.path.rsplit("/", 1)[-1]
        if path == "status.json":
            self.status_calls += 1
            return httpx.Response(200, json={"status": "UP", "chembl_db_version":
                                           "ChEMBL_38" if self.changed_release and self.status_calls > 1 else "ChEMBL_37",
                                           "chembl_release_date": "2026-05-01"})
        if path == "CHEMBL203.json":
            return httpx.Response(200, json={"target_chembl_id": "CHEMBL203", "organism": "Homo sapiens"})
        kind = path.split(".")[0]
        plural, key = {"activity": ("activities", "activity_id"), "assay": ("assays", "assay_chembl_id"),
                       "molecule": ("molecules", "molecule_chembl_id"), "document": ("documents", "document_chembl_id")}[kind]
        rows = [dict(r) for r in getattr(self, plural)]
        params = request.url.params
        if params.get(key+"__in"):
            wanted = params[key+"__in"].split(",")
            rows = [r for r in rows if r[key] in wanted]
        if self.missing and kind == "molecule":
            rows = []
        offset, limit = int(params.get("offset", "0")), int(params.get("limit", "2"))
        if kind == "activity" and offset == 2 and self.failures:
            self.failures -= 1
            return httpx.Response(503, json={"error": "일시 오류"})
        page = rows[offset:offset+limit]
        if self.duplicate and kind == "activity" and offset == 2:
            page[0][key] = rows[0][key]
        following = str(request.url.copy_set_param("offset", offset+len(page))) if offset+len(page) < len(rows) else None
        if self.bad_next and kind == "activity" and following:
            following = "https://example.org/wrong.json?offset=2"
        total = len(rows) + (1 if self.bad_count and kind == "activity" else 0)
        return httpx.Response(200, json={plural: page, "page_meta": {"offset": offset, "limit": limit,
                                                                    "total_count": total, "next": following}})


@unittest.skipUnless(HAVE_P0, "P0 extra 설치 시 실행하는 수집기 검사")
class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run = self.root / "run"
        self.server = FakeChEMBL()
        self.client = httpx.Client(transport=httpx.MockTransport(self.server))
        self.addCleanup(self.client.close)
        self.addCleanup(self.temp.cleanup)

    def collect(self, **kwargs):
        return collect(self.run, page_size=2, batch_size=2, workers=1, client=self.client,
                       sleeper=lambda delay: None, derived_dir=self.root / "tables", report_dir=self.root / "reports", **kwargs)

    def manifest(self):
        return json.loads((self.run / "manifest.json").read_text())

    def test_full_collection_preserves_repeated_molecule_censored_null_and_assay_document(self):
        result = self.collect()
        self.assertTrue(result["passed"])
        self.assertEqual(result["state"], "complete")
        self.assertEqual(result["summary"]["activities"], 3)
        self.assertEqual(result["summary"]["molecules"], 2)
        self.assertEqual(result["summary"]["documents"], 2)  # Includes the assay-only document.
        self.assertEqual(result["summary"]["relations"], {"<null>": 1, "=": 1, ">": 1})
        self.assertEqual(result["summary"]["null_reference_counts"]["document_chembl_id"], 1)
        frame = pd.read_parquet(self.root / "tables/measurements_joined.parquet")
        self.assertEqual(len(frame), 3)
        self.assertEqual(frame["molecule_chembl_id"].tolist(), ["CHEMBL1", "CHEMBL1", "CHEMBL2"])
        documents = pd.read_parquet(self.root / "tables/documents.parquet")
        self.assertEqual(documents.loc[0, "pubmed_id"], "12345")
        self.assertTrue(pd.isna(documents.loc[1, "pubmed_id"]))
        self.assertTrue(verify_collection(self.run)["passed"])

    def test_interrupted_request_resumes_from_verified_cache(self):
        self.server.failures = 3
        with self.assertRaises(CollectionError):
            self.collect()
        self.assertEqual(self.manifest()["state"], "failed")
        first_page = next(url for url in self.server.calls if "activity.json" in url and "limit=2" in url)
        self.assertEqual(self.server.calls.count(first_page), 1)
        result = self.collect(resume=True)
        self.assertTrue(result["passed"])
        self.assertEqual(self.server.calls.count(first_page), 1)
        self.assertEqual(len(self.manifest()["attempts"]), 2)

    def test_preview_does_not_claim_full_collection(self):
        result = self.collect(max_pages=1)
        self.assertEqual(result["state"], "preview_complete")
        self.assertEqual(result["summary"]["activities"], 2)
        self.assertEqual(result["summary"]["api_total_count"], 3)
        with self.assertRaises(CollectionError):
            self.collect(resume=True)  # Cannot silently change preview scope into full scope.

    def test_duplicate_activity_fails(self):
        self.server.duplicate = True
        with self.assertRaisesRegex(CollectionError, "중복"):
            self.collect()
        self.assertEqual(self.manifest()["state"], "failed")

    def test_missing_detail_id_fails(self):
        self.server.missing = True
        with self.assertRaisesRegex(CollectionError, "누락"):
            self.collect()
        self.assertEqual(self.manifest()["state"], "failed")

    def test_changed_release_fails(self):
        self.server.changed_release = True
        with self.assertRaisesRegex(CollectionError, "release"):
            self.collect()
        self.assertEqual(self.manifest()["state"], "failed")

    def test_resume_rejects_different_release_before_reusing_pages(self):
        self.server.failures = 3
        with self.assertRaises(CollectionError):
            self.collect()
        self.server.changed_release = True
        before = len(self.server.calls)
        with self.assertRaisesRegex(CollectionError, "release"):
            self.collect(resume=True)
        self.assertEqual(len(self.server.calls)-before, 1)

    def test_wrong_next_host_fails(self):
        self.server.bad_next = True
        with self.assertRaisesRegex(CollectionError, "경로"):
            self.collect()

    def test_incorrect_total_fails(self):
        self.server.bad_count = True
        with self.assertRaisesRegex(CollectionError, "건수"):
            self.collect()

    def test_raw_corruption_detected_offline(self):
        self.collect()
        record = self.manifest()["requests"]["activities_000000"]
        path = self.run / record["file"]
        path.write_bytes(path.read_bytes()+b" ")
        with self.assertRaisesRegex(CollectionError, "해시"):
            verify_collection(self.run)

    def test_export_content_is_compared_with_raw_even_if_hash_is_updated(self):
        self.collect()
        manifest = self.manifest()
        record = manifest["exports"]["joined"]
        path = self.run / record["path"]
        frame = pd.read_parquet(path)
        frame.loc[0, "standard_value"] = "999"
        frame.to_parquet(path, index=False)
        record.update(bytes=path.stat().st_size, sha256=digest(path.read_bytes()))
        atomic_json(self.run / "manifest.json", manifest)
        with self.assertRaisesRegex(CollectionError, "내용"):
            verify_collection(self.run)

    def test_failed_run_is_not_verifiable_as_complete(self):
        self.server.failures = 3
        with self.assertRaises(CollectionError):
            self.collect()
        with self.assertRaisesRegex(CollectionError, "완료"):
            verify_collection(self.run)

    def test_same_run_lock_is_exclusive(self):
        with exclusive_run(self.run):
            with self.assertRaisesRegex(CollectionError, "프로세스"):
                self.collect()

    def test_existing_unowned_output_is_not_overwritten(self):
        folder = self.root / "tables"
        folder.mkdir()
        marker = folder / "important.txt"
        marker.write_text("기존 사용자 파일")
        with self.assertRaisesRegex(CollectionError, "기존 분석 폴더"):
            self.collect()
        self.assertEqual(marker.read_text(), "기존 사용자 파일")


@unittest.skipUnless(HAVE_P0, "P0 extra 설치 시 실행하는 HTTP 검사")
class RetryTests(unittest.TestCase):
    def test_retry_after_and_non_retryable_400(self):
        with tempfile.TemporaryDirectory() as directory:
            store = RunStore(Path(directory) / "run", {"test": True})
            calls, waits = [], []
            def handler(request):
                calls.append(request)
                if len(calls) == 1:
                    return httpx.Response(429, headers={"Retry-After": "2"})
                return httpx.Response(200, json={"ok": True})
            with httpx.Client(transport=httpx.MockTransport(handler)) as client:
                api = ChEMBLClient(store, client, sleeper=waits.append)
                self.assertEqual(api.get("retry", url_for("status")), {"ok": True})
            self.assertEqual(waits, [2])
            count = []
            with httpx.Client(transport=httpx.MockTransport(lambda request: count.append(1) or httpx.Response(400))) as client:
                with self.assertRaises(CollectionError):
                    ChEMBLClient(store, client, sleeper=waits.append).get("bad", url_for("status"))
            self.assertEqual(len(count), 1)

    def test_invalid_json_is_retried_not_saved_as_success(self):
        with tempfile.TemporaryDirectory() as directory:
            store = RunStore(Path(directory) / "run", {})
            count = []
            def handler(request):
                count.append(1)
                return httpx.Response(200, content=b"{broken" if len(count) == 1 else b'{"ok":true}')
            with httpx.Client(transport=httpx.MockTransport(handler)) as client:
                value = ChEMBLClient(store, client, sleeper=lambda delay: None).get("json", url_for("status"))
            self.assertTrue(value["ok"])
            self.assertEqual(len(count), 2)
            self.assertEqual(len(store.manifest["errors"]), 1)


if __name__ == "__main__":
    unittest.main()
