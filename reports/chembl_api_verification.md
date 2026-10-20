# ChEMBL API·release·EGFR 소량 데이터 교차검증

확인일: 2026-10-19 (Asia/Seoul). **P0의 첫 단계인 공식 API 확인과 소량 조회를 수행했다. 전체 데이터 수집·감사·학습 코호트 확정은 아직 수행하지 않았다.**

후속 상태(2026-10-20): [전체 수집 결과](collection_chembl_full_20261020.md)에서 측정 26,600건을 실제 확보·검증했다. 당시 미확인 관계 11건은 `>>` 표기였다. 아래 내용은 최초 소량 조사 당시의 기록으로 유지한다. 실험·변이 감사와 학습 코호트 확정은 계속 후속 작업이다.

## 먼저 이해할 결론

프로젝트 표적인 `CHEMBL203`은 인간 EGFR 단일 단백질이며, 독립적인 UniProt 자료의 `P00533`·유전자명 `EGFR`·종 분류 ID `9606`과 일치했다. 실제 API가 제공하는 데이터 버전은 **ChEMBL 37**이다.

인간 EGFR·IC50 조건의 API 전체 집계는 **26,600개 측정 기록**이었다. 한 화합물을 여러 실험에서 측정한 기록이 포함되므로 **26,600개 화합물 또는 학습 표본이라는 뜻이 아니다.** 전체 자료를 내려받아 검산한 건수도 아니다.

소량 표본에서 동일 화합물·동일 논문에도 단백질 수준, 세포 내 인산화, 세포 증식 측정이 함께 존재했다. 표적 ID와 IC50만으로 모아서 학습하면 서로 다른 실험 결과를 같은 정답으로 취급하게 된다. 다음 단계는 전체 수집과 실험·변이별 감사다.

## 1. 버전 확인과 출처 간 차이

| 확인 대상 | 실제 관찰 | 해석 |
|---|---|---|
| `status.json` | `ChEMBL_37`, `UP`, `chembl_release_date=2026-05-01` | 조회 시점 API의 버전과 날짜 필드 |
| 고정 경로의 ChEMBL 37 release notes | 2026-05-01에 준비한 DB로 명시 | API 날짜와 일치 |
| 공식 ChEMBL 블로그 | 2026-05-29에 37 공개 공지 게시 | 공지 게시일과 DB 준비일은 구분 |
| 공식 Downloads 안내 페이지 | 확인 당시 36·July 2025 표시 | 안내 페이지의 버전 표기가 실제 API보다 늦게 갱신된 사례 |
| 소량 조회 전후 `status.json` | 두 응답의 전체 필드가 동일 | 이 조회 구간에서 버전 변경 신호 없음 |

API와 release notes의 전체 DB 건수도 서로 대조했다. 화합물 2,921,148개, compound record 3,824,604개, activity 24,527,044개, target 18,552개, document 101,100개가 일치했다. **이 수치는 ChEMBL 전체 DB 규모이며 EGFR 데이터 규모가 아니다.**

출처: [실제 상태 API](https://www.ebi.ac.uk/chembl/api/data/status.json), [ChEMBL 37 고정 release notes](https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/releases/chembl_37/chembl_37_release_notes.txt), [공식 37 공지](https://chembl.blogspot.com/2026/05/chembl-37-is-here-bigger-cleaner-and.html), [Downloads 안내](https://chembl.gitbook.io/chembl-interface-documentation/downloads).

## 2. 표적 정보의 교차검증

| 항목 | ChEMBL 조회 결과 | 독립 확인 |
|---|---|---|
| 표적 ID | `CHEMBL203` | accession 역조회에도 동일 ID 존재 |
| 이름 | Epidermal growth factor receptor | UniProt 권장 단백질 이름과 일치 |
| 유형 | `SINGLE PROTEIN` | 표적 구성 단백질 1개 |
| 생물종 | `Homo sapiens` | UniProt의 종과 일치 |
| 종 분류 ID | `9606` | UniProt의 taxonId와 일치 |
| 단백질 accession | `P00533` | UniProt의 primaryAccession과 일치 |
| 유전자명 | 표적 동의어와 연결 가능 | UniProt의 대표 유전자명 `EGFR` |

UniProt 기준 서열은 1,210개 아미노산이며 조회 응답의 sequenceVersion은 2였다. accession `P00533`으로 ChEMBL을 역조회하면 인간 표적 항목 15개가 나왔다. 단일 단백질 항목은 `CHEMBL203`이었고, 나머지에는 단백질 계열·키메라·단백질 상호작용 표적 등이 포함됐다. 따라서 단순히 이름에 EGFR이 들어간다는 이유로 다른 표적 ID의 자료를 합치지 않는다.

출처: [ChEMBL 표적 API](https://www.ebi.ac.uk/chembl/api/data/target/CHEMBL203.json), [accession 역조회](https://www.ebi.ac.uk/chembl/api/data/target.json?target_components__accession=P00533&organism=Homo%20sapiens&limit=20), [UniProt 원 응답](https://rest.uniprot.org/uniprotkb/P00533.json).

## 3. 조회 조건과 실제 집계

기본 조회 조건은 `target_chembl_id=CHEMBL203`, `target_organism=Homo sapiens`, `standard_type=IC50`이다. 정확값·정상형·생화학 실험 필터는 이 단계의 기본 수집 조건에 넣지 않았다. 먼저 보존한 뒤 감사에서 구분하기 위해서다.

| API 조건 | API가 보고한 측정 기록 수 | 주의점 |
|---|---:|---|
| EGFR + IC50 | 26,600 | 정제 전 기록 |
| 위 조건 + 표적 종 인간 | 26,600 | 건수 동일; 실험에 실제 사용된 단백질 종의 확정은 별도 |
| 위 조건 + `standard_relation = '='` | 19,719 | 관계가 정확값이라는 뜻; 구조·단위·실험·품질 적격성은 미확정 |
| 위 조건 + `<`, `>`, `<=`, `>=` | 5,471 | 정확값 회귀 정답으로 취급하지 않음 |
| 위 조건 + 관계값 null | 1,398 | 표본에는 수치 없이 `Not active`만 있는 기록 존재 |
| 위 조건 + 관계값 `~` | 1 | 근사값이므로 정확값과 구분 |
| 위 분류에 포함되지 않은 차이 | 11 | 관계 종류를 이번 소량 조회에서 확인하지 못함; 전체 감사에서 확인 |
| 기본 조건 + 변이 문자열 non-null | 5,025 | 변이 주석이 있는 기록; 적격 학습 표본 수가 아님 |

정확값 19,719건, 부등호 5,471건, 관계값 누락 1,398건, 근사값 1건, 미확인 잔여 11건의 합은 26,600건이다. **변이 주석 5,025건은 이 분류와 겹치는 별도 조건이므로 합산하지 않는다.** 나머지 21,575건을 자동으로 정상형이라고 판정하지 않는다.

또한 `assay?target_chembl_id=CHEMBL203&variant_sequence__isnull=false`는 2,229개 assay를 보고했지만, 이는 IC50 이외의 측정 종류도 포함하는 실험 수다. 처음 조회한 변이 assay 2개에는 IC50 기록이 0개였다. 이후 activity의 실제 스키마에 있는 `assay_variant_mutation__isnull=false`로 IC50를 다시 조회했다. **실험 수와 IC50 측정 수를 혼동하지 않았다.**

예시: [기본 소량 조회](https://www.ebi.ac.uk/chembl/api/data/activity.json?target_chembl_id=CHEMBL203&target_organism=Homo%20sapiens&standard_type=IC50&order_by=activity_id&limit=5), [정확값 조건 조회](https://www.ebi.ac.uk/chembl/api/data/activity.json?target_chembl_id=CHEMBL203&target_organism=Homo%20sapiens&standard_type=IC50&standard_relation=%3D&limit=1), [변이 주석 IC50 조회](https://www.ebi.ac.uk/chembl/api/data/activity.json?target_chembl_id=CHEMBL203&target_organism=Homo%20sapiens&standard_type=IC50&assay_variant_mutation__isnull=false&limit=2).

## 4. 실제 API 필드와 연결 방식

activity 1행은 화합물 1개에 대한 특정 실험의 측정 기록이다. 화합물·실험·문헌을 각각 ID로 연결한다.

| 원하는 정보 | 확인한 실제 API 경로·연결 |
|---|---|
| 측정 식별자 | activity의 `activity_id` |
| 화합물과 구조 | `molecule_chembl_id` → molecule 상세; `molecule_structures.canonical_smiles` |
| 원문에서 가져온 측정 | activity의 `type`, `relation`, `value`, `units` |
| ChEMBL 표준화 측정 | `standard_type`, `standard_relation`, `standard_value`, `standard_units` |
| 실험 | `assay_chembl_id` → assay 상세의 `description`, `assay_type`, `bao_format`, `bao_label` |
| 표적 연결 신뢰도 | assay 상세의 `confidence_score`, `relationship_type` |
| 변이 요약 | activity의 `assay_variant_accession`, `assay_variant_mutation` |
| 변이 상세 | assay의 중첩 객체 `variant_sequence` 안의 `accession`, `mutation`, `sequence`, `isoform`, `version` |
| 문헌 | `document_chembl_id` → document 상세의 `pubmed_id`, `doi`, `title`, `year` |
| 품질·중복 참고 | activity의 `data_validity_comment`, `potential_duplicate`, `standard_flag` |
| 새로운 측정 맥락 참고 | activity의 `modality`; 이번 표본에서는 null |

특히 로컬 설계의 `variant_id`가 그대로 API에 노출되는 것은 아니다. 조회한 activity와 assay 응답에서는 위 변이 요약·중첩 객체를 사용했다. `normalized_smiles`, `compound_group_id`, `variant_review_status`, `scaffold_group`, `split`, `exclusion_reason`은 이후 우리가 생성할 분석용 열이다.

페이지네이션은 `page_meta.limit`, `offset`, `next`, `previous`, `total_count`를 사용한다. 실제 첫 페이지 `offset=0`, 다음 페이지 `offset=5`를 따라갔으며 `next`는 호스트가 생략된 상대 URL이었다. `order_by=activity_id`로 순서를 명시했다. 첫 두 페이지의 ID는 정렬돼 있었고 중복이 없었다. 이것만으로 전체 수집의 누락이 없다고 보장하지 않는다.

출처: [공식 API 사용법](https://chembl.gitbook.io/chembl-interface-documentation/web-services/chembl-data-web-services), [activity 실제 스키마](https://www.ebi.ac.uk/chembl/api/data/activity/schema.json), [공식 변이 설명](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/target-questions).

## 5. 왜 실험을 구분해야 하는가: 실제 표본

화합물 `CHEMBL68920`은 같은 논문 `CHEMBL1134862`에서 다음 세 측정으로 나타났다.

| 측정 ID | 측정한 내용 | IC50 | 계산한 pIC50 |
|---|---|---:|---:|
| 32260 | EGFR kinase의 인산화 억제, 단일 단백질 형식 | 41 nM | 약 7.387 |
| 32263 | A431 세포에서 EGFR 자가인산화 억제 | 300 nM | 약 6.523 |
| 32265 | 인간 EGFR을 발현하는 3T3 세포의 증식 억제 | 7,820 nM | 약 5.107 |

IC50 수치가 작을수록 해당 실험에서 더 적은 농도로 50% 억제에 도달했다는 뜻이다. 세 값은 서로 다른 측정 맥락이므로 무조건 평균내지 않는다. pIC50는 농도를 로그 척도로 바꾼 값이며 커질수록 IC50 농도는 작다. 예를 들어 첫 기록의 원값은 `0.041 uM`이고 표준값은 `41 nM`로 같은 농도다.

첫 assay `CHEMBL674637`은 `confidence_score=8`, `relationship_type=H`, `assay_organism=null`이었다. 반면 세포 assay 두 개는 confidence 9였다. 즉 **표적 종이 인간이라는 필터만으로 실제 실험 단백질의 종을 확정할 수 없고, confidence 9만으로 단백질 기반 실험을 고를 수도 없다.** 공식 설명도 confidence는 실험과 표적의 연결 신뢰도를 뜻한다고 안내한다. 또한 이름에 3T3가 등장하는 사례처럼 표적 단백질 종과 실험 세포의 기원은 별개로 검토해야 한다.

출처: [단백질 assay](https://www.ebi.ac.uk/chembl/api/data/assay/CHEMBL674637.json), [세포 인산화 assay](https://www.ebi.ac.uk/chembl/api/data/assay/CHEMBL621151.json), [세포 증식 assay](https://www.ebi.ac.uk/chembl/api/data/assay/CHEMBL615325.json), [측정·품질·confidence 공식 설명](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/chembl-data-questions).

변이 표본에서는 동일 화합물 `CHEMBL387187`이 L858R 실험에서 63 nM, L861Q 실험에서 4 nM로 나타났다. 두 assay 모두 `CHEMBL203`에 연결된다. 변이 서열을 독립 UniProt 기준 서열과 비교하니 실제 차이가 각각 L858R·L861Q 표기와 일치했다. 다만 이 두 기록만으로 모든 화합물의 변이별 활성이나 환자 효과를 일반화하지 않는다.

출처: [L858R assay](https://www.ebi.ac.uk/chembl/api/data/assay/CHEMBL939338.json), [L861Q assay](https://www.ebi.ac.uk/chembl/api/data/assay/CHEMBL939339.json).

## 6. 교차검증 결과와 한계

주 표본은 activity ID 오름차순 첫 10행이며 6개 화합물·5개 assay·3개 문헌에 해당한다. 무작위 표본이 아니므로 전체 분포를 대표하지 않는다. 변이 IC50 2행을 추가해 총 12행의 상세 연결을 검사했다. 부등호·관계값 누락·근사값 응답은 별도 사례 조회다.

오프라인 검증 **12개 항목이 모두 통과**했다.

- 매니페스트의 원 응답 37개 조회 성공과 SHA-256 확인.
- 조회 전후 release 동일, API와 고정 release notes의 전체 DB 건수 일치.
- ChEMBL·UniProt의 표적 동일성 및 accession 역조회 일치.
- 첫 두 페이지 경계·순서·ID 중복 점검과 인간 조건 전후 건수 일치.
- 측정 12행의 분자 ID·SMILES·assay 설명·형식·문헌 ID·연도·변이 주석이 상세 응답과 일치.
- 수치 12행의 원 단위와 표준 단위 변환 일치. pChEMBL이 존재하는 10행은 계산 pIC50와 소수 둘째 자리 반올림 범위 내 일치.
- 변이 표본 2개의 실제 서열 차이가 변이 주석과 일치.
- 주 표본의 문헌 3편이 Europe PMC의 PMID·DOI·제목·연도와 일치.

**확인하지 않은 것:** 원 논문 본문·표의 측정 수치를 직접 대조하지 않았다. 전체 데이터의 고유 분자 수·중복·누수·단위 분포·scaffold 수·정상형 판정·학습 적격성도 아직 확인하지 않았다. 이는 모델 교차검증이나 독립 외부 성능 검증이 아니라, **API 데이터의 식별자·수치·출처 일관성에 대한 표본 검사**다. pChEMBL은 여러 endpoint에 쓰이는 필드이므로 이 프로젝트에서는 IC50 조건을 확인한 뒤에만 pIC50와 대조한다.

문헌 대조 출처: [Europe PMC 메타데이터 조회](https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=%28EXT_ID%3A12127526%20OR%20EXT_ID%3A2552117%20OR%20EXT_ID%3A13678409%29%20AND%20SRC%3AMED&format=json&resultType=core&pageSize=3).

## 7. 보관 파일과 재실행

- 원 응답: `data/raw/api_probe_20261019T141453676518Z/` — Git 제외. 처음 수행한 더 작은 탐색 응답은 별도 폴더에 유지했다.
- 조회 구간: 2026-10-19 14:14:53–14:16:46 UTC, 한국 시각 23:14:53–23:16:46.
- 공개 검토용 기록: [매니페스트](chembl_api_probe_manifest.json), [검증 결과](chembl_api_probe_validation.json).
- [소량 조회 스크립트](../scripts/probe_chembl_api.py), [오프라인 검증 스크립트](../scripts/check_chembl_probe.py).
- 실행 환경: 기존 `.venv`의 Python 3.12.14, 표준 라이브러리만 사용. ML 패키지 설치·lock 생성은 미수행.

```bash
# 새 소량 조회: 현재 API를 다시 호출하므로 이후 결과는 달라질 수 있음
.venv/bin/python scripts/probe_chembl_api.py

# 이번에 보관한 응답을 네트워크 없이 재검증
.venv/bin/python scripts/check_chembl_probe.py data/raw/api_probe_20261019T141453676518Z
```

`--resume <기존 폴더>`는 URL·해시가 일치하는 성공 응답을 재사용하고 종료 시 status를 갱신한다. 최신 데이터를 새로 확인하려면 `--resume` 없이 실행한다. 이 도구는 소량 탐색용이며 전체 수집의 재시작·무결성 보장 기능을 대체하지 않는다.

다음 작업은 필요한 P0 패키지의 호환성 확인·버전 고정과 전체 수집기 구현이다. 수집기는 버전 변경, 전체 페이지 누락, 측정 ID 중복, 연결 누락을 검사해야 한다. 이후 미확인 관계 11건을 포함한 전체 분포를 감사하고 실험·변이 검토표와 학습 코호트를 만든다.
