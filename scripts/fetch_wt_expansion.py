"""보류 WT 문헌의 공개 원문·SI를 새 실행 폴더에 보존한다.

접근 성공은 방법·수치 확인과 다르다. 실패 응답도 상태·해시와 함께 기록한다.
기존 실행 매니페스트와 파일을 덮어쓰지 않는다.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import httpx


ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    ("PMC10184309.html", "https://pmc.ncbi.nlm.nih.gov/articles/PMC10184309/", "html"),
    ("PMC11089552.html", "https://pmc.ncbi.nlm.nih.gov/articles/PMC11089552/", "html"),
    ("PMC4027470.html", "https://pmc.ncbi.nlm.nih.gov/articles/PMC4027470/", "html"),
    ("PMC4777322.html", "https://pmc.ncbi.nlm.nih.gov/articles/PMC4777322/", "html"),
    ("c3md00118k.html", "https://pubs.rsc.org/en/content/articlehtml/2013/md/c3md00118k", "html"),
    ("c2md20078c.html", "https://pubs.rsc.org/en/content/articlehtml/2012/md/c2md20078c", "html"),
    ("c3md00118k_si.pdf", "https://www.rsc.org/suppdata/md/c3/c3md00118k/c3md00118k.pdf", "pdf"),
    ("c2md20078c_si.pdf", "https://www.rsc.org/suppdata/md/c2/c2md20078c/c2md20078c.pdf", "pdf"),
    ("jm401045n.html", "https://pubs.acs.org/doi/10.1021/jm401045n", "html"),
    ("jm5014659.html", "https://pubs.acs.org/doi/10.1021/jm5014659", "html"),
    ("jm401045n_si.pdf", "https://pubs.acs.org/doi/suppl/10.1021/jm401045n/suppl_file/jm401045n_si_001.pdf", "pdf"),
    ("jm5014659_si.pdf", "https://pubs.acs.org/doi/suppl/10.1021/jm5014659/suppl_file/jm5014659_si_001.pdf", "pdf"),
    ("qin2016.html", "https://doi.org/10.1016/j.bmc.2016.01.003", "html"),
    ("cheng2014.html", "https://doi.org/10.1016/j.bmc.2014.10.038", "html"),
]
SI_SOURCES = [
    ("ml2c00514_si.pdf", "https://pmc.ncbi.nlm.nih.gov/articles/instance/10184309/bin/ml2c00514_si_001.pdf", "pdf"),
    ("ml3c00425_si.pdf", "https://pmc.ncbi.nlm.nih.gov/articles/instance/11089552/bin/ml3c00425_si_001.pdf", "pdf"),
    ("ml4002437_si.pdf", "https://pmc.ncbi.nlm.nih.gov/articles/instance/4027470/bin/ml4002437_si_001.pdf", "pdf"),
    ("c3md00118k_si.pdf", "https://www.rsc.org/suppdata/c3/md/c3md00118k/c3md00118k.pdf", "pdf"),
    ("c2md20078c_si.pdf", "https://www.rsc.org/suppdata/c2/md/c2md20078c/c2md20078c.pdf", "pdf"),
]
FIGSHARE_DOIS = ["10.1021/jm401045n", "10.1021/jm5014659",
                 "10.1021/acsmedchemlett.2c00514", "10.1021/acsmedchemlett.3c00425",
                 "10.1021/ml4002437"]
ADDENDUM_SOURCES = [
    ("pv3872.html", "https://www.thermofisher.com/proteins/product/Human-EGFR-ErbB1-GST-Tag-Recombinant-Protein/PV3872", "html"),
    ("pv3872_coa.pdf", "https://documents.thermofisher.com/TFS-Assets/LSG/certificate/Certificates%20of%20Analysis/1489094K_PV3872.pdf", "pdf"),
    ("carna_08_115.pdf", "https://www.carnabio.com/profiling_pdf/p108.pdf", "pdf"),
    ("zhou_records.json", "https://www.ebi.ac.uk/chembl/api/data/compound_record.json?document_chembl_id=CHEMBL2434822&limit=1000", "json"),
    ("pemberton_records.json", "https://www.ebi.ac.uk/chembl/api/data/compound_record.json?document_chembl_id=CHEMBL5634191&limit=1000", "json"),
    ("grabe_records.json", "https://www.ebi.ac.uk/chembl/api/data/compound_record.json?document_chembl_id=CHEMBL5257147&limit=1000", "json"),
    ("c3md00118k_si1.pdf", "https://www.rsc.org/suppdata/c3/md/c3md00118k/c3md00118k1.pdf", "pdf"),
    ("c2md20078c_si1.pdf", "https://www.rsc.org/suppdata/c2/md/c2md20078c/c2md20078c1.pdf", "pdf"),
]
LARGER_SOURCES = [
    ("PMC2880455.html", "https://pmc.ncbi.nlm.nih.gov/articles/PMC2880455/", "html"),
    ("apsel_nature.html", "https://www.nature.com/articles/nchembio.117", "html"),
    ("apsel_metadata.json", "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID%3A18849971%20AND%20SRC%3AMED&format=json&resultType=core", "json"),
    ("US11066414B2.html", "https://patents.google.com/patent/US11066414B2/en", "html"),
    ("apsel_records.json", "https://www.ebi.ac.uk/chembl/api/data/compound_record.json?document_chembl_id=CHEMBL1240340&limit=1000", "json"),
]
FOLLOWUP_SOURCES = [
    ("patent_records.json", "https://www.ebi.ac.uk/chembl/api/data/compound_record.json?document_chembl_id=CHEMBL5728555&limit=1000", "json"),
    ("apsel_main_lab.pdf", "https://shokatlab.ucsf.edu/pdfs/18849971.pdf", "pdf"),
    ("apsel_si_pmc.pdf", "https://pmc.ncbi.nlm.nih.gov/articles/instance/2880455/bin/NIHMS69615-supplement-1.pdf", "pdf"),
    ("apsel_si_publisher.pdf", "https://static-content.springer-cdn.com/esm/art%3A10.1038%2Fnchembio.117/MediaObjects/41589_2008_BFnchembio117_MOESM1_ESM.pdf", "pdf"),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch_one(source, out):
    name, url, kind = source
    path = out / name
    record = {"name": name, "url": url, "expected_kind": kind,
              "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
              "protocol_reviewed": False}
    if path.exists():
        raise FileExistsError(f"기존 파일 보호: {path}")
    try:
        with httpx.Client(timeout=25, follow_redirects=True) as client:
            response = client.get(url)
        path.write_bytes(response.content)
        body = response.text.lower() if kind == "html" else ""
        challenge = any(term in body for term in ("checking your browser", "verify you are human", "just a moment..."))
        if kind == "pdf":
            valid = response.content.startswith(b"%PDF")
        elif kind == "json":
            try:
                response.json()
                valid = True
            except ValueError:
                valid = False
        else:
            valid = len(response.content) > 15000 and not challenge
        record.update(http_status=response.status_code, final_url=str(response.url),
                      content_type=response.headers.get("content-type"), size=len(response.content),
                      path=str(path.relative_to(ROOT)), sha256=sha(path),
                      content_candidate=bool(response.status_code == 200 and valid),
                      challenge_detected=challenge)
    except httpx.HTTPError as exc:
        record.update(error_type=type(exc).__name__, error=str(exc))
    print(f"{name}: HTTP={record.get('http_status')}, 원문 후보={record.get('content_candidate', False)}", flush=True)
    return record


def fetch_figshare(out):
    """공개 SI를 원 논문 DOI와 대조해 가져오는 읽기 전용 API."""
    records = []
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for doi in FIGSHARE_DOIS:
            query_url = "https://api.figshare.com/v2/articles/search"
            body = {"resource_doi": doi, "page_size": 10}
            time.sleep(1.05)
            response = client.post(query_url, json=body)
            stem = doi.split("/")[-1].replace(".", "_")
            path = out / (stem + "_figshare_search.json")
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(response.content)
            record = {"url": query_url, "method": "POST", "request_json": body,
                      "http_status": response.status_code, "path": str(path.relative_to(ROOT)),
                      "sha256": sha(path), "protocol_reviewed": False}
            records.append(record)
            response.raise_for_status()
            results = response.json()
            print(f"Figshare 공개 검색 {doi}: {len(results)}개", flush=True)
            for item in results:
                time.sleep(1.05)
                url = item["url"]
                detail_response = client.get(url)
                detail_response.raise_for_status()
                detail = detail_response.json()
                if detail.get("resource_doi", "").lower() != doi.lower():
                    raise ValueError(f"SI 원 논문 DOI 불일치: {doi}")
                detail_path = out / f"figshare_{item['id']}.json"
                if detail_path.exists():
                    raise FileExistsError(detail_path)
                detail_path.write_bytes(detail_response.content)
                records.append({"url": url, "http_status": detail_response.status_code,
                                "path": str(detail_path.relative_to(ROOT)), "sha256": sha(detail_path),
                                "resource_doi": doi, "license": detail.get("license"),
                                "protocol_reviewed": False})
                for file in detail.get("files", []):
                    if file["name"].lower().endswith(".pdf"):
                        time.sleep(1.05)
                        records.append(fetch_one((f"figshare_{file['id']}.pdf", file["download_url"], "pdf"), out))
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="data/raw/wt_expansion_20261020_v1")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--batch", choices=["initial", "supplement", "addendum", "larger", "followup"], default="initial")
    args = parser.parse_args()
    out = ROOT / args.output_dir
    manifest_path = out / "manifest.json"
    if args.offline or manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        for record in manifest["sources"]:
            if record.get("path") and sha(ROOT / record["path"]) != record["sha256"]:
                raise ValueError(f"원문 해시 불일치: {record['name']}")
        print(f"기존 실행 보호·해시 확인: {len(manifest['sources'])}개 요청")
        return
    out.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        sources = {"initial": SOURCES, "supplement": SI_SOURCES, "addendum": ADDENDUM_SOURCES,
                   "larger": LARGER_SOURCES, "followup": FOLLOWUP_SOURCES}[args.batch]
        records = list(pool.map(lambda source: fetch_one(source, out), sources))
    if not any("http_status" in record for record in records):
        raise RuntimeError("모든 네트워크 요청 실패; 실행 환경의 DNS·네트워크 권한 확인 필요")
    if args.batch == "supplement":
        records.extend(fetch_figshare(out))
    manifest_path.write_text(json.dumps({
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "공개 원문·SI 접근 점검; 다운로드 성공은 방법 검토 승인 아님",
        "url_policy": "공식 PMC·출판사 URL; SI 파일명 후보는 HTTP·파일 형식으로 확인",
        "sources": records,
    }, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
