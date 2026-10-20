# EGFR Evidence Lab

ChEMBL EGFR 공개 실험 데이터로 화합물 활성을 예측하고, 실험·변이·문헌 근거를 추적하는 연구 포트폴리오 프로젝트입니다.

현재 **P0는 주 학습 코호트 검토 중, P1은 교육용 기준 모델 실행으로 진행 중**입니다. ChEMBL 37에서 EGFR 표적에 연결된 IC50 측정 26,600건·분자 14,776개·실험 2,425개·문헌 1,299개를 보관했습니다. 보수적 자동 후보 264건은 변이별 합계입니다. 추가 공개 논문의 209건은 WT·종 유래·전체 부속 표가 미확정이라 모두 보류했습니다. 기존에 원문 수치를 대조한 단일 assay 22건으로 Dummy·Random Forest 교육 실험을 완료했으며, 일반 EGFR 성능 평가용 데이터 확정과 논문 모델 재현·RAG/Agent·클라우드는 남아 있습니다.

- **[209건 검토·실제 모델 결과와 한계](reports/apsel_review_and_baseline_ko.md)**: 22건 scaffold 3-fold, seed 3개, RF 우위 미확정. [독립 검증](reports/baseline_pilot_validation.json): 저장 모델 36개 재로딩·예측 264행·누출 검사 통과, 전체 테스트 43개 통과.
- **[직접 따라 하는 한국어 실습](docs/11_baseline_practice_ko.md)**: 단위·원문 표 읽기·Dummy 평균·오차·scaffold 검사·모델 재실행·자가 점검.
- **[주 학습 데이터 확보 절차](docs/12_main_cohort_acquisition_ko.md) / [첫 실행 결과](reports/main_cohort_acquisition_ko.md)**: 2,425assay 재집계·242개 검토 대기표·787관측 원문 대조. 저자 CSV의 IC50 45건과 억제율4건을 분리했으며, 45건의 상세 방법·human 유래 확인은 남아 있습니다. 동일173행 자료의 두 assay ID와 구간 중간값180건을 확인했습니다. 새 학습 승인0건, 전체 테스트47개 통과.
- **[후속 원문 검토·실제 지표·적용 범위](reports/cohort_scope_evidence_ko.md)**: 45건의 예정 분할·구조 거리와 선별 편향, 특허 구조·원 MS 연결 경보를 실제 계산했습니다. 골격 중복0이어도 최근접 유사도는 최대0.986입니다. 원문을 대신할 수 없는 DB 파생 자료를 구분했고, 주 코호트 승인은 계속 보류했습니다. 전체 테스트52개 통과.

- [ChEMBL API 확인 결과와 쉬운 해설](reports/chembl_api_verification.md): ChEMBL 37·인간 EGFR 표적·소량 응답·단위·변이·문헌 연결 검증. API 집계 26,600건은 정제 전 측정 기록 수이며 학습 분자 수가 아닙니다.
- [P0 실행 환경 검증](reports/p0_environment_validation.md): Python 3.12·macOS arm64의 P0 패키지 14개 설치·해시 고정, 기본 검사 11항목과 실제 HTTPS 포함 12항목, 새 가상환경 재설치 확인. [설치·재실행 방법](requirements/README.md).
- [전체 수집기 사용법](docs/08_collection.md): 원 응답 보존, 페이지·상세 ID 검사, 재시작, Parquet 분석 표와 오프라인 검증.
- [실제 전체 수집 결과](reports/collection_chembl_full_20261020.md) / [구현·19개 테스트 기록](reports/collection_implementation.md) / [실제 재개 검증](reports/collection_resume_validation.json). 자료 수집 완료와 학습 적격성 판단을 구분합니다.
- [전체 감사 쉬운 요약](reports/data_audit_summary_ko.md) / [상세 데이터 감사](reports/data_audit.md) / [후보 데이터 카드](reports/dataset_card.md) / [감사 실행·원문 검토 순서](docs/09_data_audit.md). 자동 선별 후보를 확정 학습 데이터로 취급하지 않습니다.
- [학습 데이터 확정 방향 요약](reports/cohort_decision_summary_ko.md) / [문헌 근거·실험 조건·실제 판정](reports/cohort_definition_evidence.md): WT 6개 실험 검토, 공개 원문 1개 실험의 22건 수치·화합물 ID 대조 완료. 15개 실험 쌍은 공통 구조가 최대 1개라 병합 승인 0쌍. [선정 정책](configs/cohort_policy.json)을 고정했고 단일 실험 파일럿만 보존했습니다. 최종 학습 코호트는 미확정입니다.
- [기업 우대사항·EGFR 기준·도메인 이해 점검](reports/portfolio_fit_and_domain_review_ko.md): AI 연구원 실제 공고와 구현 상태, 실험·화합물·모델 기준의 차이, 추가 산출물 우선순위와 자가 점검 9문항. [회사 관련 HBE-843 논문 카드](reports/company_paper_case_hbe843.md)는 초록 확인 범위이며 본문·실험 재현과 구별합니다.

**새 터미널·다른 세션에서 이어갈 때는 [HANDOFF.txt](HANDOFF.txt)를 먼저 읽으세요.** 실행 명령, 현재 구현 상태, 다음 원문 검토 작업과 새 세션용 시작 요청을 정리했습니다.

2026-10-20 추가 범위 반영: [실행 순서·완료 조건](docs/10_execution_plan.md)에 따라 데이터 확정·기준 ML → D-MPNN → 공개 벤치마크 재현 → Agent → 클라우드를 진행합니다. 기업 관련 EGFR 내성·분해제 문헌 사례는 병행합니다. 현재 M1은 교육 실험까지 진행했으며, 주 코호트 확정이 남아 있습니다.

[첫 확대 검토 결과](reports/wt_expansion_review_ko.md): WT 12개 assay 접근·검토, 유래 문제를 해소한 검토 후보 27건, 수치 11건 대조. 별도 981건 assay에서 Cot·EGFR 열 혼입 정황을 확인해 [원문 검토 보류 목록](configs/source_review_holds.json)에 등록했습니다. 새로운 학습 승인·모델 성능 결과와 구분합니다.

## 도메인 공부 자료와 VS Code

- **[P0 시작 전 도메인·IT 기술 학습 노트 - 16쪽](output/pdf/egfr_p0_domain_tech_ko.pdf)**: 실제 API 사례, IC50·변이·실험 구분, 현재 사용한 IT 스택, 이후 기술 계획, 문제·해설·공식 출처. [원고](docs/07_p0_domain_and_tech_notes.md).
- **[한국어 도메인 학습 PDF - 14쪽](output/pdf/egfr_domain_study_guide_ko.pdf)**: EGFR·분자 구조·IC50·변이·ChEMBL·정제 연습·신약개발 맥락·문헌 읽기·문제 해설·참고문헌.
- [PDF 원고](docs/06_domain_study_guide.md) / [생성 스크립트](scripts/build_domain_guide.py).
- [VS Code 워크스페이스](egfr-evidence-lab.code-workspace)를 열면 `.venv/bin/python` 환경과 테스트·설정 점검 task를 사용할 수 있습니다. Python 확장 설치가 필요할 수 있습니다.

새로 clone한 환경에서는 Python 3.11 또는 3.12로 가상환경을 먼저 만듭니다. 현재 로컬 뼈대는 Python 3.12 가상환경으로 점검했습니다.

```bash
python3.12 -m venv .venv
PYTHONPATH=src .venv/bin/python -m egfr_lab check-config
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

PDF를 다시 만들려면 별도 PDF 의존성과 한글을 포함한 임베딩 가능한 TTF가 필요합니다. 폰트 파일은 저장소에 포함하지 않았습니다.

```bash
.venv/bin/python -m pip install '.[pdf]'
.venv/bin/python scripts/build_domain_guide.py --font /path/to/Korean.ttf
```

## 문서 읽는 순서

1. [프로젝트 설계와 데이터·평가 기준](docs/01_blueprint.md)
2. [바이오·메디컬 학습 가이드](docs/02_bio_medical_primer.md)
3. [기술 스택: 선택 이유·근거·검증](docs/03_tech_stack.md)
4. [논문 재현 범위와 실험 기록](docs/04_reproduction.md)
5. [출처와 인용 목록](docs/05_references.md)

## 실행 가능한 부분

권장 개발 환경은 Python 3.11 또는 3.12입니다. 아래는 표준 라이브러리만 사용하는 설정 점검과 정확한 IC50 단위 변환 명령입니다. 네트워크 요청이나 학습은 실행하지 않습니다. `python`은 프로젝트 가상환경의 인터프리터를 사용하세요.

```bash
PYTHONPATH=src python -m egfr_lab check-config
PYTHONPATH=src python -m egfr_lab plan
PYTHONPATH=src python -m egfr_lab convert-ic50 --value 10 --unit nM
PYTHONPATH=src python -m unittest discover -s tests -v
```

10 nM의 변환 결과는 pIC50=8입니다. `>10 nM` 같은 부등호 측정은 정확값 회귀의 정답으로 변환하지 않습니다.

ChEMBL 수집은 P0 패키지를 설치한 뒤 별도 명령으로 실행합니다. `--max-pages`는 제한 실행으로 기록되며 전체 완료와 구분합니다. 수집기에 대한 자세한 옵션과 실패·재개 동작은 [사용법](docs/08_collection.md)을 참고하세요.

```bash
PYTHONPATH=src .venv/bin/python -m egfr_lab collect --run-dir data/raw/chembl_full_20261020
PYTHONPATH=src .venv/bin/python -m egfr_lab collect --run-dir data/raw/chembl_full_20261020 --resume
PYTHONPATH=src .venv/bin/python -m egfr_lab verify-collection data/raw/chembl_full_20261020
```

전체 감사는 네트워크 없이 실행합니다. 기존 감사·검토표를 보호하므로 재실행에는 새 출력·보고서 폴더를 지정합니다([사용법](docs/09_data_audit.md)).

```bash
PYTHONPATH=src .venv/bin/python -m egfr_lab audit data/raw/chembl_full_20261020
```

의존성은 `pyproject.toml`에 단계별로 나누었습니다. **P0 패키지 14개는 [현재 Mac용 해시 lock](requirements/p0-py312-macos-arm64.txt)으로 고정했습니다.** 교육용 P1은 별도 `.venv-ml`에 scikit-learn·SciPy 등을 설치해 실제 실행했으며 [버전 스냅샷과 복원 방법](requirements/README.md)을 보관했습니다. 다른 플랫폼과 DL extras는 검증 전입니다. 재현용 구버전 Chemprop은 주 프로젝트와 환경을 분리합니다.

```bash
# Python 3.12·macOS arm64에서 P0 실행 의존성 설치
.venv/bin/python -m pip install --require-hashes --only-binary=:all: --index-url https://pypi.org/simple -r requirements/p0-py312-macos-arm64.txt
.venv/bin/python scripts/check_p0_environment.py
```

## 계획된 구조

```text
configs/project.json       # 표적, 정제·평가 정책, 단계 상태
data/raw/                  # 원 응답·버전·수집 매니페스트
data/interim/              # 실험·변이 검토표, 정제 제외 사유
data/processed/            # 학습 표와 고정 분할
src/egfr_lab/
  config.py                # 구현: 설정 점검
  labels.py                # 구현: 정확값 IC50 → pIC50
  data/                    # 구현: 수집·재개·무결성·자동 감사·조건 비교; 최종 코호트 미확정
  features/                # 확장 계획: 분자 정규화·유사도; 파일럿 fingerprint는 modeling에 구현
  modeling/                # 구현: 교육용 Dummy·RF·분할·누출·오차·cluster bootstrap; D-MPNN은 계획
  evaluation/              # 확장 계획: 주 코호트·문헌 평가
  literature/              # 계획: 문헌 메타데이터·검색·인용
  agent/                   # 계획: 제한된 도구 선택·상태 관리
artifacts/                 # 모델과 실행 매니페스트
reports/                   # 데이터 감사·평가·모델 카드·재현 보고서
deployment/                # 배포 계획, 실제 리소스 생성 없음
```

원 데이터·감사·교육 실험 결과를 실행별로 보관합니다. 현재 모델 결과는 22건 파일럿에 한정하며 검색·Agent·배포의 실제 실행 결과는 아직 없습니다.

ChEMBL 원 데이터의 공식 안내는 CC BY-SA 3.0입니다. 데이터를 공개할 때 출처·release·가공 내용·라이선스를 함께 기록합니다. 논문 원문은 별도 이용 조건을 확인합니다. [ChEMBL 공식 라이선스](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/general-questions)
