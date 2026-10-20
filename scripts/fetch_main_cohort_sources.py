"""주 코호트 후보의 공개 원문·공식 record·ACS SI를 보존한다."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import httpx

from fetch_wt_expansion import fetch_one


ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    ("US11155546B2.html", "https://patents.google.com/patent/US11155546B2/en", "html"),
    ("US8846699B2.html", "https://patents.google.com/patent/US8846699B2/en", "html"),
    ("US9987276B2.html", "https://patents.google.com/patent/US9987276B2/en", "html"),
    ("pv3872.html", "https://www.thermofisher.com/proteins/product/Human-EGFR-ErbB1-GST-Tag-Recombinant-Protein/PV3872", "html"),
]
DOCUMENTS = ["CHEMBL5728771", "CHEMBL3638799", "CHEMBL4033795", "CHEMBL1140899", "CHEMBL5727085"]
DOIS = ["10.1021/acs.jmedchem.7b01612", "10.1021/jm800829v"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(client, url, path, records, body=None):
    response = client.post(url, json=body) if body is not None else client.get(url)
    path.write_bytes(response.content)
    records.append({"url": url, "method": "POST" if body is not None else "GET",
                    "request_json": body, "http_status": response.status_code,
                    "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                    "path": str(path.relative_to(ROOT)), "sha256": digest(path),
                    "protocol_reviewed": False})
    response.raise_for_status()
    return response.json()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="data/raw/main_cohort_sources_20261020")
    parser.add_argument("--followup", action="store_true", help="다음 WT 후보 3개와 앞선 논문의 CSV·XLS 자료 확보")
    parser.add_argument("--main-text", action="store_true", help="공개 본문과 공식 XML 접근 점검")
    parser.add_argument("--reference", action="store_true", help="2023 논문이 명시한 2019 실험법 원문·SI 확보")
    args = parser.parse_args()
    out = ROOT / args.output_dir
    if out.exists():
        raise FileExistsError(f"기존 자료 보호: {out}")
    out.mkdir(parents=True)
    records = []
    failures = []
    if args.main_text:
        for source in [
            ("PMC9969398.html", "https://pmc.ncbi.nlm.nih.gov/articles/PMC9969398/", "html"),
            ("PMC9969398.xml", "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9969398/fullTextXML", "xml"),
            ("jm2c01434.html", "https://pubs.acs.org/doi/10.1021/acs.jmedchem.2c01434", "html"),
            ("jm3c02302.html", "https://pubs.acs.org/doi/10.1021/acs.jmedchem.3c02302", "html"),
        ]:
            records.append(fetch_one(source, out))
        (out / "manifest.json").write_text(json.dumps({"created_at_utc": datetime.now(timezone.utc).isoformat(),
            "scope": "공개 본문 접근; 접근 성공은 조건·수치 검증 아님", "sources": records}, ensure_ascii=False, indent=2)+"\n")
        if not any(record.get("http_status") == 200 for record in records):
            raise RuntimeError("공개 본문 요청 실패: 네트워크 확인 필요")
        return
    sources = [] if args.followup else SOURCES
    documents = ["CHEMBL5380802", "CHEMBL5543120", "CHEMBL4038351"] if args.followup else DOCUMENTS
    dois = ["10.1021/acs.jmedchem.2c01434", "10.1021/acs.jmedchem.3c02302", "10.1021/acs.jmedchem.7b00515", DOIS[0]] if args.followup else DOIS
    if args.reference:
        sources = [
            ("ref28_repository.html", "https://ir.nhri.edu.tw/handle/3990099045/12290", "html"),
            ("ref28.pdf", "https://ir.nhri.edu.tw/bitstream/3990099045/12290/1/NBP2019112001.pdf", "pdf"),
        ]
        documents = []
        dois = ["10.1021/acs.jmedchem.9b00722"]
    for source in sources:
        records.append(fetch_one(source, out))
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for document in documents:
            url = f"https://www.ebi.ac.uk/chembl/api/data/compound_record.json?document_chembl_id={document}&limit=1000"
            page = 0
            try:
                while url:
                    item = save_json(client, url, out / f"{document}_records_{page}.json", records)
                    next_page = item["page_meta"]["next"]
                    url = "https://www.ebi.ac.uk" + next_page if next_page and next_page.startswith("/") else next_page
                    page += 1
                    time.sleep(.3)
                print(f"공식 record {document}: {page}페이지", flush=True)
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                failures.append({"document": document, "error": str(exc)})
        for doi in dois:
            stem = doi.split("/")[-1].replace(".", "_")
            try:
                items = save_json(client, "https://api.figshare.com/v2/articles/search",
                                  out / f"{stem}_search.json", records,
                                  {"resource_doi": doi, "page_size": 30})
                for item in items:
                    detail = save_json(client, item["url"], out / f"figshare_{item['id']}.json", records)
                    if detail.get("resource_doi", "").lower() != doi.lower():
                        raise ValueError("SI 원 논문 DOI 불일치")
                    for file in detail.get("files", []):
                        suffix = Path(file["name"]).suffix.lower()
                        if suffix in {".pdf", ".csv", ".xls", ".xlsx"}:
                            # 이미 받은 앞선 PDF는 새 batch에서 중복 다운로드하지 않는다.
                            if args.followup and doi == DOIS[0] and suffix == ".pdf":
                                continue
                            kind = "pdf" if suffix == ".pdf" else "binary"
                            result = fetch_one((f"figshare_{file['id']}{suffix}", file["download_url"], kind), out)
                            result.update(resource_doi=doi, license=detail.get("license"),
                                          provider_md5=file.get("computed_md5"))
                            if result.get("http_status") == 200:
                                result["provider_md5_matches"] = hashlib.md5((ROOT / result["path"]).read_bytes()).hexdigest() == file["computed_md5"]
                                if kind == "binary":
                                    result["content_candidate"] = result["provider_md5_matches"]
                            records.append(result)
                            time.sleep(1)
                print(f"공개 SI 검색 {doi}: {len(items)}개", flush=True)
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                failures.append({"doi": doi, "error": str(exc)})
    (out / "manifest.json").write_text(json.dumps({
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "공개 원문 접근·보존; 다운로드는 학습 승인 아님",
        "sources": records, "failures": failures,
    }, ensure_ascii=False, indent=2) + "\n")
    if not any(record.get("http_status") == 200 for record in records):
        raise RuntimeError("공개 자료 수집 실패: 네트워크·DNS 권한 확인 필요")


if __name__ == "__main__":
    main()
