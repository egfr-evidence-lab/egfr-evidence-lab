"""Small, archived API inspection; not a complete dataset collector.

Run from the project root with .venv/bin/python scripts/probe_chembl_api.py.
Uses only the standard library. Every response is saved with its URL and hash.
"""

import argparse
import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


BASE = "https://www.ebi.ac.uk/chembl/api/data/"
ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", type=Path, help="기존 소량 조회 폴더에서 성공한 응답을 재사용")
    args = parser.parse_args()
    started = datetime.now(timezone.utc)
    if args.resume:
        output = args.resume.resolve()
        old = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        started = datetime.fromisoformat(old["started_at_utc"])
        records = old["requests"]
    else:
        output = ROOT / "data/raw" / started.strftime("api_probe_%Y%m%dT%H%M%S%fZ")
        output.mkdir(parents=True, exist_ok=False)
        records = []

    def fetch(name, url, params=None, is_json=True, refresh=False):
        if params:
            url += "?" + urlencode(params)
        cached = next((item for item in records if item["name"] == name), None)
        if cached and not cached.get("failed") and not refresh:
            body = (output / cached["file"]).read_bytes()
            if cached["url"] != url or hashlib.sha256(body).hexdigest() != cached["sha256"]:
                raise ValueError(f"Cached request or hash mismatch: {name}")
            return json.loads(body) if is_json else body.decode("utf-8")
        if cached:
            records.remove(cached)
        entry = {"name": name, "url": url, "attempts": []}
        for attempt in range(3):
            try:
                request = Request(url, headers={"User-Agent": "egfr-evidence-lab/0.1 API-inspection",
                                               "Accept": "application/json" if is_json else "text/plain"})
                with urlopen(request, timeout=30) as response:
                    body = response.read()
                    entry.update({"http_status": response.status, "final_url": response.url,
                                  "content_type": response.headers.get("Content-Type"),
                                  "server_date": response.headers.get("Date")})
                value = json.loads(body) if is_json else body.decode("utf-8")
                filename = name + (".json" if is_json else ".txt")
                (output / filename).write_bytes(body)
                entry.update({"file": filename, "bytes": len(body),
                              "sha256": hashlib.sha256(body).hexdigest(),
                              "retrieved_at_utc": datetime.now(timezone.utc).isoformat()})
                records.append(entry)
                print(json.dumps({"name": name, "saved": filename,
                                  "total_count": value.get("page_meta", {}).get("total_count")
                                  if is_json and isinstance(value, dict) else None}), flush=True)
                return value
            except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
                entry["attempts"].append({"attempt": attempt + 1, "error": str(exc)})
                # Invalid queries and missing endpoints should not be retried.
                if isinstance(exc, HTTPError) and 400 <= exc.code < 500 and exc.code != 429:
                    break
                if attempt < 2:
                    time.sleep(2 ** attempt)
        entry["failed"] = True
        records.append(entry)
        print(json.dumps({"name": name, "failed": entry["attempts"]}, ensure_ascii=False), flush=True)
        return None

    status_before = fetch("status_before", BASE + "status.json")
    if not status_before:
        raise SystemExit("수집 전 release 확인 실패. 다른 조회를 시작하지 않습니다.")
    release = re.fullmatch(r"ChEMBL_(\d+)", status_before["chembl_db_version"]).group(1)
    params = {"target_chembl_id": "CHEMBL203", "standard_type": "IC50",
              "target_organism": "Homo sapiens", "order_by": "activity_id", "limit": 5}
    jobs = [
        ("target", BASE + "target/CHEMBL203.json", None, True),
        ("activities_page1", BASE + "activity.json", params, True),
        ("target_by_accession", BASE + "target.json",
         {"target_components__accession": "P00533", "organism": "Homo sapiens", "limit": 20}, True),
        ("release_notes", f"https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/releases/chembl_{release}/chembl_{release}_release_notes.txt", None, False),
        ("uniprot", "https://rest.uniprot.org/uniprotkb/P00533.json", None, True),
        ("variant_assays", BASE + "assay.json",
         {"target_chembl_id": "CHEMBL203", "variant_sequence__isnull": "false", "order_by": "assay_chembl_id", "limit": 2}, True),
        ("activities_target_only", BASE + "activity.json",
         {"target_chembl_id": "CHEMBL203", "standard_type": "IC50", "limit": 1}, True),
        ("activities_exact", BASE + "activity.json",
         {**params, "standard_relation": "=", "limit": 1}, True),
        ("activities_censored", BASE + "activity.json",
         {**params, "standard_relation__in": "<,>,<=,>=", "limit": 2}, True),
        ("activity_schema", BASE + "activity/schema.json", None, True),
        ("activities_relation_missing", BASE + "activity.json",
         {**params, "standard_relation__isnull": "true", "limit": 1}, True),
        ("activities_approximate", BASE + "activity.json",
         {**params, "standard_relation": "~", "limit": 2}, True),
        ("activities_variant_ic50", BASE + "activity.json",
         {**params, "assay_variant_mutation__isnull": "false", "limit": 2}, True),
        ("europepmc_documents", "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
         {"query": "(EXT_ID:12127526 OR EXT_ID:2552117 OR EXT_ID:13678409) AND SRC:MED",
          "format": "json", "resultType": "core", "pageSize": 3}, True),
    ]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [(job[0], pool.submit(fetch, *job)) for job in jobs]
        responses = {name: future.result() for name, future in futures}
    page1 = responses.get("activities_page1")
    if page1 and page1["page_meta"].get("next"):
        responses["activities_page2"] = fetch("activities_page2", urljoin(BASE, page1["page_meta"]["next"]))
    samples = ((page1 or {}).get("activities", []) +
               (responses.get("activities_page2") or {}).get("activities", []) +
               (responses.get("activities_variant_ic50") or {}).get("activities", []))
    # Follow only a small set of identifiers already observed in the sample.
    detail_jobs = []
    for resource, key in [("assay", "assay_chembl_id"), ("molecule", "molecule_chembl_id"),
                          ("document", "document_chembl_id")]:
        for identifier in sorted({row[key] for row in samples if row.get(key)}):
            detail_jobs.append((f"{resource}_{identifier}", BASE + f"{resource}/{identifier}.json"))
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [(name, pool.submit(fetch, name, url)) for name, url in detail_jobs]
        responses.update({name: future.result() for name, future in futures})
    # Check whether the two variant assays actually have IC50 measurements;
    # the variant assay count itself includes endpoints other than IC50.
    for assay in (responses.get("variant_assays") or {}).get("assays", []):
        identifier = assay["assay_chembl_id"]
        fetch(f"variant_ic50_{identifier}", BASE + "activity.json",
              {**params, "assay_chembl_id": identifier, "limit": 1})
    status_after = fetch("status_after", BASE + "status.json", refresh=True)
    manifest = {"scope": "Small non-random API inspection; no full collection or cohort approval",
                "script": "scripts/probe_chembl_api.py",
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "started_at_utc": started.isoformat(),
                "finished_at_utc": datetime.now(timezone.utc).isoformat(),
                "status_before": status_before, "status_after": status_after,
                "release_stable": bool(status_before and status_after and
                                       status_before.get("chembl_db_version") == status_after.get("chembl_db_version") and
                                       status_before.get("chembl_release_date") == status_after.get("chembl_release_date")),
                "requests": sorted(records, key=lambda row: row["name"])}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Evidence directory: {output}", flush=True)


if __name__ == "__main__":
    main()
