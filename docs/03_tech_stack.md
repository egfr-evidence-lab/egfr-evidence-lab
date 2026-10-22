# 기술 스택과 검증 계획

이 문서는 **우리 프로젝트에 선택한 기술과 후보**를 정리합니다. 2026-10-20 기준 P0 패키지는 Python 3.12·macOS arm64에서 설치·기능·재설치를 검증하고 해시로 고정했습니다. P1 교육 실험은 별도 `.venv-ml`에서 실행하고 버전 스냅샷을 남겼습니다. [P0 검증](../reports/p0_environment_validation.md), [P1 실행·검증 범위](../reports/apsel_review_and_baseline_ko.md). 채용 회사의 실제 사용 스택이나 모든 플랫폼의 호환성을 확인한 것은 아닙니다.


아래 다섯 영역을 이 프로젝트에서 어떻게 구현했는지 정리합니다. 2026-10-22 기준 딥러닝 비교(M2)·공개 벤치마크 축소 재현(M3)·도구 호출 Agent(M5)·컨테이너 추론 API와 클라우드 실행(M6)을 **범위를 제한해** 완료했고, 기업 문헌 사례(M4)는 원문 미확보로 보류입니다. 각 항목의 범위 한계는 [마일스톤 기록](../configs/portfolio_scope.json)과 해당 보고서에 적었습니다.

| 추가 기술 스택 | 넣을 수 있는 기능 | 근거 | 완료 증거 |
|---|---|---|---|
| 딥러닝 | Chemprop의 PyTorch 기반 D-MPNN으로 분자 그래프 → pIC50 | [Chemprop v2 원 논문](https://pubs.acs.org/doi/10.1021/acs.jcim.5c02332), [공식 문서](https://chemprop.readthedocs.io/en/latest/index.html) | 동일 분할 RF/D-MPNN 비교·seed 변동·오차 분석 |
| 의약바이오 데이터 경험 | ChEMBL 실험·변이·단위·문헌 정제 | [ChEMBL 실험 설명](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/chembl-data-questions) | 원자료 매니페스트·정제 제외표·데이터 카드 |
| 논문 구현·재현 | D-MPNN 방법 이해·적용 + 분리된 단일 공개 벤치마크 재현 | [Yang 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6727618/), [Heid 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC10777403/), [저자 benchmark](https://github.com/chemprop/chemprop_benchmark) | 코드·버전·원 데이터·분할·표/지표의 일치와 차이 기록 |
| 클라우드 | 컨테이너 추론 서비스, 모델·원자료 버전 저장, 로그 | [AWS Fargate](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html), [S3 Versioning](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html) | 배포 버전·실제 호출·재시작·지연시간·로그 |
| Agentic AI | 수치 예측·측정 조회·문헌 검색 도구를 선택하는 제한된 Agent | [LangGraph workflows/agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents) | 도구 호출 trace·인용 검증·held-out 질문 평가 |

**의약바이오 데이터 경험은 라이브러리 이름이 아닌 도메인 역량**이고, 논문 재현 역시 도구가 아닌 실험 수행 역량입니다.

## 단계별 스택

| 영역 | 선택 | 선택 이유 / 근거 | 도입 시점 |
|---|---|---|---|
| 환경 | 기존 Python 3.12.14 독립 venv | 현재 Mac의 P0 설치·기능·재설치 검증 완료. Chemprop 호환성은 P2에서 별도 검증. [설치 문서](https://chemprop.readthedocs.io/en/latest/installation.html) | P0 환경 확인 완료 |
| 수집·테이블 | httpx, pandas, Parquet/pyarrow | API 원 응답과 분석 테이블을 구분해 저장하는 프로젝트 설계. [ChEMBL 접근 방법](https://www.ebi.ac.uk/training/online/courses/chembl-quick-tour/accessing-chembl-data/) | P0 |
| 분자 처리 | RDKit | 구조 파싱·Morgan fingerprint·분자 유사도. [공식 입문 문서](https://www.rdkit.org/docs/GettingStartedInPython.html) | P0/P1 |
| 기준 ML | scikit-learn의 DummyRegressor·RandomForestRegressor | 평균 예측과 구조 기반 비선형 예측을 구분해 비교하는 설계. [평가/교차검증](https://scikit-learn.org/stable/modules/cross_validation.html) | P1 |
| 통계 | NumPy, SciPy + 그룹 재표집 코드 | paired 차이·CI 계산. [SciPy bootstrap](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html) | P1 |
| DL | **Chemprop v1.6.1 / PyTorch 2.5.1** (계획은 v2였음) | 분자 그래프 표현을 학습. 수작업 fingerprint와 비교. [v2 원 논문](https://pubs.acs.org/doi/10.1021/acs.jcim.5c02332) | P2 완료 |
| 실험 기록 | JSON 매니페스트 → MLflow | 파라미터·코드 버전·지표·출력 파일 관리. [MLflow Tracking](https://mlflow.org/docs/latest/ml/tracking/) | P1, MLflow는 필요 시 |
| 문헌 | Europe PMC API, SQLite/JSON 메타데이터 | 문헌 식별자와 허용된 텍스트를 함께 관리. [공식 개발자 문서](https://dev.europepmc.org/developers) | P3 |
| 검색 | 정확 ID + BM25 우선, Sentence Transformers/FAISS는 추가 후보 | 짧은 변이명·화합물 식별자의 검색 누락을 관찰한 뒤 hybrid 검색 여부 결정 | P3 |
| LLM·검증 | provider 교체 가능한 호출 계층, Pydantic | 모델·prompt·응답·실행 ID 고정. 구조화된 출력도 내용의 진실성을 보장하지 않으므로 별도 확인 | P3/P4 |
| Agent | LangGraph의 상태·조건부 라우팅·도구 호출 | 고정 workflow와 결과에 따른 도구 선택을 구분. [공식 문서](https://docs.langchain.com/oss/python/langgraph/workflows-agents) | P4 |
| API/UI | FastAPI, 필요 시 Streamlit | 예측 API와 연구 결과 화면을 얇게 연결하는 설계 | P4/P5 |
| 클라우드 | Docker, AWS ECR/ECS Fargate, S3, CloudWatch | 학습과 추론을 분리한 CPU 추론 배포를 우선. [배포 계획](../deployment/README.md) | P5 |

Sentence Transformers/FAISS/FastAPI/Streamlit은 설계 후보이며 현재 설치·실행 검증하지 않았습니다. 기술 이름을 늘리기 위해 모든 후보를 동시에 도입하지 않습니다. 상용 LLM provider는 아직 선정하지 않았고 SDK/API 비용도 미확정입니다.

## 딥러닝에서 배울 내용

원자를 node, 결합을 edge로 표현 → 방향성 결합 메시지 전달 → 분자 표현 집계 → 회귀 출력을 학습합니다. 학습률·epoch·배치·dropout·조기종료·라벨 스케일링을 기록합니다. D-MPNN이 RF보다 좋다는 결론은 실험 전에는 내리지 않습니다. [Heid et al., 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC10777403/)

추가 후보인 사전학습 분자 모델, 앙상블, 보정된 예측 구간은 RF/D-MPNN 검증 후의 별도 실험입니다. 첫 버전에는 대규모 사전학습·분자 생성·도킹·3D 모델을 포함하지 않습니다.

## 설치·버전 정책

- `pyproject.toml`은 단계별 의존성 선언이며 lock 파일이 아닙니다. P0의 검증 버전과 해시는 `requirements/p0-py312-macos-arm64.txt`로 별도 고정했습니다.
- 기존 Python 3.12.14 환경에서 P0 5개 직접 패키지와 간접 의존성 9개를 설치했습니다. import·통신·CSV/Parquet·분자 처리·별도 빈 환경 재설치 검사를 통과했습니다. [재실행 방법](../requirements/README.md)을 참고하세요.
- P1은 `.venv-ml`에 SciPy·scikit-learn·matplotlib 등을 설치해 모델 실행·재로딩·전체 테스트 43개와 `pip check`를 통과했습니다. `requirements/ml-py312-macos-arm64.freeze.txt`는 정확 버전 스냅샷이며 해시 lock·새 환경 재설치 검증은 아닙니다. P2 이후 의존성은 별도 검증합니다.
- **2026-10-22 정정: 계획은 v2였고 실제로는 v1.6.1만 썼습니다.** M3(SAMPL 재현)은 저자 환경이 v1.6.1이라 그 버전이 필요했고, M2(pilot22 D-MPNN)도 같은 `.venv-repro` 환경에서 v1.6.1로 돌렸습니다. 두 실험의 환경을 통일해 버전 차이가 결과에 섞이지 않게 한 선택이지만, 처음 계획과 다릅니다. v2로 EGFR 실험을 다시 돌리는 것은 실행하지 않았습니다. v1 모델을 v2로 그대로 바꾸어 동일 재현이라고 부르지 않습니다. 공식 README는 v2 재작성과 기본 설정 차이를 안내합니다. [공식 저장소](https://github.com/chemprop/chemprop)
- `pyproject.toml`의 `deep` extra는 `chemprop>=2,<3`으로 남겨 두었습니다. 실제 실행 환경은 `.venv-repro`의 v1.6.1이며 그 버전은 [M2 설정](../configs/dmpnn_pilot22.json)과 [M3 보고서](../reports/sampl_repro_20261021_v2/benchmark_repro_report_ko.md)에 기록했습니다.
- GPU는 데이터 크기·학습시간 측정 후 결정합니다. 로컬 CPU 실험은 가능성 확인부터 시작하고, GPU가 필요하면 별도 학습 환경을 고릅니다. Fargate는 이 설계에서 추론 서비스용입니다.
- 현재 실행 뼈대의 표준 라이브러리 검증과 전체 ML/DL 환경의 검증을 구분해 기록합니다.
