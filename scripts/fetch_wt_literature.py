"""WT 6개 문헌의 Europe PMC 메타데이터·공개 XML을 출처와 함께 보존한다."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import httpx
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
OUT = ROOT / "data/raw/wt_literature_20261020"
ASSETS = {
    "allenamide_si.pdf": "https://www.rsc.org/suppdata/c7/md/c7md00571g/c7md00571g1.pdf",
    "ward_si.pdf": "https://pubs.acs.org/doi/suppl/10.1021/jm400822z/suppl_file/jm400822z_si_001.pdf",
    "landrum_curation.ipynb": "https://raw.githubusercontent.com/rinikerlab/overlapping_assays/main/ChEMBL32_OverlappingIC50s-paper.ipynb",
    "allenamide_main.html": "https://pmc.ncbi.nlm.nih.gov/articles/PMC6083791/",
    "allenamide_pmc_si.pdf": "https://pmc.ncbi.nlm.nih.gov/articles/PMC6083791/bin/MD-009-C7MD00571G-s001.pdf",
    "allenamide_compound_records.json": "https://www.ebi.ac.uk/chembl/api/data/compound_record.json?document_chembl_id=CHEMBL4257480&limit=1000",
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    candidates = ROOT / "data/interim/audit_chembl_full_20261020/candidate_measurements.csv"
    frame = pd.read_csv(candidates, dtype=str, keep_default_na=False)
    papers = frame.loc[frame.variant_screen.eq("WT"), ["document_chembl_id", "document_pubmed_id", "document_doi"]].drop_duplicates()
    audit_path = ROOT / "data/interim/audit_chembl_full_20261020/activity_audit.csv"
    audit = pd.read_csv(audit_path, dtype=str, keep_default_na=False)
    expansion = audit.loc[audit.variant_screen.eq("WT") & audit.screen_reasons.eq("species_unclear")]
    terms = [f"EXT_ID:{p}" for p in sorted(set(expansion.document_pubmed_id) - {""})]
    terms += [f'DOI:"{d}"' for d in sorted(set(expansion.loc[expansion.document_pubmed_id.eq(""), "document_doi"]) - {""})]
    ASSETS["wt_expansion_metadata.json"] = str(httpx.URL(BASE + "/search", params={"query": "(" + " OR ".join(terms) + ") AND SRC:MED", "format": "json", "resultType": "core", "pageSize": 100}))
    records, assets = [], []
    with httpx.Client(timeout=40, follow_redirects=True) as client:
        for paper in papers.to_dict("records"):
            pmid = paper["document_pubmed_id"]
            url = str(httpx.URL(BASE + "/search", params={"query": f"EXT_ID:{pmid} AND SRC:MED", "format": "json", "resultType": "core"}))
            path = OUT / (pmid + ".json")
            if not path.exists():
                response = client.get(url)
                response.raise_for_status()
                path.write_bytes(response.content)
                time.sleep(0.15)
            result = json.loads(path.read_text())["resultList"]["result"]
            if len(result) != 1 or result[0]["id"] != pmid or result[0].get("doi", "").lower() != paper["document_doi"].lower():
                raise ValueError(f"문헌 ID·DOI 연결 불일치: {pmid}")
            record = {**paper, "query_url": url, "path": str(path.relative_to(ROOT)),
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                      "pmcid": result[0].get("pmcid"), "isOpenAccess": result[0].get("isOpenAccess"),
                      "fullTextUrlList": result[0].get("fullTextUrlList"), "xml_status": "no_pmcid"}
            if record["pmcid"]:
                xml_url = BASE + "/" + record["pmcid"] + "/fullTextXML"
                xml_path = OUT / (record["pmcid"] + ".xml")
                if not xml_path.exists():
                    response = client.get(xml_url)
                    if response.status_code == 200:
                        xml_path.write_bytes(response.content)
                    record["xml_status"] = str(response.status_code)
                else:
                    record["xml_status"] = "cached"
                record["xml_url"] = xml_url
                if xml_path.exists():
                    record.update(xml_path=str(xml_path.relative_to(ROOT)), xml_sha256=hashlib.sha256(xml_path.read_bytes()).hexdigest())
            records.append(record)
            print(f"문헌 {pmid}: PMC={record['pmcid']}, XML={record['xml_status']}", flush=True)
        for name, url in ASSETS.items():
            path = OUT / name
            if path.exists():
                status = "cached"
            else:
                response = client.get(url)
                status = str(response.status_code)
                if name.endswith(".pdf"):
                    valid = response.content.startswith(b"%PDF")
                elif name.endswith(".html"):
                    valid = "EGFR kinase activity assay" in response.text
                else:
                    valid = response.text.lstrip().startswith("{")
                if response.status_code == 200 and valid:
                    path.write_bytes(response.content)
            asset = {"url": url, "status": status, "path": str(path.relative_to(ROOT)) if path.exists() else None}
            if path.exists():
                asset["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            assets.append(asset)
            print(f"공개 부속자료 {name}: {status}, 저장={path.exists()}", flush=True)
    manifest = {"retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "candidate_csv_sha256": hashlib.sha256(candidates.read_bytes()).hexdigest(),
                "activity_audit_csv_sha256": hashlib.sha256(audit_path.read_bytes()).hexdigest(),
                "source": "Europe PMC REST API 및 공식 공개 부속자료", "records": records, "assets": assets}
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
