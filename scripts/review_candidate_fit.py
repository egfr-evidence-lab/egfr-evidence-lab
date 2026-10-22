"""주 학습 코호트 후보의 적합성을 프로젝트 자신의 기준으로 대조한다.

새 수집·새 학습을 하지 않는다. 기존 동결 산출물만 읽는다:
  - data/interim/main_cohort_inventory_20261020/source_priority_queue.csv (242 assay)
  - data/interim/cohort_scope_diagnostics_20261020/cohort_metrics.csv (분할 진단 지표)
  - configs/cohort_policy.json (critical_fields)

게이트는 configs/project.json·cohort_policy.json·HANDOFF.txt의 불변 기준에서 가져왔다.
각 게이트의 판정 근거(evidence)는 사람이 확인한 경로/인용을 함께 적는다.
게이트 통과가 학습 승인이 아니다. 승인은 사람의 독립 검토를 거쳐야 한다.

사용:
  PYTHONPATH=src .venv-ml/bin/python scripts/review_candidate_fit.py \
      --output-dir data/interim/candidate_fit_review_20261020
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "data/interim/main_cohort_inventory_20261020/source_priority_queue.csv"
DIAG = ROOT / "data/interim/cohort_scope_diagnostics_20261020/cohort_metrics.csv"
POLICY = ROOT / "configs/cohort_policy.json"

# 사람이 이 세션에서 직접 확인한 외부 근거. 각 항목은 재확인 가능한 경로/식별자를 갖는다.
# 값: (판정, 근거문자열). 판정은 "pass" / "fail" / "unknown".
VERIFIED_EVIDENCE: dict[str, dict[str, tuple[str, str]]] = {
    "CHEMBL4258549": {  # pilot22
        "species_human": ("pass", "ChEMBL assay description에 'Wild type human EGFR' 명시 + 원문 PMC6083791 확보"),
        "primary_text_accessible": ("pass", "Europe PMC pmcid=PMC6083791, inEPMC=Y, availability에 'Free' 포함 (2026-10-20 재확인)"),
        "quantitative_conditions_known": ("pass", "원문에서 ATP 5 uM / poly(Glu,Tyr)4:1 / 37C / 60분 / ELISA 확인 (reports/cohort_definition_evidence.md)"),
        "no_source_conflict": ("pass", "본문 Tables 1·3의 22/22 수치가 원 activity ID와 일치 (HANDOFF.txt 문헌·코호트 기준 검토)"),
    },
    "CHEMBL5382277": {  # furan45
        "species_human": ("unknown", "ChEMBL description은 '(unknown origin)'. ref28(CHEMBL4416105) description의 'human'과 PDB 6JZ0(Homo sapiens/P00533/696-1021/WT)이 정황 근거이나 동일 assay 기록이 아님 - 추론 금지 규칙상 미확정"),
        "primary_text_accessible": ("fail", "2023 본문(PMC9969398)은 공개이나 실험법을 위임한 ref28(DOI 10.1021/acs.jmedchem.9b00722)이 구독 전용. ACS 403, EuropePMC 'Subscription required', NHRI 권리안내 HTML (data/raw/scope_evidence_20261020_v3/manifest.json#access_blocked_log)"),
        "quantitative_conditions_known": ("fail", "ATP 농도·효소량·기질농도·온도·buffer pH 미확인. description은 'in presence of ATP'로 수치 없음"),
        "no_source_conflict": ("unknown", "저자 CSV 25.3/24.9 nM vs DB 25 nM 2건 미해소 (reports/cohort_scope_evidence_ko.md 3절)"),
    },
    "CHEMBL5737421": {  # patent64
        "species_human": ("pass", "특허 원문: 'wild-type EGFR kinase (Invitrogen, PV3872)'. PV3872 공식 제품자료로 human·GST 668-1210 확인(사용 lot 미확인)"),
        "primary_text_accessible": ("pass", "US11155546B2 특허 전문 공개"),
        "quantitative_conditions_known": ("pass", "특허 원문: ATP 10 uM / enzyme 0.8 ng/uL / Tyr04 2 uM / 25C 60분 / TR-FRET"),
        "no_source_conflict": ("fail", "G번호별 원 MS와 DB 구조 계산값이 35관측 중 13관측에서 약 14-30 Da 차이 (data/interim/patent_structure_review_20261020_v2/)"),
    },
    "CHEMBL5141216": {  # BLU-945 WT biochemical
        "species_human": ("unknown", "ChEMBL description은 'wild type human EGFR ... GST ... Sf9'라고 하나, 원문(PMC9340769) 방법에는 GST·Sf9·insect 언급이 전혀 없고 효소는 'WT and mutant EGFR enzymes (SignalChem)'로만 기재 - DB 주석이 원문을 넘어섬"),
        "primary_text_accessible": ("pass", "Europe PMC isOpenAccess=Y, PMC9340769. 전문 XML 로컬 보유: data/raw/protocol_discovery_20261020_v2/PMC9340769.xml"),
        "quantitative_conditions_known": ("pass", "원문 'Inhibition of EGFR Mutant Biochemical Enzymatic Activity': 기질 2.5 uM, ATP 1 mM, 10 mM MgCl2, 0.015% Brij-35, 1 mM DTT, 1% DMSO, 100 mM HEPES pH 7.5, 25 C, 억제제 10분 사전배양, Caliper EZReader 2"),
        "no_source_conflict": ("fail", "기질 펩타이드 불일치: 원문 5-FAM-EEPLYWSFPAKKK-CONH2 vs ChEMBL description 5-FAM-EEPLYINSFPAKKK-CONH. 또한 원문에 없는 GST/Sf9가 DB 설명에 존재"),
    },
    "CHEMBL1243977": {  # Apsel209
        "species_human": ("unknown", "description 'recombinant EGFR' - 종 미기재. homolog(H) 플래그·confidence 8"),
        "primary_text_accessible": ("pass", "PMC2880455 저자 PDF 확보. 단 SI 표는 challenge HTML/403/404로 미확보"),
        "quantitative_conditions_known": ("unknown", "ATP 10 uM은 확인. 효소 구성체·농도·전체 SI 조건 미확정"),
        "no_source_conflict": ("unknown", "정확값 100 uM 28건(상한 초과 총 30건)의 의미 미확인"),
    },
    "CHEMBL5736995": {  # 981건
        "species_human": ("pass", "특허 원문 KinEASE(Cisbio) TR-FRET 기재"),
        "primary_text_accessible": ("pass", "US11066414B2 특허 전문 공개"),
        "quantitative_conditions_known": ("pass", "특허 원문에 TR-FRET 조건 기재"),
        "no_source_conflict": ("fail", "Table3 앞 문장이 Cot 결과이며 928건이 Cot 열과 일치, 명시 EGFR 열 일치 1건 - 표적 열 혼입 정황으로 assay 전체 보류"),
    },
}

GATES = [
    ("variant_confirmed_WT", "변이 확정(WT)"),
    ("format_biochemical", "형식 확정(생화학)"),
    ("species_human", "종(human) 확인"),
    ("structures_verified", "구조 보류 0"),
    ("no_duplicates", "중복 0"),
    ("exact_only", "정확값만(부등호 혼입 없음)"),
    ("primary_text_accessible", "일차 원문 접근 가능"),
    ("quantitative_conditions_known", "정량 조건(ATP·온도·readout) 확인"),
    ("no_source_conflict", "원문-DB 충돌 없음"),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tryint(x, d=0):
    try:
        return int(x)
    except (TypeError, ValueError):
        return d


def tryfloat(x, d=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def evaluate(row: dict) -> dict:
    aid = row["assay_chembl_id"]
    ev = VERIFIED_EVIDENCE.get(aid, {})
    raw = tryint(row["raw_rows"])
    exact = tryint(row["exact_positive_nM_rows"])

    gates: dict[str, dict[str, str]] = {}

    def put(name, verdict, why):
        gates[name] = {"verdict": verdict, "evidence": why}

    put("variant_confirmed_WT",
        "pass" if row["variant_screen"] == "WT" else "fail",
        f"source_priority_queue.csv variant_screen={row['variant_screen']}")
    put("format_biochemical",
        "pass" if row["format_screen"] == "biochemical_candidate" else "fail",
        f"source_priority_queue.csv format_screen={row['format_screen']}")
    put("structures_verified",
        "pass" if tryint(row["structure_hold_rows"]) == 0 else "fail",
        f"structure_hold_rows={row['structure_hold_rows']}")
    put("no_duplicates",
        "pass" if tryint(row["potential_duplicate_rows"]) == 0 else "fail",
        f"potential_duplicate_rows={row['potential_duplicate_rows']}")
    put("exact_only",
        "pass" if raw == exact else "fail",
        f"raw_rows={raw}, exact_positive_nM_rows={exact} (차이는 부등호·비정상값)")

    for name in ("species_human", "primary_text_accessible",
                 "quantitative_conditions_known", "no_source_conflict"):
        verdict, why = ev.get(name, ("unknown", "이 세션에서 확인하지 않음"))
        put(name, verdict, why)

    passed = sum(1 for g, _ in GATES if gates[g]["verdict"] == "pass")
    failed = sum(1 for g, _ in GATES if gates[g]["verdict"] == "fail")
    unknown = sum(1 for g, _ in GATES if gates[g]["verdict"] == "unknown")

    span = None
    if tryfloat(row["pIC50_max"]) is not None and tryfloat(row["pIC50_min"]) is not None:
        span = round(tryfloat(row["pIC50_max"]) - tryfloat(row["pIC50_min"]), 4)

    return {
        "assay_chembl_id": aid,
        "document_chembl_id": row["document_chembl_id"],
        "document_type": row["document_type"],
        "doi": row["doi"],
        "pmid": row["pmid"],
        "raw_rows": raw,
        "exact_rows": exact,
        "structures": tryint(row["recomputed_single_component_structures"]),
        "connectivity_groups": tryint(row["connectivity_groups"]),
        "scaffolds": tryint(row["recomputed_scaffolds"]),
        "largest_scaffold_fraction": tryfloat(row["largest_scaffold_fraction"]),
        "pIC50_span": span,
        "confidence_score": row["confidence_score"],
        "auto_hold_reasons": row["assay_hold_reasons"],
        "gates_passed": passed,
        "gates_failed": failed,
        "gates_unknown": unknown,
        "gates": gates,
        "training_approved": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    out = Path(args.output_dir)
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"거부: 출력 폴더가 비어 있지 않다. 새 경로를 지정하라: {out}")
    out.mkdir(parents=True, exist_ok=True)

    rows = list(csv.DictReader(QUEUE.open(newline="", encoding="utf-8")))
    by_assay = {r["assay_chembl_id"]: r for r in rows}

    results = [evaluate(by_assay[aid]) for aid in VERIFIED_EVIDENCE if aid in by_assay]
    results.sort(key=lambda r: (-r["gates_passed"], r["gates_failed"]))

    # 큐 전체 통계 (후보 선정의 모집단을 함께 기록)
    population = {
        "queue_rows": len(rows),
        "zero_auto_hold_rows": [r["assay_chembl_id"] for r in rows if r["assay_hold_reasons"].strip() == ""],
        "wt_and_biochemical_rows": [r["assay_chembl_id"] for r in rows
                                    if r["variant_screen"] == "WT" and r["format_screen"] == "biochemical_candidate"],
    }

    summary_csv = out / "candidate_gate_summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["assay_chembl_id", "document_type", "exact_rows", "scaffolds",
                    "largest_scaffold_fraction", "pIC50_span",
                    "gates_passed", "gates_failed", "gates_unknown",
                    *[g for g, _ in GATES], "training_approved"])
        for r in results:
            w.writerow([r["assay_chembl_id"], r["document_type"], r["exact_rows"], r["scaffolds"],
                        r["largest_scaffold_fraction"], r["pIC50_span"],
                        r["gates_passed"], r["gates_failed"], r["gates_unknown"],
                        *[r["gates"][g]["verdict"] for g, _ in GATES], r["training_approved"]])

    detail = out / "candidate_gate_detail.json"
    detail.write_text(json.dumps({
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "주 학습 코호트 후보 적합성 대조 (모델 학습·수집 없음, 승인 아님)",
        "policy_path": "configs/cohort_policy.json",
        "policy_critical_fields": json.loads(POLICY.read_text(encoding="utf-8"))["cross_assay_pooling_requires"]["critical_fields"],
        "gate_definitions": {g: label for g, label in GATES},
        "population": population,
        "candidates": results,
        "training_approved_total": 0,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    manifest = out / "manifest.json"
    manifest.write_text(json.dumps({
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "script": "scripts/review_candidate_fit.py",
        "script_sha256": sha256(Path(__file__)),
        "inputs_sha256": {
            "data/interim/main_cohort_inventory_20261020/source_priority_queue.csv": sha256(QUEUE),
            "data/interim/cohort_scope_diagnostics_20261020/cohort_metrics.csv": sha256(DIAG),
            "configs/cohort_policy.json": sha256(POLICY),
        },
        "outputs_sha256": {
            "candidate_gate_summary.csv": sha256(summary_csv),
            "candidate_gate_detail.json": sha256(detail),
        },
        "model_training_executed": False,
        "new_collection_executed": False,
        "training_approved": False,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    for r in results:
        print(f"{r['assay_chembl_id']:<15} pass={r['gates_passed']} fail={r['gates_failed']} "
              f"unknown={r['gates_unknown']}  n={r['exact_rows']:>4} scaf={r['scaffolds']:>3} "
              f"span={r['pIC50_span']}")
    print(f"\n출력: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
