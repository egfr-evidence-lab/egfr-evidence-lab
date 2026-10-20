"""포트폴리오 적합성 검토에 사용한 공개 공고·논문 메타데이터를 보존한다."""

from datetime import datetime, timezone
from html.parser import HTMLParser
import argparse
import hashlib
import json
import math
from pathlib import Path

import httpx
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/portfolio_sources_20261020"
SOURCES = {
    "ai_job.html": "https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=55253770",
    "ai_job_detail.html": "https://www.saramin.co.kr/zf_user/jobs/relay/view-detail?rec_idx=55253770",
    "company_paper_metadata.json": "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID%3A41635121%20AND%20SRC%3AMED&format=json&resultType=core",
    "sgc_probe_criteria.html": "https://www.sgc-unc.org/main-st",
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for name, url in SOURCES.items():
            path = OUT / name
            if path.exists():
                status, final_url = "cached", url
            else:
                response = client.get(url)
                status, final_url = response.status_code, str(response.url)
                if response.status_code == 200:
                    path.write_bytes(response.content)
            record = {"url": url, "final_url": final_url, "status": status}
            if path.exists():
                record.update(path=str(path.relative_to(ROOT)), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            records.append(record)
            print(f"공개 근거 {name}: {status}, 저장={path.exists()}", flush=True)
    (OUT / "manifest.json").write_text(json.dumps({"retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "sources": records}, ensure_ascii=False, indent=2) + "\n")


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.words, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1

    def handle_data(self, text):
        if not self.skip:
            self.words.append(text)


def validate():
    manifest = json.loads((OUT / "manifest.json").read_text())
    for record in manifest["sources"]:
        path = ROOT / record["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError("보관한 공개 근거의 해시가 다릅니다.")
    parser = PlainText()
    parser.feed((OUT / "ai_job_detail.html").read_text())
    job = " ".join(" ".join(parser.words).split())
    preferences = ["딥러닝 프레임워크", "의약·바이오 데이터", "논문 구현 및 재현", "클라우드 환경", "Agentic AI"]
    qualifications = ["Python 기반 분석", "통계적 검증", "학력무관", "데이터 전처리"]
    if any(term not in job for term in preferences + qualifications) or "AI 연구원" not in job:
        raise ValueError("AI 공고의 실제 우대·자격 본문을 확인하지 못했습니다.")
    metadata = json.loads((OUT / "company_paper_metadata.json").read_text())["resultList"]["result"]
    if len(metadata) != 1 or metadata[0]["id"] != "41635121" or metadata[0]["doi"].lower() != "10.1002/ardp.70193":
        raise ValueError("회사 문헌 PMID·DOI 연결이 다릅니다.")
    abstract = metadata[0].get("abstractText", "")
    if any(term not in abstract for term in ("HBE-843", "26-103", "1.9-18", "90%")):
        raise ValueError("회사 문헌 초록의 보고값을 다시 확인해야 합니다.")
    pilot_path = ROOT / "data/interim/cohort_review_20261020/context_pilot.csv"
    wt_path = ROOT / "data/interim/cohort_review_20261020/wt_measurement_decisions.csv"
    pilot = pd.read_csv(pilot_path, dtype=str, keep_default_na=False)
    wt = pd.read_csv(wt_path, dtype=str, keep_default_na=False)
    phases = json.loads((ROOT / "configs/project.json").read_text())["phases"]
    implementation_files = [str(p.relative_to(ROOT)) for d in ("src/egfr_lab/modeling", "src/egfr_lab/agent", "deployment", "artifacts")
                            for p in (ROOT / d).rglob("*") if p.is_file() and "__pycache__" not in str(p)]
    result = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "passed": True,
              "ai_job_id": "55253770", "preferred_skills_confirmed": preferences,
              "qualifications_confirmed": qualifications,
              "company_paper_identity": {k: metadata[0][k] for k in ("id", "doi", "title", "pubYear")},
              "company_paper_review_scope": "출판사 초록·Europe PMC 메타데이터; 본문/SI 전수 검토 아님",
              "wt_measurements": len(wt), "wt_below_100nM": int(pd.to_numeric(wt.standard_value).lt(100).sum()),
              "pilot_measurements": len(pilot), "pilot_below_100nM": int(pd.to_numeric(pilot.standard_value).lt(100).sum()),
              "10nM_pIC50": -math.log10(10e-9), "100nM_pIC50": -math.log10(100e-9),
              "phases": phases, "implementation_files_checked": implementation_files,
              "inputs_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in (pilot_path, wt_path, ROOT / "configs/project.json", OUT / "manifest.json")},
              "source_files_hashed": len(manifest["sources"]),
              "claims_not_assessed": ["기업 채용 통과 여부", "사용자 도메인 이해도", "임상 유효성", "새 모델 성능"],
              "universal_egfr_numeric_threshold_claimed": False}
    (ROOT / "reports/portfolio_fit_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="보관한 원문만 검증")
    args = parser.parse_args()
    if not args.offline:
        main()
    validate()
