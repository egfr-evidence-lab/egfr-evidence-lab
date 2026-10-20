# ChEMBL 전체 수집기 사용법

구현일: 2026-10-20. Python 3.12·macOS arm64에서 검증한 P0 환경을 사용한다. [패키지 설치](../requirements/README.md) 후 프로젝트 루트에서 실행한다.

## 수집 범위와 단계 구분

수집 조건은 인간 EGFR `CHEMBL203`, `target_organism=Homo sapiens`, `standard_type=IC50`로 고정돼 있다. confidence·실험 형식·변이·부등호·품질 플래그로 자료를 미리 제외하지 않는다. 원값·표준값·SMILES·관련 상세 응답을 보존한다.

이번 수집기는 **기술적인 수집 무결성**을 검사한다. 실험·변이 적격성 검토, 화학 정규화, 반복 측정 요약, 학습 분할·모델 학습은 후속 단계다. 표적 종 조건을 실험 단백질 종의 확정으로 해석하지 않고, 변이 주석 null을 정상형 확정으로 바꾸지 않는다.

## 명령

```bash
# 새 전체 수집
PYTHONPATH=src .venv/bin/python -m egfr_lab collect --run-dir data/raw/chembl_full_20261020

# 같은 조건으로 중단 지점에서 재개
PYTHONPATH=src .venv/bin/python -m egfr_lab collect --run-dir data/raw/chembl_full_20261020 --resume

# 저장된 원 응답과 테이블을 네트워크 없이 검증
PYTHONPATH=src .venv/bin/python -m egfr_lab verify-collection data/raw/chembl_full_20261020
```

기존 실행 폴더에는 `--resume` 없이 쓰지 않는다. 새 실험을 하려면 다른 폴더 이름을 사용한다. `--run-dir`를 생략하면 UTC 시각을 포함한 새 실행 폴더를 만든다. 실행 간 원자료·실행 기록을 합치지 않는다.

제한 실행 예시:

```bash
PYTHONPATH=src .venv/bin/python -m egfr_lab collect --run-dir data/raw/chembl_preview_20261020 --page-size 5 --batch-size 3 --max-pages 2
```

`--max-pages`는 측정 수집 페이지만 제한하며, 그 측정에 연결된 상세 자료는 모두 조회한다. 이 경우 항상 `preview_complete`로 기록해 전체 완료와 구분한다. 제한 실행을 재시작할 때도 같은 `--page-size`, `--batch-size`, `--workers`, `--max-pages`를 전달한다. 제한 실행 폴더를 전체 실행으로 전환하지 않는다.

| 옵션 | 기본값 | 동작 |
|---|---:|---|
| --page-size | 500 | 요청 페이지 크기; 허용 설정 1~1,000 |
| --batch-size | 50 | 상세 조회 ID 묶음 크기; 허용 설정 1~100 |
| --workers | 3 | 상세 요청 동시 작업 수; 1~3 |
| --max-pages | 제한 없음 | 지정 시 소량 실행으로 기록 |
| --resume | 꺼짐 | 같은 옵션의 기존 원 응답을 해시 확인 후 재사용 |

위 범위는 수집기의 운영 설정이며 API 전체 자원에서 보장하는 최적값이라는 뜻은 아니다.

## 동작 순서

1. 실행 폴더 잠금을 얻어 같은 경로의 동시 쓰기를 막는다.
2. 현재 API status·release와 인간 EGFR 표적을 확인한다. 재시작 시 원래 release와 다르면 중단한다.
3. activity ID 오름차순으로 페이지를 따라간다. 매 페이지의 offset·건수·ID 순서·중복·다음 URL의 필터를 검사한다.
4. 측정의 고유 assay ID를 묶음 조회한다. variant_sequence 중첩 객체도 원 응답에 보관한다.
5. 측정의 고유 molecule ID를 묶음 조회한다. 원 구조와 molecule_hierarchy 등 상세 응답을 보관한다.
6. 측정과 assay 양쪽에서 등장한 document ID의 합집합을 조회한다. assay에만 연결된 문헌도 빠뜨리지 않는다.
7. 종료 시 측정 API 집계와 release를 다시 조회해 시작 시점과 대조한다.
8. 분석 테이블을 생성하고 원 응답·표·건수·연결을 오프라인으로 다시 검사한다.
9. 검사 후에만 `complete` 또는 `preview_complete`와 보고서를 기록한다. 실패하면 성공 상태로 남기지 않는다.

## 저장 위치

```text
data/raw/<실행 폴더>/
  responses/             요청별 원 JSON 응답
  manifest.json          조건·release·요청·시각·해시·오류·실행 코드 해시
  checkpoint.json        진행 상태 요약; 기준 기록은 manifest.json
  .collection.lock       OS 프로세스 잠금용 파일

data/interim/<실행 폴더>/
  activities.parquet
  assays.parquet
  molecules.parquet
  documents.parquet
  measurements_joined.parquet
  .collection_owner.json 실행 소유 기록

reports/
  collection_<실행 폴더>.md
  collection_<실행 폴더>.json
```

원 응답과 중간 데이터는 기존 `.gitignore`에 따라 Git에서 제외한다. 보고서는 파일 수·집계·검증 결과를 남긴다. 데이터 공개 여부는 원자료 크기·출처·라이선스를 검토해 별도로 정한다.

Parquet은 분석용으로 선택한 필드를 명시적인 자료형으로 저장한다. 숫자처럼 보이는 원 측정값은 원래 표기를 보존하도록 문자열로 유지하고, activity ID·연도·일부 플래그는 nullable 정수로 저장한다. 분석용 테이블에 선택하지 않은 중첩 정보도 원 JSON에는 남아 있다.

결합 표는 측정 1건당 1행이다. 상세 열은 `assay_detail__`, `molecule_detail__`, `document_detail__` 접두어를 써서 activity에 원래 있던 요약값을 덮어쓰지 않는다. `many_to_one` 결합을 검사하고, 관련 상세 자료가 빠지거나 행 수가 변하면 실패한다.

## 실패와 재개

- 연결·타임아웃·408·429·5xx·잘못된 JSON은 최대 3회 시도한다. 일반적인 나머지 4xx는 반복하지 않는다.
- 대기 시간은 지수 증가와 `Retry-After`를 반영한다. 서버가 60초보다 긴 대기를 요구하면 상태를 보존해 중단하고 이후 재개하도록 안내한다.
- 모든 성공 응답은 파일 저장 후 매니페스트를 원자적으로 갱신한다. checkpoint는 요약이므로 갱신 도중 중단돼도 매니페스트로 재개한다.
- 완료한 응답은 요청 URL·바이트 수·SHA-256·JSON을 확인한 뒤 재사용한다. 진행 중 실패한 페이지는 다음 실행에서 다시 요청한다.
- 해시가 틀리거나 원 파일이 없으면 성공으로 간주하지 않는다. 손상 원본을 임의로 덮어쓰지 말고 새 실행 폴더에 재수집한다.
- 상세 요청 실패 시 아직 시작하지 않은 작업을 취소한다. 이미 진행 중인 최대 3개 요청은 종료·타임아웃까지 기다릴 수 있다.
- Ctrl+C는 `interrupted` 상태와 기존 성공 응답을 남긴다. 프로세스 강제 종료 시에도 다음 실행에서 OS 잠금은 풀리고 매니페스트를 읽어 재개할 수 있다.

동일 release·건수와 정렬·연결 검사를 통과해도 실시간 API가 트랜잭션 수준으로 고정된 스냅샷이라는 보장은 아니다. 변경이 감지되면 새 실행으로 재수집하거나 공식 고정 release 다운로드 방식을 검토한다.

## 검사 코드와 완료 증거

- 구현: `src/egfr_lab/data/chembl.py`, `store.py`, `collection.py`와 CLI.
- 테스트: `tests/test_collection.py`. 서버 실패 후 캐시 재개, release 변경, 중복 ID, 상세 누락, 잘못된 페이지, 원 응답 손상, 테이블 내용 변경, 실행 잠금, 기존 파일 보호, 재시도 정책을 검사한다.
- 실제 소량 실행: `chembl_preview_20261020`의 측정 10건·분자 6개·실험 5개·문헌 3개 보관·검증을 확인했다.
- [전체 실행 결과](../reports/collection_chembl_full_20261020.md): 측정 26,600건·분자 14,776개·assay 2,425개·문헌 1,299개. 원 응답 432개·Parquet 5개를 최종 검증했다.
- [실제 재개 검사](../reports/collection_resume_validation.json): 기존 원 응답 429개의 해시는 모두 유지됐고, 재개 시 새 요청은 상태·건수 확인 3개뿐이었다. 분석 표는 최신 저장 자료형 코드로 재생성했다.

공식 근거: [ChEMBL 페이지네이션·필터·정렬·ID 목록 조회](https://chembl.gitbook.io/chembl-interface-documentation/web-services/chembl-data-web-services), [HTTPX Client](https://www.python-httpx.org/advanced/clients/). 배치 크기·동시 요청 수·재시도 상한과 저장 방식은 프로젝트의 설계 선택이다.
