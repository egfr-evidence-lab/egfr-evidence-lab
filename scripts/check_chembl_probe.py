"""저장한 소량 ChEMBL 응답을 오프라인 교차검증한다. 전체 데이터 감사가 아니다."""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from egfr_lab.labels import ic50_to_pic50


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_directory", type=Path, help="소량 API 원 응답 폴더")
    args = parser.parse_args()
    folder = args.evidence_directory
    results = []

    def read(name):
        return json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))

    def check(name, passed, detail):
        results.append({"check": name, "passed": bool(passed), "detail": detail})

    manifest = read("manifest")
    failures = [r["name"] for r in manifest["requests"] if r.get("failed")]
    check("조회 성공", not failures, {"실패한 요청": failures, "요청 수": len(manifest["requests"])})
    hashes = {r["name"]: hashlib.sha256((folder / r["file"]).read_bytes()).hexdigest() == r["sha256"]
              for r in manifest["requests"] if not r.get("failed")}
    check("원 응답 SHA-256", all(hashes.values()), hashes)
    before, after = read("status_before"), read("status_after")
    check("조회 전후 release", before == after, {"이전": before, "이후": after})
    release_notes = (folder / "release_notes.txt").read_text(encoding="utf-8")
    totals = {"disinct_compounds": "compounds", "compound_records": "compound records",
              "activities": "activities", "targets": "targets", "publications": "documents"}
    release_comparisons = {}
    for key, label in totals.items():
        found = re.search(r"([\d,]+) " + re.escape(label) + r"\b", release_notes)
        release_comparisons[key] = bool(found and int(found.group(1).replace(",", "")) == before[key])
    check("API와 고정 release notes 전역 건수", all(release_comparisons.values()), release_comparisons)
    target, uniprot = read("target"), read("uniprot")
    component = target["target_components"][0]
    target_ok = (target["target_chembl_id"] == "CHEMBL203" and target["target_type"] == "SINGLE PROTEIN"
                 and component["accession"] == uniprot["primaryAccession"] == "P00533"
                 and target["tax_id"] == uniprot["organism"]["taxonId"] == 9606
                 and target["organism"] == uniprot["organism"]["scientificName"] == "Homo sapiens"
                 and uniprot["genes"][0]["geneName"]["value"] == "EGFR")
    check("ChEMBL・UniProt 표적 동일성", target_ok,
          {"표적": target["target_chembl_id"], "UniProt": component["accession"], "분류 ID": target["tax_id"]})
    single = [r["target_chembl_id"] for r in read("target_by_accession")["targets"]
              if r["target_type"] == "SINGLE PROTEIN"]
    check("UniProt accession 역방향 조회", single == ["CHEMBL203"], {"단일 단백질 표적": single})
    page1, page2 = read("activities_page1"), read("activities_page2")
    first, second = page1["activities"], page2["activities"]
    primary = first + second
    ids = [r["activity_id"] for r in primary]
    check("페이지 경계와 ID 중복", len(ids) == len(set(ids)) == 10 and ids == sorted(ids)
          and page1["page_meta"]["offset"] == 0 and page2["page_meta"]["offset"] == len(first)
          and page1["page_meta"]["total_count"] == page2["page_meta"]["total_count"],
          {"측정 ID": ids, "주의": "앞 두 페이지만 점검; 전체 누락 검증 아님"})
    total = page1["page_meta"]["total_count"]
    check("인간 조건 추가 전후 API 건수", total == read("activities_target_only")["page_meta"]["total_count"],
          {"표적만 지정": read("activities_target_only")["page_meta"]["total_count"], "인간 조건 추가": total})
    samples = primary + read("activities_variant_ic50")["activities"]
    link_results, numeric_results, variant_results = [], [], []
    for row in samples:
        assay = read("assay_" + row["assay_chembl_id"])
        molecule = read("molecule_" + row["molecule_chembl_id"])
        document = read("document_" + row["document_chembl_id"])
        variant = assay["variant_sequence"]
        links_ok = (row["target_chembl_id"] == assay["target_chembl_id"] == "CHEMBL203"
                    and row["molecule_chembl_id"] == molecule["molecule_chembl_id"]
                    and row["canonical_smiles"] == molecule["molecule_structures"]["canonical_smiles"]
                    and row["document_chembl_id"] == assay["document_chembl_id"] == document["document_chembl_id"]
                    and row["document_year"] == document["year"]
                    and row["assay_description"] == assay["description"]
                    and row["assay_type"] == assay["assay_type"]
                    and row["bao_format"] == assay["bao_format"]
                    and row["assay_variant_mutation"] == (variant["mutation"] if variant else None))
        link_results.append({"activity_id": row["activity_id"], "passed": links_ok})
        p_standard = ic50_to_pic50(float(row["standard_value"]), row["standard_units"], row["standard_relation"])
        p_original = ic50_to_pic50(float(row["value"]), row["units"], row["relation"])
        numerical_ok = math.isclose(p_standard, p_original, abs_tol=1e-8)
        pchembl_error = None
        if row["pchembl_value"] is not None:
            pchembl_error = abs(p_standard - float(row["pchembl_value"]))
            numerical_ok = numerical_ok and pchembl_error <= 0.0051
        numeric_results.append({"activity_id": row["activity_id"], "passed": numerical_ok,
                                "pic50": p_standard, "pchembl_rounding_error": pchembl_error})
        if variant:
            sequence, reference = variant["sequence"], uniprot["sequence"]["value"]
            differences = ([f"{a}{i}{b}" for i, (a, b) in enumerate(zip(reference, sequence), 1) if a != b]
                           if len(sequence) == len(reference) else [])
            expected = variant["mutation"].split(",")
            variant_results.append({"assay": assay["assay_chembl_id"], "expected": expected,
                                    "observed": differences,
                                    "passed": len(sequence) == len(reference) and sorted(differences) == sorted(expected)})
    check("측정·분자·실험·문헌 연결", all(r["passed"] for r in link_results), link_results)
    check("원 단위・표준 단위・pChEMBL 수치", all(r["passed"] for r in numeric_results), numeric_results)
    check("변이 서열과 UniProt 기준 서열", bool(variant_results) and all(r["passed"] for r in variant_results), variant_results)
    epmc = {r["id"]: r for r in read("europepmc_documents")["resultList"]["result"]}
    documents = {r["document_chembl_id"] for r in primary}
    external_results = []
    for identifier in sorted(documents):
        d = read("document_" + identifier)
        match = epmc.get(str(d["pubmed_id"]))
        passed = bool(match and match["doi"].lower() == d["doi"].lower()
                      and match["title"] == d["title"] and int(match["pubYear"]) == d["year"])
        external_results.append({"document": identifier, "PMID": d["pubmed_id"], "passed": passed})
    check("Europe PMC 문헌 메타데이터", all(r["passed"] for r in external_results), external_results)
    counts = {"전체": total, "정확값 관계 =": read("activities_exact")["page_meta"]["total_count"],
              "부등호 < > <= >=": read("activities_censored")["page_meta"]["total_count"],
              "관계값 null": read("activities_relation_missing")["page_meta"]["total_count"],
              "근사 관계 ~": read("activities_approximate")["page_meta"]["total_count"]}
    counts["나머지 관계 미확인"] = total - sum(v for k, v in counts.items() if k != "전체")
    summary = {"전체 검사 통과": all(r["passed"] for r in results), "checks": results,
               "API 집계": counts, "변이 문자열 non-null IC50 기록": read("activities_variant_ic50")["page_meta"]["total_count"],
               "주 표본": {"측정": len(primary), "분자": len({r['molecule_chembl_id'] for r in primary}),
                           "실험": len({r['assay_chembl_id'] for r in primary}),
                           "문헌": len(documents), "형식": dict(Counter(r['bao_label'] for r in primary))},
               "연결 검증 표본": len(samples),
               "제한": "비무작위 소량 표본. 전체 데이터 품질·논문 원문 수치·학습 적격성은 검증하지 않음."}
    (folder / "validation.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "checks"}, ensure_ascii=False, indent=2))
    for result in results:
        print(("통과" if result["passed"] else "실패") + ": " + result["check"])
    if not summary["전체 검사 통과"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
