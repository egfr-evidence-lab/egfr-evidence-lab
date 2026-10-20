"""전체 수집·상세 연결·분석 테이블 생성·오프라인 무결성 검사."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from importlib import metadata
from pathlib import Path
import platform
import time

from .chembl import BASE, RESOURCES, ChEMBLClient, next_url, url_for, validate_page
from .store import CollectionError, RunStore, atomic_bytes, atomic_json, digest, exclusive_run, utc_now


ROOT = Path(__file__).resolve().parents[3]
SCOPE = {"target_chembl_id": "CHEMBL203", "target_organism": "Homo sapiens", "standard_type": "IC50"}


def source_digest():
    paths = sorted(Path(__file__).parent.glob("*.py")) + [Path(__file__).parents[1] / "__main__.py"]
    return digest(b"".join(p.name.encode() + b"\0" + p.read_bytes() for p in paths))


def release(status):
    if status.get("status") != "UP" or not status.get("chembl_db_version") or not status.get("chembl_release_date"):
        raise CollectionError("ChEMBL 정상 상태·release 정보를 확인할 수 없습니다.")
    return {k: status[k] for k in ("chembl_db_version", "chembl_release_date")}


def identifiers(rows, field):
    return {row[field] for row in rows if row.get(field) not in (None, "")}


def read_stream(store, stream):
    resource, params = stream["resource"], stream["params"]
    rows, seen, previous, offset, total = [], set(), None, 0, None
    url = url_for(resource, params)
    if not stream["keys"]:
        raise CollectionError("빈 스트림 기록입니다.")
    for i, key in enumerate(stream["keys"]):
        value = store.read(key, url)
        if value is None:
            raise CollectionError(f"스트림 요청 기록 누락: {key}")
        page, meta, previous = validate_page(value, resource, offset, total, seen, previous)
        total = meta["total_count"]
        rows.extend(page)
        offset += len(page)
        if i < len(stream["keys"]) - 1:
            if not meta.get("next"):
                raise CollectionError("마지막 페이지 뒤에 추가 페이지가 기록됐습니다.")
            url = next_url(url, meta["next"], params, resource, offset)
        elif bool(meta.get("next")) != bool(stream["partial"]):
            raise CollectionError("스트림 완료 상태와 마지막 응답이 다릅니다.")
    if stream["total_count"] != total:
        raise CollectionError("스트림 total_count와 원 응답이 다릅니다.")
    return rows


def snapshots(store):
    streams = store.manifest["streams"]
    if "activities" not in streams:
        raise CollectionError("측정 스트림이 없습니다.")
    data = {resource: [] for resource in RESOURCES}
    for name, stream in sorted(streams.items()):
        resource = stream["resource"]
        if resource not in RESOURCES or (resource == "activity" and name != "activities"):
            raise CollectionError("알 수 없거나 중복된 측정 스트림입니다.")
        rows = read_stream(store, stream)
        if resource == "activity":
            expected = {**SCOPE, "order_by": "activity_id", "limit": store.manifest["options"]["page_size"]}
            if stream["params"] != expected:
                raise CollectionError("측정 스트림의 수집 조건이 다릅니다.")
            max_pages = store.manifest["options"]["max_pages"]
            if stream["partial"] and (max_pages is None or len(stream["keys"]) != max_pages):
                raise CollectionError("제한 실행과 페이지 수가 일치하지 않습니다.")
            if any(any(row.get(k) != v for k, v in SCOPE.items()) for row in rows):
                raise CollectionError("요청 조건 밖의 측정이 반환됐습니다.")
        else:
            field = RESOURCES[resource][1]
            wanted = set(stream["params"][field + "__in"].split(","))
            if stream["partial"] or identifiers(rows, field) != wanted:
                raise CollectionError(f"상세 ID 누락·추가 또는 미완료: {name}")
        data[resource].extend(rows)
    for resource, rows in data.items():
        field = RESOURCES[resource][1]
        if len(identifiers(rows, field)) != len(rows):
            raise CollectionError(f"자원 간 묶음 조회에 중복 ID가 있습니다: {resource}")
    expected = {"assay": identifiers(data["activity"], "assay_chembl_id"),
                "molecule": identifiers(data["activity"], "molecule_chembl_id"),
                "document": identifiers(data["activity"], "document_chembl_id") |
                            identifiers(data["assay"], "document_chembl_id")}
    for resource, wanted in expected.items():
        got = identifiers(data[resource], RESOURCES[resource][1])
        if got != wanted:
            raise CollectionError(f"관련 {resource} 연결 누락 또는 예상 밖 ID: 누락 {len(wanted-got)}, 추가 {len(got-wanted)}")
    return data


def summary(data, store):
    rows = data["activity"]
    def counts(field):
        return dict(sorted(Counter("<null>" if r.get(field) is None else str(r[field]) for r in rows).items()))
    return {"api_total_count": store.manifest["streams"]["activities"]["total_count"],
            "activities": len(rows), "molecules": len(data["molecule"]), "assays": len(data["assay"]),
            "documents": len(data["document"]),
            "activity_documents": len(identifiers(rows, "document_chembl_id")),
            "relations": counts("standard_relation"), "units": counts("standard_units"),
            "assay_types": counts("assay_type"), "bao_formats": counts("bao_label"),
            "validity_comments": counts("data_validity_comment"), "sources": counts("src_id"),
            "variant_annotation_non_null": sum(r.get("assay_variant_mutation") is not None for r in rows),
            "null_reference_counts": {field: sum(r.get(field) in (None, "") for r in rows)
                                      for field in ("molecule_chembl_id", "assay_chembl_id", "document_chembl_id")},
            "scientific_curation_complete": False, "training_cohort_approved": False}


ACTIVITY_FIELDS = ["activity_id", "molecule_chembl_id", "parent_molecule_chembl_id", "assay_chembl_id",
                   "document_chembl_id", "target_chembl_id", "target_organism", "target_tax_id",
                   "type", "relation", "value", "units", "standard_type", "standard_relation",
                   "standard_value", "standard_units", "standard_upper_value", "standard_text_value",
                   "pchembl_value", "canonical_smiles", "assay_description", "assay_type", "bao_format",
                   "bao_label", "assay_variant_accession", "assay_variant_mutation", "data_validity_comment",
                   "potential_duplicate", "standard_flag", "src_id", "document_year", "modality"]
ASSAY_FIELDS = ["assay_chembl_id", "target_chembl_id", "document_chembl_id", "description", "assay_type",
                "bao_format", "bao_label", "confidence_score", "relationship_type", "assay_organism",
                "assay_tax_id", "assay_cell_type", "cell_chembl_id", "src_id"]
DOCUMENT_FIELDS = ["document_chembl_id", "doi", "pubmed_id", "year", "title", "journal", "doc_type", "src_id"]
INTEGER_FIELDS = {"activity_id", "potential_duplicate", "standard_flag", "src_id", "document_year",
                  "confidence_score", "assay_tax_id", "year", "variant_isoform", "variant_version"}


def tables(data):
    import pandas as pd
    result = {}
    for resource in RESOURCES:
        converted = []
        if resource == "activity":
            fields = ACTIVITY_FIELDS
        elif resource == "assay":
            fields = ASSAY_FIELDS + ["variant_accession", "variant_mutation", "variant_sequence",
                                     "variant_isoform", "variant_version"]
        elif resource == "molecule":
            fields = ["molecule_chembl_id", "pref_name", "molecule_type", "canonical_smiles",
                      "standard_inchi_key", "parent_chembl_id"]
        else:
            fields = DOCUMENT_FIELDS
        for record in data[resource]:
            row = {field: record.get(field) for field in fields}
            if resource == "assay":
                variant = record.get("variant_sequence") or {}
                for name in ("accession", "mutation", "sequence", "isoform", "version"):
                    row["variant_" + name] = variant.get(name)
            elif resource == "molecule":
                structures, hierarchy = record.get("molecule_structures") or {}, record.get("molecule_hierarchy") or {}
                row.update(canonical_smiles=structures.get("canonical_smiles"),
                           standard_inchi_key=structures.get("standard_inchi_key"),
                           parent_chembl_id=hierarchy.get("parent_chembl_id"))
            converted.append(row)
        # Construct nullable columns directly: inferring int+null as float first
        # would turn a PMID such as 12345 into the incorrect string "12345.0".
        frame = pd.DataFrame({field: pd.array([row[field] for row in converted],
                                             dtype="Int64" if field in INTEGER_FIELDS else "string")
                              for field in fields})
        result[resource] = frame
    joined = result["activity"].copy()
    for resource in ("assay", "molecule", "document"):
        key = RESOURCES[resource][1]
        prefix = resource + "_detail__"
        joined = joined.merge(result[resource].add_prefix(prefix), how="left", left_on=key,
                              right_on=prefix+key, sort=False, validate="many_to_one")
        missing = joined[key].notna() & joined[prefix+key].isna()
        if missing.any():
            raise CollectionError(f"테이블 결합 후 {resource} 연결 누락: {int(missing.sum())}")
    if len(joined) != len(data["activity"]) or joined["activity_id"].nunique() != len(joined):
        raise CollectionError("테이블 결합 과정에서 측정 행 수가 달라졌습니다.")
    result["joined"] = joined
    return result


def write_tables(data, store, output):
    output.mkdir(parents=True, exist_ok=True)
    owner = output / ".collection_owner.json"
    if owner.exists():
        if json.loads(owner.read_text())["run_id"] != store.manifest["run_id"]:
            raise CollectionError("분석 테이블 폴더가 다른 실행에 속합니다. 기존 자료를 덮어쓰지 않습니다.")
    elif any(output.iterdir()):
        raise CollectionError("소유 기록이 없는 기존 분석 폴더입니다. 새 실행 폴더 이름을 사용하세요.")
    else:
        atomic_json(owner, {"run_id": store.manifest["run_id"]})
    for name, frame in tables(data).items():
        path = output / ("measurements_joined.parquet" if name == "joined" else RESOURCES[name][0] + ".parquet")
        # Serialize to an in-memory buffer, then atomically replace the destination.
        atomic_bytes(path, frame.to_parquet(engine="pyarrow", index=False))
        store.export(name, path)


def verify_collection(run_dir, check_exports=True):
    store = RunStore(run_dir, resume=True)
    m = store.manifest
    if m["state"] not in {"complete", "preview_complete"}:
        raise CollectionError(f"완료된 실행이 아닙니다: {m['state']}")
    for key in m["requests"]:
        store.read(key)
    before = release(store.read(m["status_before_key"]))
    after = release(store.read(m["status_after_key"]))
    if before != after or before != m["release"]:
        raise CollectionError("수집 전후 release가 일치하지 않습니다.")
    target = store.read("target")
    if target.get("target_chembl_id") != SCOPE["target_chembl_id"] or target.get("organism") != SCOPE["target_organism"]:
        raise CollectionError("보관한 표적 정보가 수집 조건과 다릅니다.")
    data = snapshots(store)
    result = summary(data, store)
    final_count = store.read(m["count_after_key"])["page_meta"]["total_count"]
    if final_count != result["api_total_count"]:
        raise CollectionError("수집 종료 시 API 전체 건수가 변경됐습니다.")
    if m["options"]["max_pages"] is None and (m["state"] != "complete" or result["activities"] != final_count):
        raise CollectionError("전체 수집 건수가 일치하지 않습니다.")
    if m["options"]["max_pages"] is not None and m["state"] != "preview_complete":
        raise CollectionError("제한 실행을 전체 완료로 기록했습니다.")
    if result != m["summary"]:
        raise CollectionError("보관 자료와 요약 통계가 다릅니다.")
    if check_exports:
        import pandas as pd
        expected_tables = tables(data)
        if set(m["exports"]) != set(expected_tables):
            raise CollectionError("분석 테이블 산출물 목록이 맞지 않습니다.")
        for name, record in m["exports"].items():
            path = store.path / record["path"]
            if not path.is_file() or path.stat().st_size != record["bytes"] or digest(path.read_bytes()) != record["sha256"]:
                raise CollectionError(f"분석 파일 누락·해시 불일치: {name}")
            try:
                pd.testing.assert_frame_equal(expected_tables[name], pd.read_parquet(path, engine="pyarrow"))
            except AssertionError as exc:
                raise CollectionError(f"원 응답과 분석 테이블 내용이 다릅니다: {name}") from exc
    return {"verified_at_utc": utc_now(), "passed": True, "state": m["state"], "release": before,
            "raw_responses": len(m["requests"]), "exports_verified": check_exports, "summary": result,
            "limit": "기술적 수집 무결성 확인; 실험·변이 적격성 판단과 구조 정제는 후속 작업"}


def collect(run_dir, *, page_size=500, batch_size=50, workers=3, max_pages=None, resume=False,
            client=None, sleeper=time.sleep, derived_dir=None, report_dir=None):
    for name, value, upper in (("page_size", page_size, 1000), ("batch_size", batch_size, 100), ("workers", workers, 3)):
        if type(value) is not int or not 1 <= value <= upper:
            raise CollectionError(f"{name}은 1~{upper} 범위 정수여야 합니다.")
    if max_pages is not None and (type(max_pages) is not int or max_pages < 1):
        raise CollectionError("max_pages는 양의 정수여야 합니다.")
    options = {"scope": SCOPE, "page_size": page_size, "batch_size": batch_size,
               "workers": workers, "max_pages": max_pages}
    with exclusive_run(run_dir):
        store = RunStore(run_dir, options, resume)
        attempt = len(store.manifest["attempts"])
        store.manifest["attempts"].append({"started_at_utc": utc_now(), "source_sha256": source_digest(),
                                           "python": platform.python_version(), "platform": platform.platform(),
                                           "packages": {name: metadata.version(name)
                                                        for name in ("httpx", "numpy", "pandas", "rdkit", "pyarrow")}})
        store.update(state="collecting", source={
            "name": "ChEMBL", "api_base": BASE, "license": "CC BY-SA 3.0",
            "license_reference": "https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/general-questions",
            "citation_doi": "10.1093/nar/gkad1004"})
        api = ChEMBLClient(store, client, sleeper=sleeper)
        try:
            before_key = f"status_before_{attempt:04d}"
            before = api.get(before_key, url_for("status"))
            current_release = release(before)
            if store.manifest.get("release") not in (None, current_release):
                raise CollectionError("기존 실행과 현재 release가 다릅니다. 새 실행 폴더로 수집하세요.")
            store.update(release=current_release, status_before_key=before_key)
            target = api.get("target", BASE + "target/CHEMBL203.json")
            if target.get("organism") != "Homo sapiens" or target.get("target_chembl_id") != "CHEMBL203":
                raise CollectionError("인간 EGFR 표적 확인 실패")
            print(f"수집 버전: {current_release['chembl_db_version']} | 실행 폴더: {store.path}", flush=True)
            activities = api.pages("activities", "activity", {**SCOPE, "order_by": "activity_id", "limit": page_size},
                                   max_pages, lambda n, total: print(f"측정 수집: {n:,}/{total:,}", flush=True))

            def details(resource, wanted):
                plural, field = RESOURCES[resource]
                wanted = sorted(wanted)
                batches = [wanted[i:i+batch_size] for i in range(0, len(wanted), batch_size)]
                result = []
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    jobs = {pool.submit(api.pages, f"{plural}_{i:06d}", resource,
                                        {field+"__in": ",".join(batch), "order_by": field, "limit": page_size}): batch
                            for i, batch in enumerate(batches)}
                    try:
                        for done, future in enumerate(as_completed(jobs), 1):
                            rows = future.result()
                            if identifiers(rows, field) != set(jobs[future]):
                                raise CollectionError(f"{plural} 묶음 조회에 누락·추가 ID가 있습니다.")
                            result.extend(rows)
                            if done % 10 == 0 or done == len(batches):
                                print(f"{plural} 상세 수집: 묶음 {done}/{len(batches)} | 자료 {len(result):,}건", flush=True)
                    except BaseException:
                        api.cancelled.set()
                        for future in jobs:
                            future.cancel()
                        raise
                return result

            assays = details("assay", identifiers(activities, "assay_chembl_id"))
            details("molecule", identifiers(activities, "molecule_chembl_id"))
            details("document", identifiers(activities, "document_chembl_id") | identifiers(assays, "document_chembl_id"))
            count_key, after_key = f"count_after_{attempt:04d}", f"status_after_{attempt:04d}"
            count = api.get(count_key, url_for("activity", {**SCOPE, "order_by": "activity_id", "limit": 1}))
            after = api.get(after_key, url_for("status"))
            if release(after) != current_release:
                raise CollectionError("수집 중 release가 변경됐습니다. 새 실행으로 재수집하세요.")
            data = snapshots(store)
            stats = summary(data, store)
            if count["page_meta"]["total_count"] != stats["api_total_count"]:
                raise CollectionError("수집 종료 시 전체 건수가 달라졌습니다.")
            output = Path(derived_dir) if derived_dir else ROOT / "data/interim" / store.path.name
            write_tables(data, store, output)
            state = "complete" if max_pages is None else "preview_complete"
            store.update(state=state, summary=stats, status_after_key=after_key, count_after_key=count_key,
                         completed_at_utc=utc_now())
            validation = verify_collection(store.path)
            reports = Path(report_dir) if report_dir else ROOT / "reports"
            reports.mkdir(parents=True, exist_ok=True)
            stem = "collection_" + store.path.name
            atomic_json(reports / (stem + ".json"), validation)
            lines = ["# ChEMBL 수집 결과", "", f"검증 시각(UTC): {validation['verified_at_utc']}", "",
                     f"상태: **{state}**. " + ("전체 조건 일치 측정 수집 완료." if state == "complete" else "제한 실행이며 전체 수집 완료가 아님."),
                     f"Release: {current_release['chembl_db_version']} / {current_release['chembl_release_date']}", "",
                     f"측정 {stats['activities']:,}건 / API 집계 {stats['api_total_count']:,}건",
                     f"분자 {stats['molecules']:,}개 / 실험 {stats['assays']:,}개 / 문헌 {stats['documents']:,}개", "",
                     "## 관계값 분포", "", "| 관계값 | 측정 수 |", "|---|---:|"]
            lines.extend(f"| {key} | {value:,} |" for key, value in stats["relations"].items())
            lines.extend(["", f"원 응답 {validation['raw_responses']}개와 분석 테이블 5개의 해시·내용·연결을 오프라인 검증함.",
                          f"측정의 원래 비어 있는 연결값: {json.dumps(stats['null_reference_counts'], ensure_ascii=False)}", "",
                          "변이·실험 적격성 검토, 화학 정규화, 학습 코호트 확정과 모델 학습은 수행하지 않음.",
                          "API의 동일 release·건수 확인은 트랜잭션 스냅샷 보장이 아니며, 고정 release 다운로드와 동일하다고 주장하지 않음.", "",
                          "출처: [ChEMBL API](https://www.ebi.ac.uk/chembl/api/data/docs), "
                          "[공식 API 설명](https://chembl.gitbook.io/chembl-interface-documentation/web-services/chembl-data-web-services).",
                          "ChEMBL 원 데이터 라이선스: CC BY-SA 3.0. 출처·release·가공 이력을 함께 기록할 것. "
                          "[공식 라이선스 설명](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/general-questions).", ""])
            atomic_bytes(reports / (stem + ".md"), "\n".join(lines).encode())
            print(f"검증 완료: {state} | 측정 {stats['activities']:,}건 | 보고서 {reports / (stem+'.md')}", flush=True)
            return validation
        except BaseException as exc:
            store.error({"stage": "collection", "error": f"{type(exc).__name__}: {exc}"})
            store.update(state="interrupted" if isinstance(exc, KeyboardInterrupt) else "failed")
            raise
        finally:
            api.close()
