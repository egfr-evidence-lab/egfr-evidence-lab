"""감사 산출물의 출처·무결성·행 보존·정확 라벨을 독립 검사한다."""

import argparse
import hashlib
import json
import math
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(audit_dir):
    manifest = json.loads((audit_dir / "audit_manifest.json").read_text())
    if manifest["state"] != "complete" or manifest["training_ready"] is not False:
        raise ValueError("감사 완료·학습 미확정 상태가 아닙니다.")
    for section in ("inputs", "outputs"):
        for name, record in manifest[section].items():
            if sha(record["path"]) != record["sha256"]:
                raise ValueError(f"{section} 파일 해시 불일치: {name}")
    if sha(Path(manifest["run_dir"]) / "manifest.json") != manifest["source_manifest_sha256"]:
        raise ValueError("수집 매니페스트가 감사 당시와 다릅니다.")
    for name, expected in manifest["code_sha256"].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"감사 코드가 실행 당시와 다릅니다: {name}")
    frames = {name: pd.read_csv(record["path"], dtype=str, keep_default_na=False)
              for name, record in manifest["outputs"].items() if record["path"].endswith(".csv")}
    for name, frame in frames.items():
        if len(frame) != manifest["outputs"][name]["rows"]:
            raise ValueError(f"CSV 행 수가 다릅니다: {name}")
    source = pd.read_parquet(manifest["inputs"]["activity"]["path"])
    audited, candidates = frames["activity_audit"], frames["candidate_measurements"]
    if len(audited) != len(source) or set(audited.activity_id) != set(source.activity_id.astype(str)) or audited.activity_id.duplicated().any():
        raise ValueError("원 측정 ID의 누락·중복이 있습니다.")
    expected = audited.loc[audited.provisional_candidate.eq("True")]
    pd.testing.assert_frame_equal(candidates.reset_index(drop=True), expected.reset_index(drop=True))
    powers = {"M": 0, "mM": -3, "uM": -6, "nM": -9, "pM": -12}
    for row in audited.to_dict("records"):
        if row["pIC50_computed"]:
            if row["standard_relation"] != "=" or row["standard_type"] != "IC50":
                raise ValueError("정확 IC50가 아닌 행에 회귀 라벨이 있습니다.")
            n = float(row["standard_value"])
            unit = row["standard_units"].replace("µ", "u").replace("μ", "u")
            if not math.isfinite(n) or n <= 0 or not math.isclose(float(row["pIC50_computed"]), -math.log10(n) - powers[unit], abs_tol=1e-10):
                raise ValueError("농도와 pIC50 계산이 일치하지 않습니다.")
    if candidates.screen_reasons.ne("").any() or candidates.variant_screen.eq("unresolved").any():
        raise ValueError("보류 행이 후보에 섞였습니다.")
    if frames["manual_review_queue"].decision.ne("").any():
        raise ValueError("자동 감사 초안에 수동 결정이 작성되어 있습니다.")
    summary_path = manifest["outputs"]["audit_summary.json"]["path"]
    summary = json.loads(Path(summary_path).read_text())
    if sum(summary["exclusive_waterfall"].values()) != len(source) or sum(s["measurements"] for s in summary["cohorts"].values()) != len(candidates):
        raise ValueError("전체·변이별 수치가 일치하지 않습니다.")
    return {"passed": True, "checked_measurements": len(audited), "candidate_measurements": len(candidates),
            "csv_files": len(frames), "output_files_hashed": len(manifest["outputs"]),
            "audit_manifest_sha256": sha(audit_dir / "audit_manifest.json"),
            "checks": ["입력·출력·코드·수집 매니페스트 SHA-256", "CSV 행 수", "전체 활동 ID 보존·유일성",
                       "후보 행 전체 내용 대조", "정확 IC50 농도로 pIC50 독립 재계산", "미해결·보류 후보 혼입 방지",
                       "수동 결정 빈칸", "전체·변이별 집계 합계"],
            "limit": "기술적 무결성 검사이며 자동 분류의 과학적 정확도·원문 검토 완료를 뜻하지 않음"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit_dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = check(args.audit_dir)
    body = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(body)
    print(body)
