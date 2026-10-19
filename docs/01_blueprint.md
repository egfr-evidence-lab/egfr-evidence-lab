# 프로젝트 설계

작성·출처 확인 기준일: 2026-10-19. 아래 수치와 정책은 별도 표시가 없으면 **프로젝트 설계안**이며 데이터의 실제 통계나 논문의 결론이 아닙니다.

## 문제와 산출물

연구 질문: **정의된 EGFR 실험 코호트에서 분자 구조로 pIC50를 예측할 수 있는가? 새로운 분자 골격에서 성능이 얼마나 달라지는가?**

후속 질문: 실제 측정과 예측을 구분하면서 관련 실험·문헌·변이 근거를 조회할 수 있는가?

회사 게시 공고의 AI 신약설계·ADC/DAC/TPD 및 첨부 채용 이미지의 전처리·통계 검증 요구를 고려한 설계입니다. 회사가 이 라이브러리들을 사용한다는 주장은 아닙니다. [회사 공고](https://www.saramin.co.kr/zf_user/jobs/view?rec_idx=54544319)

## 전체 흐름

```text
ChEMBL 원자료 + release/요청/해시 매니페스트
  → 실험·분자·변이·문헌 연결
  → 데이터 감사 및 단일 학습 코호트 확정
  → 정제·제외 사유 기록
  → 고정 scaffold 분할
  → Dummy / Morgan+RF / D-MPNN
  → 오차·신뢰구간·적용 범위 보고

문헌 메타데이터 + 재사용 가능한 텍스트
  → 식별자 연결 + 키워드 검색
  → 필요 시 dense 검색 결합
  → RAG: 근거를 인용한 설명

Agent
  → 예측 / 측정값 조회 / 문헌 검색 / 근거 조회 도구 선택
  → 제한된 재검색과 출처 확인
  → 결과: 예측 / 관측 / 문헌 해석 / 정보 부족을 구분
```

Agent와 DL은 동일 모델이 아닙니다. 수치 예측은 학습된 모델이 수행하고 LLM은 도구 선택과 근거 기반 서술을 담당합니다.

## P0 — 먼저 수행할 데이터 감사

1. 표적은 인간 EGFR `CHEMBL203`, 원 엔드포인트는 IC50로 시작합니다.
2. ChEMBL release와 수집 시각, 요청 파라미터, 파일 SHA-256, 원자료 건수, 결합 후 누락 건수를 저장합니다. API 수집 중 버전이 바뀌면 재수집하거나 고정 release 다운로드로 전환합니다.
3. 분자 SMILES와 식별자, activity, assay, document, variant 정보를 연결합니다. 페이지별 요청 성공·누락도 검사합니다.
4. exact/부등호 측정, 단위, 분자 중복, assay 형식, 변이 상태, 문헌별 분포를 집계합니다.
5. **생화학 실험 중 해석 가능한 단일 변이 상태**를 초기 코호트 후보로 검토합니다. 정상형은 첫 후보이며, 확보 가능성을 확인하기 전에는 확정하지 않습니다.
6. 주 코호트의 화합물 수, 독립 scaffold 수, 라벨 범위와 문헌 편중을 확인하고 학습 가능 여부를 결정합니다. 보편적인 최소 건수처럼 임의 숫자를 제시하지 않습니다. 작으면 모델 범위를 축소하고 탐색 분석 중심으로 전환합니다.

**감사 산출물:** `reports/data_audit.md`, `data/interim/assay_review.csv`, `reports/dataset_card.md`.

ChEMBL에서 정상형과 변이형은 같은 표적 ID를 가질 수 있습니다. `variant_id` 및 실험 설명을 함께 확인합니다. null은 DB의 정상형 구분에 사용되지만 실험 해석이 불분명한 자료까지 정상형이라고 확정하지 않습니다. 자동으로 판별하지 못한 것은 별도 보류합니다. [공식 변이 설명](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/target-questions)

## 정제 정책

| 항목 | 제안한 정책 |
|---|---|
| 목표값 | IC50만 선택, 양수이며 유한한 정확값을 mol/L로 해석해 pIC50 변환 |
| 부등호 | `>`, `<`, `>=` 등은 정확값 학습에서 제외하고 원자료·제외표에 보존 |
| 단위 | 지원 농도 단위만 변환. 질량농도는 분자량 없이 임의 변환하지 않음 |
| 표적 신뢰도 | confidence 9를 초기 필터 후보로 검토하되 실험 동질성의 증거로 취급하지 않음 |
| 실험 형식 | 단백질 기반과 세포 기반, 증식 억제 실험을 한 라벨로 합치지 않음 |
| 변이 | 정상형·명시적 변이·불명확·미검토 구분; 복합 변이는 구성 전체 보존 |
| 오류 표시 | validity/duplicate 플래그를 검토하고 제외·유지 이유를 기록 |
| 화학 정규화 | RDKit 파싱, 염·혼합물·모체 선택, 입체화학 정책을 문서화; 원 SMILES 보존 |
| 반복 측정 | 같은 분자·같은 실험·같은 변이 맥락에서만 요약 가능. 다른 논문의 값을 무조건 평균내지 않음 |
| 중복·누수 | 정규화된 분자 식별자를 그룹으로 유지. 입체이성질체를 의도 없이 합치지 않음 |

ChEMBL은 단위·품질·잠재적 중복 정보를 제공하지만 모든 실험이 비교 가능하도록 보장하지는 않습니다. [활성·실험 필드 설명](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/chembl-data-questions)

## 계획한 분석 테이블

| 필드 | 목적 |
|---|---|
| `activity_id`, `molecule_chembl_id`, `target_chembl_id` | 원 측정과 분자를 추적 |
| `canonical_smiles`, `normalized_smiles`, `compound_group_id` | 원 구조·처리 구조·분할 그룹 |
| `standard_type`, `standard_relation`, `standard_value`, `standard_units`, `pic50` | 라벨 변환의 원값과 결과 |
| `assay_chembl_id`, `assay_type`, `bao_format`, `assay_description` | 실험 맥락 |
| `variant_id`, `variant_mutation`, `variant_review_status` | 변이·정상형 검토 근거 |
| `document_chembl_id`, `pubmed_id`, `doi`, `document_year` | 문헌 연결, 존재 여부도 검사 |
| `scaffold_group`, `split`, `exclusion_reason` | 분할과 제외 추적 |

이것은 **로컬 분석 테이블의 제안 스키마**입니다. API 응답의 실제 필드 경로·결합 관계와 동일하다고 가정하지 않습니다. [공식 스키마 예제](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/schema-questions-and-sql-examples)

## P1/P2 — 모델과 통계 검증

1. DummyRegressor(학습 라벨 평균) → Morgan fingerprint+RandomForestRegressor → Chemprop D-MPNN 순서로 구현합니다.
2. 70/15/15는 목표 비율입니다. scaffold 그룹 크기 때문에 실제 비율이 달라지면 기록하고 그룹을 쪼개 비율을 강제하지 않습니다. 고리 없는 분자의 빈 scaffold 처리 정책도 고정합니다.
3. 주 결과는 scaffold 분할, 비교 결과는 분자 중복을 막은 random 분할로 보고합니다. random 성능만으로 새로운 화학 구조의 성능을 주장하지 않습니다.
4. 전처리 학습·특징 선택·스케일링·튜닝·early stopping은 학습/검증 데이터에서만 수행합니다. 테스트는 모델·실험 설계를 고정한 뒤 사용합니다.
5. **주 지표 MAE**, 보조 RMSE·Spearman. 동일 평가 화합물·동일 분할에서 비교하고 실패한 구조와 문헌/assay 편중도 분석합니다.
6. 모델 A/B의 MAE 차이는 동일 테스트 표본의 paired 비교로 계산합니다. 유사 구조 내 의존성을 고려해 **scaffold cluster를 같은 인덱스로 재표집**하는 bootstrap을 구현할 계획입니다. SciPy의 기본 `paired=True`만 호출한다고 cluster bootstrap이 되는 것은 아닙니다.
7. 반복 학습 seed의 변동과 테스트 표본 재표집 CI를 별도 보고합니다. bootstrap CI는 주어진 데이터·모델·재표집 가정에 조건부이며 미래 모든 실험에 대한 보장이 아닙니다. 독립 cluster가 적으면 해석을 제한합니다.
8. assay/논문 holdout은 민감도 분석 후보입니다. 같은 분자가 양쪽에 걸치는지 추가 검사하고, 중복 제거로 작아진 경우 그 사실을 보고합니다. 이를 독립 외부 검증이라고 부르지 않습니다.

Scaffold 평가와 학습 분할 선택의 근거: [Yang et al., 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6727618/), [scikit-learn 교차검증](https://scikit-learn.org/stable/modules/cross_validation.html). Paired 재표집 개념: [SciPy bootstrap](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html). 위 cluster 설계는 이 프로젝트의 제안입니다.

예측 신뢰도 대신 초기에는 **학습 분자와의 최대 유사도·scaffold 유무**를 적용 범위 참고치로 표시합니다. ensemble 분산은 경험적 변동이지 보정된 확률이 아닙니다. 예측 구간은 별도 검증/보정 후에만 표시합니다.

## P3/P4 — RAG와 Agent

문헌 수집은 Europe PMC API를 사용합니다. 식별자 직접 조회·정확한 화합물명·EGFR 변이 문자열 검색을 먼저 구현합니다. 문헌 본문은 허용된 OA 콘텐츠만 처리하고 라이선스와 사용 텍스트 범위를 기록합니다. 문헌/문단/출처의 식별자를 보존합니다. [Europe PMC 개발자 문서](https://dev.europepmc.org/developers), [PMC 자동 수집 정책](https://pmc.ncbi.nlm.nih.gov/tools/developers)

검색 baseline은 키워드/BM25입니다. dense 검색은 누락되는 동의어 질의가 실제로 있는지 평가한 뒤 추가합니다. 범용 embedding이 생의학 용어와 화합물명을 잘 찾는다고 가정하지 않습니다.

Agent는 단일 Agent로 시작합니다. 허용 도구는 `predict_activity`, `lookup_measurements`, `search_literature`, `fetch_evidence`입니다. 명확한 요청에서 필요한 도구를 선택하고 최대 6회 호출·검색 재시도 2회로 제한하는 것이 초기 설계입니다. 이는 보편적 최적값이 아니라 조정 가능한 운영 상한입니다. 고정 순서 실행은 workflow로, 결과에 따른 도구 선택과 재검색까지 구현했을 때 Agent로 설명합니다. [LangGraph 공식 설명](https://docs.langchain.com/oss/python/langgraph/workflows-agents)

별도 수작업 평가 세트를 개발용 20개, 최종 평가용 30개로 구성할 계획입니다. 변이 일치/불일치, 논문 없음, 측정값 없음, 단위 오류, 예측 도구 실패 사례를 포함합니다. 문헌이 없는 질문의 Recall은 별도로 정의합니다.

| 평가 대상 | 검증 |
|---|---|
| 검색 | 정답 문헌 Recall@5, MRR; 문서 단위로 평가 |
| 추출 | 화합물·변이·측정값·단위·실험 조건의 정확도 |
| 인용 | 주장별 문단의 실제 뒷받침 여부를 수작업 확인 |
| Agent | 필수 도구 선택, 잘못된 호출, 종료·보류, 반복 상한 |
| 시스템 | 응답시간, 토큰/호출량, 실패율, 실행 환경 |

평가 질문/정답을 prompt나 few-shot에 넣지 않습니다. 공개 학습 자료에 노출된 논문 여부는 완전히 통제할 수 없으므로 일반화 주장을 제한합니다. LLM 기반 자동 채점은 보조이며 핵심 수치·인용은 사람이 확인합니다.

## 단계별 완료 증거

| 단계 | 완료 조건 |
|---|---|
| P0 | 원자료·release·해시·정제 건수·실험/변이 검토·코호트 선택 문서 |
| P1 | 기준 모델 대비 RF, 고정 분할, 누수 점검, 오차·CI 보고 |
| P2 | 같은 평가 조건 D-MPNN 비교, 방법 적용/재현 구분 문서 |
| P3 | 출처를 추적하는 검색, held-out 질의 평가 |
| P4 | 도구 호출 trace, 근거 보류·실패 처리, Agent 평가 |
| P5 | 클라우드 환경에서 추론·로그·모델 버전·재시작 확인 |

현재 위 단계는 모두 계획 상태입니다. 데이터 감사 결과에 따라 다음 단계의 범위를 수정합니다.
