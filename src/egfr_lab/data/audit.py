"""보수적인 자동 선별 감사. 원문 검토나 최종 학습 데이터 확정을 대신하지 않는다."""

from collections import Counter
from importlib import metadata
from io import BytesIO
import json
import math
from pathlib import Path
import platform
import re

import pandas as pd
from rdkit import Chem, rdBase
from rdkit.Chem.Scaffolds import MurckoScaffold

from ..labels import ic50_to_pic50
from .collection import ROOT, verify_collection
from .store import atomic_bytes, atomic_json, digest, utc_now


POLICY = "conservative-screen-v1"
SOURCES = {
    "ChEMBL 실험·품질": "https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/chembl-data-questions",
    "ChEMBL 변이·표적": "https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/target-questions",
    "RDKit scaffold": "https://www.rdkit.org/docs/source/rdkit.Chem.Scaffolds.MurckoScaffold.html",
}
REASONS = {
    "target_link": "직접 인간 EGFR 연결(confidence 9, D, taxon 9606) 미충족",
    "species_unclear": "실험 설명에 단백질 유래 불명 표기",
    "variant_unresolved": "정상형/단일 변이 맥락 미확정 또는 표기 충돌",
    "format_not_biochemical": "생화학 실험 근거 미충족 또는 세포/실험 형식 충돌",
    "endpoint": "표준 endpoint가 IC50가 아님",
    "not_exact": "부등호·근삿값·관계 결측",
    "invalid_value": "농도 결측·비수치·비양수·비유한 값",
    "unsupported_unit": "지원하지 않는 단위(질량 농도 등)",
    "quality_flag": "품질 경고(원문 재검토 필요)",
    "potential_duplicate": "ChEMBL 잠재 중복 인용 플래그",
    "not_standardized": "standard_flag가 1이 아님",
    "structure": "구조 결측·파싱 실패·다성분·분자 유형 미확정/부적합",
    "document_conflict": "측정과 assay의 출처 문헌 ID 불일치",
    "variant_conflict": "측정과 assay의 변이 메타데이터 불일치",
}
MUTATION = re.compile(r"\b[ACDEFGHIKLMNPQRSTVWY]\d{2,4}[ACDEFGHIKLMNPQRSTVWY]\b", re.I)
WT = re.compile(r"\bwild[\s-]*type\b|\bWT\b", re.I)
MUTANT = re.compile(r"\bmutant\b|\bmutation\b|\bdel\d*\b|\bdeletion\b|\binsertion\b|\bexon\s*\d+\b", re.I)
CELL = re.compile(r"\bcells?\b|\bcellular\b|\bin vivo\b|proliferation|viability|cytotoxic|\bMTT\b|celltiter", re.I)
BIO = re.compile(r"recombinant|\bsubstrate\b|\bATP\b|\bHTRF\b|Z.?[ -]?lyte|\bFRET\b|enzym|kinase domain|radiometric|scintillation|ADP.Glo|kinase.Glo", re.I)
PROTEIN_FORMATS = {"single protein format", "protein format", "cell-free format"}


def value(item):
    return "" if item is None or pd.isna(item) else str(item).strip()


def mutations(text):
    return sorted(set(x.upper() for x in MUTATION.findall(text)))


def classify_assay(row):
    text, annotation = value(row.get("description")), value(row.get("variant_mutation"))
    wt = bool(WT.search(text))
    text_mutations = mutations(text)
    mutant = bool(MUTANT.search(text) or text_mutations)
    annotated = mutations(annotation)
    accession = value(row.get("variant_accession"))
    variant, evidence = "unresolved", "정상형의 명시적 근거 없음"
    if annotation:
        if annotation.upper() == "UNDEFINED MUTATION" or not annotated:
            evidence = "정의되지 않은 변이 메타데이터"
        elif re.sub(r"[\s,;/]", "", annotation.upper()) != "".join(MUTATION.findall(annotation.upper())):
            evidence = "지원하지 않는 변이 표기"
        elif accession != "P00533":
            evidence = "변이 기준 accession이 P00533과 다르거나 결측"
        elif wt or (text_mutations and set(annotated) != set(text_mutations)):
            evidence = "설명과 구조화 변이 표기가 충돌"
        else:
            variant, evidence = "+".join(annotated), "P00533 구조화 변이; 설명에서 상충 표기 없음"
    elif wt and not mutant and not accession and re.search(r"EGF.?R|epidermal growth factor receptor", text, re.I):
        variant, evidence = "WT", "설명에 정상형 EGFR 명시; 변이 단서 없음"
    elif mutant:
        evidence = "설명에 변이 단서가 있지만 메타데이터 미확정"
    if CELL.search(text) or value(row.get("bao_label")) in {"cell-based format", "organism-based format", "cell membrane format", "subcellular format"}:
        fmt = "cellular_or_conflict"
    elif value(row.get("assay_type")) == "B" and value(row.get("bao_label")) in PROTEIN_FORMATS and BIO.search(text):
        fmt = "biochemical_candidate"
    else:
        fmt = "unresolved_or_other"
    reasons = []
    if not (value(row.get("target_chembl_id")) == "CHEMBL203" and value(row.get("confidence_score")) == "9"
            and value(row.get("relationship_type")) == "D" and value(row.get("assay_organism")) == "Homo sapiens"
            and value(row.get("assay_tax_id")) == "9606"):
        reasons.append("target_link")
    if re.search(r"unknown (?:origin|source)|origin unknown|undefined origin", text, re.I):
        reasons.append("species_unclear")
    if variant == "unresolved":
        reasons.append("variant_unresolved")
    if fmt != "biochemical_candidate":
        reasons.append("format_not_biochemical")
    return {"variant_screen": variant, "variant_evidence_ko": evidence, "format_screen": fmt,
            "assay_screen_reasons": ";".join(reasons), "assay_candidate": not reasons,
            "review_status": "자동 선별·원문 미검토"}


def audit_molecule(row):
    smiles = value(row.get("canonical_smiles"))
    result = {"canonical_isomeric_smiles": "", "connectivity_smiles": "", "scaffold_smiles": "",
              "structure_group": "", "fragment_count": 0, "unspecified_stereocenters": 0,
              "structure_status": "missing_smiles", "structure_candidate": False}
    if not smiles:
        return result
    # 파싱 실패는 행별 상태로 보존한다.
    with rdBase.BlockLogs():
        mol = Chem.MolFromSmiles(smiles)
    if mol is None or mol.GetNumAtoms() == 0:
        result["structure_status"] = "parse_failed"
        return result
    canonical = Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)
    fragments = len(Chem.GetMolFrags(mol))
    result.update(canonical_isomeric_smiles=canonical, fragment_count=fragments,
                  connectivity_smiles=Chem.MolToSmiles(mol, canonical=True, isomericSmiles=False),
                  structure_group=digest(canonical.encode()),
                  unspecified_stereocenters=sum(label == "?" for _, label in Chem.FindMolChiralCenters(mol, includeUnassigned=True)))
    if fragments != 1:
        result["structure_status"] = "multiple_fragments_hold"
    elif value(row.get("molecule_type")) in {"", "Unknown"}:
        result["structure_status"] = "molecule_type_unconfirmed_hold"
    elif value(row.get("molecule_type")) != "Small molecule":
        result["structure_status"] = "not_small_molecule_hold"
    else:
        result.update(structure_status="single_component_candidate", structure_candidate=True,
                      scaffold_smiles=MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False))
    return result


def measurement_screen(row):
    reasons, pic50 = [], None
    if value(row.get("standard_type")) != "IC50":
        reasons.append("endpoint")
    relation = value(row.get("standard_relation"))
    unit = value(row.get("standard_units"))
    if relation != "=":
        reasons.append("not_exact")
    try:
        number = float(value(row.get("standard_value")))
        valid = math.isfinite(number) and number > 0
    except ValueError:
        valid = False
    if not valid:
        reasons.append("invalid_value")
    if unit.replace("μ", "u").replace("µ", "u") not in {"M", "mM", "uM", "nM", "pM"}:
        reasons.append("unsupported_unit")
    if not reasons:
        pic50 = ic50_to_pic50(number, unit, relation)
    if value(row.get("data_validity_comment")) not in {"", "Manually validated"}:
        reasons.append("quality_flag")
    if value(row.get("potential_duplicate")) != "0":
        reasons.append("potential_duplicate")
    if value(row.get("standard_flag")) != "1":
        reasons.append("not_standardized")
    return pic50, reasons


def build_frames(activities, assays, molecules, documents):
    assay_review = assays.copy()
    for column in ("variant_sequence",):
        if column in assay_review:
            assay_review["variant_sequence_sha256"] = [digest(value(x).encode()) if value(x) else "" for x in assay_review[column]]
            assay_review = assay_review.drop(columns=column)
    classified = [classify_assay(r) for r in assays.to_dict("records")]
    assay_review = pd.concat([assay_review.reset_index(drop=True), pd.DataFrame(classified)], axis=1)
    molecule_audit = pd.concat([molecules.reset_index(drop=True), pd.DataFrame([audit_molecule(r) for r in molecules.to_dict("records")])], axis=1)
    assay_map = {r["assay_chembl_id"]: r for r in assay_review.to_dict("records")}
    mol_map = {r["molecule_chembl_id"]: r for r in molecule_audit.to_dict("records")}
    doc_map = {r["document_chembl_id"]: r for r in documents.to_dict("records")}
    screened = []
    for row in activities.to_dict("records"):
        a, m, d = assay_map[row["assay_chembl_id"]], mol_map[row["molecule_chembl_id"]], doc_map[row["document_chembl_id"]]
        pic50, reasons = measurement_screen(row)
        assay_reasons = a["assay_screen_reasons"].split(";") if a["assay_screen_reasons"] else []
        reasons = assay_reasons + reasons
        if not m["structure_candidate"]:
            reasons.append("structure")
        if value(row["document_chembl_id"]) != value(a["document_chembl_id"]):
            reasons.append("document_conflict")
        if value(row.get("assay_variant_mutation")) != value(a.get("variant_mutation")) or value(row.get("assay_variant_accession")) != value(a.get("variant_accession")):
            reasons.append("variant_conflict")
        screened.append({**row, "pIC50_computed": pic50, "variant_screen": a["variant_screen"],
                         "format_screen": a["format_screen"], "screen_reasons": ";".join(reasons),
                         "first_reason": reasons[0] if reasons else "candidate",
                         "provisional_candidate": not reasons,
                         **{k: m[k] for k in ("canonical_isomeric_smiles", "connectivity_smiles", "structure_group", "scaffold_smiles", "unspecified_stereocenters")},
                         "assay_document_chembl_id": a["document_chembl_id"],
                         "document_doi": value(d.get("doi")), "document_pubmed_id": value(d.get("pubmed_id")),
                         "document_title": value(d.get("title")), "review_status": "자동 선별·원문 미검토"})
    activity_audit = pd.DataFrame(screened)
    candidates = activity_audit.loc[activity_audit.provisional_candidate].copy()
    context = ["structure_group", "assay_chembl_id", "variant_screen", "document_chembl_id"]
    if candidates.empty:
        repeats = pd.DataFrame(columns=context + ["measurements", "pIC50_min", "pIC50_max", "activity_ids", "pIC50_span"])
    else:
        repeats = candidates.groupby(context, dropna=False).agg(
            measurements=("activity_id", "size"), pIC50_min=("pIC50_computed", "min"),
            pIC50_max=("pIC50_computed", "max"), activity_ids=("activity_id", lambda x: ";".join(map(str, x)))).reset_index()
        repeats["pIC50_span"] = repeats.pIC50_max - repeats.pIC50_min
        repeats = repeats.loc[repeats.measurements > 1]
    queue = assay_review.copy()
    queue["priority"] = ["01_후보_원문검토" if r["assay_candidate"] else "02_보류_근거확인" for r in classified]
    queue = queue.merge(activities.groupby("assay_chembl_id").size().rename("activity_count"), on="assay_chembl_id", validate="one_to_one")
    queue = queue.merge(documents[["document_chembl_id", "doi", "pubmed_id", "title"]], on="document_chembl_id", how="left", validate="many_to_one")
    queue = queue.sort_values(["priority", "activity_count", "assay_chembl_id"], ascending=[True, False, True])
    for c in ("reviewer", "reviewed_at", "decision", "evidence_url", "protein_construct", "atp_concentration_uM",
              "substrate", "preincubation_minutes", "reaction_minutes", "readout", "covalent_time_dependence", "review_notes"):
        queue[c] = ""
    return {"assay_review": assay_review, "molecule_audit": molecule_audit,
            "activity_audit": activity_audit, "candidate_measurements": candidates,
            "repeat_contexts": repeats, "manual_review_queue": queue}


def distribution(series):
    return dict(sorted(Counter(value(x) or "(결측)" for x in series).items()))


def cohort_stats(frame):
    if frame.empty:
        return {"measurements": 0, "structures": 0, "assays": 0, "documents": 0, "ring_scaffolds": 0, "acyclic_structures": 0}
    docs = frame.document_chembl_id.value_counts()
    scaffold = frame[["structure_group", "scaffold_smiles"]].drop_duplicates()
    return {"measurements": len(frame), "structures": int(frame.structure_group.nunique()),
            "molecule_ids": int(frame.molecule_chembl_id.nunique()), "assays": int(frame.assay_chembl_id.nunique()),
            "documents": int(frame.document_chembl_id.nunique()),
            "ring_scaffolds": int(frame.loc[frame.scaffold_smiles.ne(""), "scaffold_smiles"].nunique()),
            "acyclic_structures": int(scaffold.scaffold_smiles.eq("").sum()),
            "pIC50_min": float(frame.pIC50_computed.min()), "pIC50_median": float(frame.pIC50_computed.median()),
            "pIC50_max": float(frame.pIC50_computed.max()), "largest_document": str(docs.index[0]),
            "largest_document_fraction": float(docs.iloc[0] / len(frame)),
            "top5_document_fraction": float(docs.iloc[:5].sum() / len(frame)),
            "structures_with_multiple_assays": int((frame.groupby("structure_group").assay_chembl_id.nunique() > 1).sum()),
            "unspecified_stereo_measurements": int(frame.unspecified_stereocenters.gt(0).sum())}


def summarize(frames, activities):
    a, c, m, s = (frames[k] for k in ("activity_audit", "candidate_measurements", "molecule_audit", "assay_review"))
    reasons = Counter(reason for text in a.screen_reasons for reason in text.split(";") if reason)
    repeat_keys = ["molecule_chembl_id", "assay_chembl_id", "document_chembl_id", "assay_variant_mutation", "assay_variant_accession"]
    repeated = activities.groupby(repeat_keys, dropna=False).size()
    exact_keys = repeat_keys + ["standard_type", "standard_relation", "standard_value", "standard_units"]
    exact_repeated = activities.groupby(exact_keys, dropna=False).size()
    review_pools = {}
    for reason in ("species_unclear", "structure"):
        mask = a.variant_screen.eq("WT") & a.screen_reasons.eq(reason)
        review_pools[reason] = {"measurements": int(mask.sum()), "assays": int(a.loc[mask, "assay_chembl_id"].nunique()),
                              "interpretation": "이 사유만으로 보류된 WT 자료. 재판정 전 후보 수에 더하지 않음"}
    return {"policy": POLICY, "measurements": len(a), "assays": len(s), "molecules": len(m),
            "measurement_documents": int(activities.document_chembl_id.nunique()),
            "distributions": {k: distribution(activities[k]) for k in ("standard_relation", "standard_units", "data_validity_comment", "potential_duplicate", "standard_flag", "src_id", "document_year")},
            "molecule_type": distribution(m.molecule_type),
            "variant_by_assay": distribution(s.variant_screen), "format_by_assay": distribution(s.format_screen),
            "structure_status": distribution(m.structure_status), "overlapping_hold_reasons": dict(sorted(reasons.items())),
            "exclusive_waterfall": distribution(a.first_reason),
            "cohorts": {str(v): cohort_stats(g) for v, g in c.groupby("variant_screen", sort=True)},
            "candidate_repeat_contexts": len(frames["repeat_contexts"]),
            "candidate_repeated_measurements": int(frames["repeat_contexts"].measurements.sum()),
            "all_record_repeat_contexts": int(repeated.gt(1).sum()),
            "all_record_repeat_context_measurements": int(repeated[repeated.gt(1)].sum()),
            "all_record_identical_value_groups": int(exact_repeated.gt(1).sum()),
            "all_record_identical_value_measurements": int(exact_repeated[exact_repeated.gt(1)].sum()),
            "wt_single_reason_review_pools": review_pools,
            "pchembl_crosscheck": pchembl_check(a),
            "manual_review_completed": 0, "training_ready": False}


def pchembl_check(frame):
    p = pd.to_numeric(frame.pchembl_value, errors="coerce")
    mask = p.notna() & frame.pIC50_computed.notna()
    delta = (p[mask] - frame.loc[mask, "pIC50_computed"]).abs()
    return {"compared": int(mask.sum()), "difference_over_0_011": int(delta.gt(0.011).sum()),
            "max_absolute_difference": float(delta.max()) if len(delta) else None,
            "interpretation": "표준 농도로 재계산; pChEMBL 반올림 허용차 0.011로 교차 확인"}


def markdown_table(mapping):
    return "\n".join(f"| {key} | {count:,} |" for key, count in mapping.items())


def reports(summary, output):
    lines = ["# EGFR 전체 데이터 감사", "", f"정책: `{POLICY}`. 자동 선별 결과이며 원문 검토 완료 수는 0건이다. 학습 코호트는 미확정이다.", "",
             f"수집 release: {summary['release']['chembl_db_version']} / {summary['release']['chembl_release_date']}.", "",
             f"측정 {summary['measurements']:,}건 / 실험 {summary['assays']:,}개 / 분자 ID {summary['molecules']:,}개를 전수 검사했다.", "",
             "## 관측값과 품질", ""]
    for k, counts in summary["distributions"].items():
        lines += [f"### {k}", "", "| 값 | 측정 수 |", "|---|---:|", markdown_table(counts), ""]
    lines += ["## 실험·구조 분류", ""]
    for k in ("variant_by_assay", "format_by_assay", "molecule_type", "structure_status"):
        lines += [f"### {k}", "", "| 자동 분류 | 건수 |", "|---|---:|", markdown_table(summary[k]), ""]
    lines += ["## 보류 사유", "", "여러 사유가 한 측정에 겹칠 수 있다. 보류는 원자료 삭제를 뜻하지 않는다.", "",
              "| 사유 | 해당 측정 수 |", "|---|---:|"]
    lines += [f"| {REASONS[k]} (`{k}`) | {n:,} |" for k, n in summary["overlapping_hold_reasons"].items()]
    lines += ["", "첫 사유만 세는 상호 배타적 흐름(총합은 전체 측정 수):", "", "| 첫 사유 | 측정 수 |", "|---|---:|", markdown_table(summary["exclusive_waterfall"]), "", "## 변이별 생화학 후보", "",
              "서로 다른 변이 코호트를 합치지 않는다. 같은 WT 안에서도 ATP·기질·반응 시간·검출법 차이가 남아 있다.", "",
              "| 변이 | 측정 | 고유 구조 | 실험 | 문헌 | 고리 scaffold | pIC50 범위 | 최대 문헌 비율 |", "|---|---:|---:|---:|---:|---:|---|---:|"]
    for v, stats in summary["cohorts"].items():
        lines.append(f"| {v} | {stats['measurements']:,} | {stats['structures']:,} | {stats['assays']:,} | {stats['documents']:,} | {stats['ring_scaffolds']:,} | {stats['pIC50_min']:.3f}–{stats['pIC50_max']:.3f} | {stats['largest_document_fraction']:.1%} |")
    lines += ["", "## 중복·라벨 교차 확인", "",
              f"전체 자료에서 동일 분자 ID·assay·변이 메타데이터·문헌의 반복 맥락 {summary['all_record_repeat_contexts']:,}개({summary['all_record_repeat_context_measurements']:,}건). 그 안에서 관계·표준값 문자열·단위까지 같은 그룹 {summary['all_record_identical_value_groups']:,}개({summary['all_record_identical_value_measurements']:,}건). 결측도 같은 표기로 묶은 기술적 집계이다. 이 수치는 반복 실험과 중복 인용을 자동 구별하지 않으며, 문자열이 다른 반올림값도 통합하지 않는다.", "",
              f"후보에서 동일 구조·assay·변이·문헌의 반복 맥락 {summary['candidate_repeat_contexts']:,}개, 해당 측정 {summary['candidate_repeated_measurements']:,}건. 평균·중앙값 집계나 행 삭제는 하지 않았다.", "",
              f"pChEMBL 교차 확인: {json.dumps(summary['pchembl_crosscheck'], ensure_ascii=False)}", "",
              "서로 다른 assay의 같은 분자는 별도 관측으로 유지했다. 잠재 중복 인용 플래그는 보류했다. 플래그가 0이어도 독립 재측정을 보증하지 않는다.", "",
              "## 사용 정책과 다음 결정", "",
              "1. WT 후보를 첫 원문 검토 대상으로 제안한다. WT가 최종 학습 대상으로 확정된 것은 아니다.",
              "2. manual_review_queue.csv에서 후보 우선으로 원문·SI를 확인한다. ATP 농도, 기질, 반응 시간, 단백질 구성체, 공유결합/시간 의존성, 검출법을 기록한다.",
              "3. 생물학적·측정 맥락이 비교 가능한 하위 코호트를 확정한 후 반복값 처리와 scaffold 분할을 정한다. 최소 표본 수나 성능을 미리 단정하지 않는다.",
              "4. 변이 미기재를 WT로 간주하지 않는다. unknown origin 표기는 인간 assay 메타데이터와 별개로 보류했다.",
              "5. CELL 키워드는 발현용 세포까지 보류할 수 있다. 형식 불명 자료도 생화학 단서가 있더라도 보류하므로 누락이 존재한다. 자동 규칙의 정확도·재현율은 검증하지 않았다.",
              "6. 분자 유형이 Small molecule로 확인된 단일 성분만 구조 후보로 둔다. 유형 결측·Unknown은 비소분자라고 단정하지 않고 별도 보류한다. 탈염·중성화·tautomer 통합·최대 조각 선택을 하지 않는다. 입체화학은 보존하고 미지정 중심을 표시한다.",
              "7. 구조 식별자는 canonical isomeric SMILES의 SHA-256이다. connectivity SMILES는 입체·동위원소 정보 없는 비교용이며 라벨 통합에 사용하지 않는다. Murcko scaffold는 chirality=False이고 비고리 구조는 빈 scaffold로 별도 집계한다. 아직 데이터 분할은 하지 않았다.", "",
              "## 산출물과 재현", "", f"감사 테이블: `{output}`. `audit_manifest.json`에 입력·출력·정책 코드 해시와 실행 환경을 기록했다.", "",
              "assay_review.csv는 자동 분류표, manual_review_queue.csv는 비어 있는 수동 검토 입력칸을 포함한 작업용 사본이다. 재실행 시 기존 폴더와 보고서를 덮어쓰지 않는다.", "", "## WT 추가 검토 대상", ""]
    lines += ["자동 선별 범위 밖의 WT 재검토 대상(후보 합산 금지):", "", "| 유일한 보류 사유 | 측정 | 실험 |", "|---|---:|---:|"]
    lines += [f"| {REASONS[k]} | {v['measurements']:,} | {v['assays']:,} |" for k, v in summary["wt_single_reason_review_pools"].items()]
    lines += ["", "구조 보류는 유형 결측·Unknown·명시적 비소분자·다성분 등을 포함하므로 분자별 상태를 확인해야 한다.", "", "## 공식 근거", ""]
    lines += [f"- [{name}]({url})" for name, url in SOURCES.items()]
    card = ["# EGFR 후보 데이터 카드", "", "상태: 자동 선별 초안. 학습용 확정 데이터가 아니며 모델 학습·평가를 실행하지 않았다.", "",
            "- 출처: ChEMBL_37, release 2026-05-01, 인간 EGFR CHEMBL203 / UniProt P00533. 실제 수집 매니페스트를 함께 확인한다.",
            "- 라이선스: ChEMBL CC BY-SA 3.0. 재배포 시 원 출처와 가공 이력을 표시하고 해당 조건을 따른다.",
            "- 단위: 정확한 양수 유한 IC50만 pIC50 = −log10(mol/L)로 계산. M·mM·uM(µM/μM)·nM·pM 지원. 질량 농도는 자동 환산하지 않는다.",
            "- 범위: confidence 9 + 직접 연결 D + 인간 assay 종·taxon 확인. B와 단백질 형식, 설명의 생화학 단서가 함께 필요하다.",
            "- WT: 명시적 WT EGFR 표현이 있어야 하고 변이 단서·구조화 변이와 충돌하면 보류한다. 변이는 P00533 메타데이터와 설명을 대조한다.",
            "- 품질: 비표준·품질 경고·잠재 중복 인용은 보류. 부등호 자료는 원문 그대로 남기며 정확 회귀 라벨로 사용하지 않는다.",
            "- 화학 처리: RDKit 파싱·canonical isomeric SMILES만 적용. 원 SMILES·전하·동위원소·입체정보 보존. 원자료 parent ID는 참고만 하며 자동 치환하지 않는다.",
            "- 반복 측정: 활동 ID 모두 유지. 다른 실험·변이·문헌의 값을 일괄 평균하지 않는다.",
            "- 제한: 문헌/assay 편향, 실험 조건 차이, 입체정보 미지정, 자동 규칙의 오분류 가능성. 원문·SI 전수 검토는 미완료.",
            "- 용도: 연구용 데이터 검토와 향후 화합물 활성 예측의 후보 선정. 임상 효능·안전성 또는 치료 권고를 의미하지 않는다.",
            "- 다음 관문: 원문 근거와 동질성 확인 → 코호트·반복 정책 확정 → 구조 그룹 및 scaffold 누출 검사 → 학습.", "",
            "전체 수치·분포·검토 제한은 [data_audit.md](data_audit.md), 기계 판독 요약은 audit_summary.json을 확인한다.", ""]
    return "\n".join(lines) + "\n", "\n".join(card) + "\n"


def audit(run_dir, *, output_dir=None, report_dir=None):
    run_dir = Path(run_dir).resolve()
    output = Path(output_dir) if output_dir else ROOT / "data/interim" / ("audit_" + run_dir.name)
    report_dir = Path(report_dir) if report_dir else ROOT / "reports"
    if output.exists() or any((report_dir / name).exists() for name in ("data_audit.md", "dataset_card.md", "audit_summary.json")):
        raise ValueError("기존 감사 결과·검토 기록을 보호합니다. 새 --output-dir와 --report-dir를 지정하세요.")
    verification = verify_collection(run_dir)
    if verification["state"] != "complete":
        raise ValueError("전체 수집이 완료된 실행만 전체 감사할 수 있습니다.")
    manifest_bytes = (run_dir / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest["release"] != verification["release"]:
        raise ValueError("검증 이후 release 기록이 변경됐습니다.")
    inputs, tables = {}, {}
    for key in ("activity", "assay", "molecule", "document"):
        record = manifest["exports"][key]
        path = run_dir / record["path"]
        blob = path.read_bytes()
        if digest(blob) != record["sha256"]:
            raise ValueError(f"검증 이후 입력 테이블이 변경됐습니다: {key}")
        tables[key] = pd.read_parquet(BytesIO(blob))
        inputs[key] = {"path": str(path.resolve()), "sha256": digest(blob)}
    frames = build_frames(tables["activity"], tables["assay"], tables["molecule"], tables["document"])
    summary = summarize(frames, tables["activity"])
    summary["release"] = manifest["release"]
    if sum(summary["exclusive_waterfall"].values()) != len(tables["activity"]) or len(frames["activity_audit"].activity_id.unique()) != len(tables["activity"]):
        raise ValueError("감사에서 측정의 누락·중복이 발생했습니다.")
    if (run_dir / "manifest.json").read_bytes() != manifest_bytes:
        raise ValueError("감사 도중 수집 매니페스트가 변경됐습니다.")
    output.mkdir(parents=True, exist_ok=False)
    report_dir.mkdir(parents=True, exist_ok=True)
    outputs = {}
    for name, frame in frames.items():
        path = output / (name + ".csv")
        atomic_bytes(path, frame.to_csv(index=False).encode("utf-8-sig"))
        outputs[name] = {"path": str(path.resolve()), "rows": len(frame), "sha256": digest(path.read_bytes())}
    data_report, card = reports(summary, output)
    # 데이터 카드의 release도 실제 수집 기록으로 대체한다.
    card = card.replace("ChEMBL_37, release 2026-05-01", f"{manifest['release']['chembl_db_version']}, release {manifest['release']['chembl_release_date']}")
    for name, content in (("data_audit.md", data_report), ("dataset_card.md", card), ("audit_summary.json", json.dumps(summary, ensure_ascii=False, indent=2))):
        path = report_dir / name
        atomic_bytes(path, content.encode())
        outputs[name] = {"path": str(path.resolve()), "sha256": digest(path.read_bytes())}
    source = Path(__file__)
    atomic_json(output / "audit_manifest.json", {
        "state": "complete", "created_at_utc": utc_now(), "policy": POLICY,
        "run_dir": str(run_dir), "source_manifest_sha256": digest(manifest_bytes),
        "release": manifest["release"], "license": "CC BY-SA 3.0", "verification": verification,
        "inputs": inputs, "outputs": outputs,
        "code_sha256": {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in (source, source.parents[1] / "labels.py")},
        "versions": {p: metadata.version(p) for p in ("pandas", "rdkit", "pyarrow")},
        "python": platform.python_version(), "platform": platform.platform(),
        "manual_review_completed": 0, "training_ready": False, "sources": SOURCES,
    })
    return {"output_dir": str(output), "report_dir": str(report_dir), **summary}
