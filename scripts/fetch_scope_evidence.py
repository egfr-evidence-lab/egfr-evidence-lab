"""적용 범위 검토용 공식 메타데이터·논문 XML·특허 원 구조 그림 확보."""

from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import re

from fetch_wt_expansion import fetch_one
from review_patent_assay import TableRows


ROOT = Path(__file__).resolve().parents[1]


class RowImages(TableRows):
    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        if tag == "img" and self.cell is not None:
            self.cell.append(" IMAGE:" + dict(attrs).get("src", "") + " ")


def image_sources():
    html = (ROOT/"data/raw/main_cohort_sources_20261020/US11155546B2.html").read_text()
    sources = []
    for chunk in re.split(r"(?=<heading\b)", html):
        heading = re.match(r"<heading[^>]*>(.*?)</heading>",chunk,re.S)
        if heading:
            key = re.search(r"\((G-(?:2|3|7))\)",heading[1])
            if key:
                urls = re.findall(r'<img[^>]+src="([^"]+)"',chunk)
                sources.append((f"{key[1]}_scheme.png",urls[0],"png"))
    chunks = re.findall(r"<tables\b.*?</tables>",html,re.S)
    parser = RowImages()
    parser.feed(chunks[0])
    for row in parser.rows:
        if len(row)==7 and row[1] in {"G-14","G-33","G-41","G-51","G-54"}:
            for column in [4,5]:
                urls = re.findall(r"IMAGE:(\S+)",row[column])
                for index,url in enumerate(urls):
                    sources.append((f"{row[1]}_column{column}_{index}.png",url,"png"))
    parser = RowImages()
    parser.feed(chunks[1])
    for row in parser.rows:
        if len(row)==3 and re.search(r"ample\s+(109|114)$",row[0]):
            number = re.search(r"(\d+)$",row[0])[1]
            url = re.search(r"IMAGE:(\S+)",row[1])[1]
            sources.append((f"G-{number}_structure.png",url,"png"))
    return sources


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",default="data/raw/scope_evidence_20261020_v2")
    parser.add_argument("--supplement",action="store_true",help="OA 연결의 실제 자료 종류와 운동학 논문 본문 확인")
    args=parser.parse_args()
    out = ROOT/args.output_dir
    if out.exists():
        raise FileExistsError(f"기존 자료 보호: {out}")
    out.mkdir(parents=True)
    sources = [
        ("ref28_openalex.json","https://api.openalex.org/works/W2976708824","json"),
        ("ref28_epmc.json","https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID%3A31560541%20AND%20SRC%3AMED&format=json&resultType=core","json"),
        ("ref28_crossref.json","https://api.crossref.org/works/10.1021/acs.jmedchem.9b00722","json"),
        ("Yang2019.xml","https://www.ebi.ac.uk/europepmc/webservices/rest/PMC6727618/fullTextXML","xml"),
        ("kinetics2024.xml","https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11089659/fullTextXML","xml"),
    ] + image_sources()
    if args.supplement:
        sources=[
            ("ref28_oa_link.html","https://doi.org/10.7270/q21v5jfw","html"),
            ("ref28_datacite.json","https://api.datacite.org/dois/10.7270/q21v5jfw","json"),
            ("kinetics2024.html","https://pmc.ncbi.nlm.nih.gov/articles/PMC11089659/","html"),
        ]
    records=[]
    for source in sources:
        record=fetch_one(source,out)
        if source[2]=="png" and record.get("path"):
            record["content_candidate"]=(ROOT/record["path"]).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        records.append(record)
    (out/"manifest.json").write_text(json.dumps({"created_at_utc":datetime.now(timezone.utc).isoformat(),
        "scope":"원문·공식 메타데이터·원 구조 그림의 읽기 전용 접근; 접근 성공은 학습 승인 아님", "sources":records},ensure_ascii=False,indent=2)+"\n")
    if not any(record.get("http_status")==200 for record in records):
        raise RuntimeError("네트워크·DNS 연결 실패")


if __name__=="__main__":
    main()
