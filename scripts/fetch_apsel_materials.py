"""Apsel 2008 공개 부속자료의 공식 경로를 점검·보존한다."""

from datetime import datetime, timezone
import argparse
import json
from pathlib import Path

from fetch_wt_expansion import fetch_one


ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    ("si_nature_legacy.pdf", "https://www.nature.com/nchembio/journal/v4/n11/extref/nchembio.117-S1.pdf", "pdf"),
    ("si_nature_legacy_under.pdf", "https://www.nature.com/nchembio/journal/v4/n11/extref/nchembio.117_S1.pdf", "pdf"),
    ("si_pmc_direct.pdf", "https://pmc.ncbi.nlm.nih.gov/articles/PMC2880455/bin/NIHMS69615-supplement-1.pdf", "pdf"),
    ("si_author.pdf", "https://shokatlab.ucsf.edu/pdfs/18849971_SI.pdf", "pdf"),
]
MIRRORS = [
    ("si_epmc.pdf", "https://europepmc.org/articles/PMC2880455/bin/NIHMS69615-supplement-1.pdf", "pdf"),
    ("si_epmc_instance.pdf", "https://europepmc.org/articles/PMC2880455/bin/NIHMS69615-supplement-1.pdf?download=1", "pdf"),
    ("si_nature_media.pdf", "https://www.nature.com/articles/nchembio.117/MediaObjects/41589_2008_BFnchembio117_MOESM1_ESM.pdf", "pdf"),
]
PUBLISHER_MEDIA = [
    ("si_springernature.pdf", "https://media.springernature.com/full/springer-static/esm/art%3A10.1038%2Fnchembio.117/MediaObjects/41589_2008_BFnchembio117_MOESM1_ESM.pdf", "pdf"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="data/raw/apsel_materials_20261020")
    parser.add_argument("--mirrors", action="store_true")
    parser.add_argument("--publisher-media", action="store_true")
    args = parser.parse_args()
    out = ROOT / args.output_dir
    if out.exists():
        raise FileExistsError(f"기존 자료 보호: {out}")
    out.mkdir(parents=True)
    sources = PUBLISHER_MEDIA if args.publisher_media else (MIRRORS if args.mirrors else SOURCES)
    records = [fetch_one(source, out) for source in sources]
    if not any("http_status" in r for r in records):
        out.rmdir()
        raise RuntimeError("모든 요청 실패; 네트워크 권한 확인 필요")
    (out / "manifest.json").write_text(json.dumps({"created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "공식·저자 공개 SI 경로 후보; 성공 여부는 HTTP·PDF 형식으로 확인", "sources": records}, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
