# EGFR Evidence Lab

ChEMBL 공개 EGFR 실험 데이터로 화합물 활성을 예측하고, **그 예측의 근거와 한계를 추적 가능하게 기록하는** 연구 포트폴리오 프로젝트입니다.

**[대시보드 보기](https://claude.ai/artifact/TjSsKVEvgDaXWFMGfiQqru)** · [정의와 결과 PDF](output/pdf/egfr_project_definition_and_results_ko.pdf) · [학습 가이드 PDF](output/pdf/egfr_learning_guide_medical_ai_ko.pdf) · [HANDOFF.txt](HANDOFF.txt)

---

## 한눈에

| | |
|---|---|
| 수집 | ChEMBL `CHEMBL203` IC50 측정 **26,600건** · 분자 14,776 · assay 2,425 · 문헌 1,299 |
| 선정 기준 통과 | **5,511건** · assay 558개 |
| 학습에 사용 | **22건** · scaffold 12개 (단일 문헌·단일 assay) |
| 단계 | M1·M2·M3·M5·M6 완료(범위 제한) · **M4 보류**(원문 유료) |
| 테스트 | **81개 통과** |

### 이 프로젝트의 결론을 한 문장으로

> 엔지니어링은 데이터 수집부터 클라우드 추론까지 전부 돌아간다. 그리고 **22건으로는 어떤 모델도 평균 예측을 확실히 넘지 못한다는 것**이 측정 결과다.

성능 자랑이 아니라 **근거와 한계의 기록**입니다. 결과의 절반이 "미확정"이고, 그것이 이 프로젝트의 산출물입니다.

---

## 왜 22건인가 — 원인과 결과

이 프로젝트를 설명하는 가장 중요한 숫자입니다.

### 원인: 실험 조건이 다르면 같은 IC50도 다른 양이다

생화학 IC50은 효소 농도·**ATP 농도**·기질·전처리 시간·반응 시간·온도·pH·검출 방식에 따라 몇 배씩 달라집니다. ATP 경쟁 저해제는 특히 ATP 농도에 민감합니다. 어떤 논문은 1 µM, 어떤 논문은 10 µM을 쓰는데, 같은 화합물이 다른 IC50으로 보고됩니다.

그래서 [선정 정책](configs/cohort_policy.json)에 **13개 필수 필드**를 정의하고, 값이 빠진 것을 같다고 보지 않는다(`missing_values_count_as_equal: false`)고 못박았습니다.

### 결과: 기준은 통과했지만 합칠 수 없었다

| 단계 | 기준 | 남은 측정 | assay |
|---|---|---|---|
| 0 | 수집 전체 | 26,600 | 2,425 |
| 2 | 등식 값만 (부등호 제외) | 19,719 | 2,053 |
| 4 | 변이 미지정 (WT 후보) | 15,377 | 1,460 |
| 5 | 생화학 실험만 | 14,114 | 1,328 |
| 6 | 단일 단백질 형식 | 9,938 | 913 |
| 7 | 표적 신뢰도 9 | 6,503 | 649 |
| 8–9 | 품질 경고·중복 제외 | **5,511** | **558** |
| 10 | 단일 assay 선택 | **22** | **1** |

**558개 assay 중 실험 조건이 같다고 원문으로 확인한 조합이 하나도 없었습니다**(cross-assay pooling 승인 0쌍). 데이터가 없어서가 아니라 **근거가 없어서** 쓰지 않았습니다.

재현: `.venv-serve/bin/python scripts/build_portfolio_data.py --out tmp/portfolio_data`

---

## 확인하려 한 질문과 답

| 단계 | 질문 | 답 |
|---|---|---|
| **M1** | 기준 모델이 평균 예측보다 나은가 | **확정할 수 없다.** scaffold 분할 3 seed 모두 차이의 95% 구간이 0을 포함 |
| **M2** | D-MPNN이 수작업 fingerprint보다 나은가 | **구별되지 않는다.** paired 12개 중 11개가 0 포함. 예측 표준편차 0.011~0.036 대 관측 0.377 — 상수 붕괴 |
| **M3** | 공개 벤치마크를 재현할 수 있는가 | **저자값과 구별되지 않는 결과.** 세 세트 모두 저자 보고값이 우리 95% 구간 안. 단 축소 조건이므로 동일 조건 재현은 아니다 |
| **M4** | 기업 문헌 사례를 원문 검토할 수 있는가 | **할 수 없다.** DOI `10.1002/ardp.70193` 유료. 5개 경로 확인, 우회하지 않음 |
| **M5** | LLM이 근거 없는 수치를 만들지 않는가 | **도구 선택·인용·오류 처리는 통과.** 약점은 종료 판단. 규칙 8/8, gpt-4.1 5/8, gpt-5-mini 4/8 |
| **M6** | 서비스로 만들어 클라우드에서 돌릴 수 있는가 | **돌아간다.** 로컬·클라우드 예측 5/5 일치. 다만 클라우드가 3.5~5.9배 느리고, 적용 범위 밖에서 모델이 상수를 돌려준다 |

### 분할 방식이 결론을 바꾼다

| 분할 | seed | RF−Dummy MAE | 95% 구간 | 판정 |
|---|---|---|---|---|
| **scaffold**(주 지표) | 42 | −0.0146 | −0.0819 ~ +0.0506 | 0 포함 — 미확정 |
| scaffold | 123 | −0.0095 | −0.0766 ~ +0.0639 | 0 포함 — 미확정 |
| scaffold | 2026 | −0.0170 | −0.0906 ~ +0.0513 | 0 포함 — 미확정 |
| random | 42 | −0.0525 | −0.1143 ~ **−0.0047** | **0 제외** |

random 분할 seed 42만 보면 "RF가 유의하게 낫다"고 쓸 수 있습니다. 주 지표를 **실행 전에** scaffold로 정해두지 않았다면 유리한 쪽을 고를 수 있었습니다.

### 적용 범위 밖에서 모델이 상수를 돌려준다

M6에서 구조가 전혀 다른 분자 10개를 넣어본 결과입니다.

| 분자 | 예측 pIC50 | 환산 IC50 | 최대 Tanimoto |
|---|---|---|---|
| 포도당 | 8.048 | 약 9 nM | 0.045 |
| 에탄올 | 8.054 | 약 9 nM | 0.053 |
| 아스피린 | 8.055 | 약 9 nM | 0.133 |
| 니코틴 | 8.143 | 약 7 nM | 0.163 |

예측값 폭 **0.095**, 표준편차 **0.035** — 학습 라벨 표준편차 0.381의 **9%**입니다. 숫자만 돌려주는 API였다면 포도당이 9 nM EGFR 저해제로 보고됐을 것입니다.

**그래서 서비스 응답에서 적용 범위 판정과 고지를 생략할 수 없게 만들었습니다.**

---

## 대시보드 — 두 섹션

**[claude.ai/artifact/TjSsKVEvgDaXWFMGfiQqru](https://claude.ai/artifact/TjSsKVEvgDaXWFMGfiQqru)**

마크업에 숫자를 직접 쓰지 않았습니다. 9개 데이터셋에서만 채우고, 각 데이터셋에 어느 산출물에서 왔는지 적었습니다. 숫자를 클릭하면 출처와 원본 행을 볼 수 있습니다.

### 섹션 1 — 코호트와 지표

- **정제 퍼널**: 26,600 → 22. 막대에 올리면 그 단계의 기준과 제외 이유
- **95% 구간 플롯**: 0선 기준으로 M1·M2의 차이 구간. 0을 포함하면 회색
- scaffold 분할 MAE, 관측 대 예측 산점도, 마일스톤 표, 지연시간 비교

### 섹션 2 — 근거와 적용 범위

- **변이 분포**: L858R → T790M → C797S 내성 계보를 assay 건수와 함께. `UNDEFINED MUTATION` 115건은 경고색
- 부등호·측정 형식·문헌 연대 분포
- **22건 근거 체인**: 분자 → 측정값 → `activity_id` → SMILES. ChEMBL 원본까지 되짚을 수 있다
- **적용 범위 산점도**: 학습 라벨 범위를 띠로 표시하고 무관한 분자 10개의 예측이 한 점에 모이는 것

데이터 추출: [`scripts/build_portfolio_data.py`](scripts/build_portfolio_data.py)

---

## 문서

### 정리 PDF

| 문서 | 내용 |
|---|---|
| **[프로젝트 정의와 결과 — 11쪽](output/pdf/egfr_project_definition_and_results_ko.pdf)** | 무엇을 확인하려 했고 무엇을 정의했으며 무엇이 확인됐는가. 사전 예상과 실제, 주장하지 않는 것 목록 ([원고](docs/16_project_definition_and_results_ko.md)) |
| **[의학 도메인·AI 기술 학습 가이드 — 14쪽](output/pdf/egfr_learning_guide_medical_ai_ko.pdf)** | EGFR·IC50·변이·실험 조건부터 scaffold 분할·부트스트랩·Agent 평가·gVisor까지. 각 지식이 이 프로젝트의 어느 지점에서 필요했는지 함께 적음 ([원고](docs/15_learning_guide_medical_ai_ko.md)) |
| [P0 도메인·IT 기술 노트 — 16쪽](output/pdf/egfr_p0_domain_tech_ko.pdf) | 프로젝트 시작 전 학습 노트 ([원고](docs/07_p0_domain_and_tech_notes.md)) |
| [도메인 학습 가이드 — 14쪽](output/pdf/egfr_domain_study_guide_ko.pdf) | EGFR·분자 구조·IC50·변이·ChEMBL 입문 ([원고](docs/06_domain_study_guide.md)) |

PDF를 다시 만들려면 한글이 포함된 임베딩 가능한 TTF가 필요합니다. 폰트는 저장소에 넣지 않았습니다.

```bash
.venv-serve/bin/python scripts/build_session_notes_pdf.py \
    --font /System/Library/Fonts/Supplemental/AppleGothic.ttf \
    --source docs/16_project_definition_and_results_ko.md \
    --output output/pdf/egfr_project_definition_and_results_ko.pdf
```

### 읽는 순서

1. [프로젝트 설계와 데이터·평가 기준](docs/01_blueprint.md)
2. [바이오·메디컬 학습 가이드](docs/02_bio_medical_primer.md)
3. [기술 스택: 선택 이유·근거·검증](docs/03_tech_stack.md)
4. [논문 재현 범위와 실험 기록](docs/04_reproduction.md)
5. [출처와 인용 목록](docs/05_references.md)

**다른 세션에서 이어갈 때는 [HANDOFF.txt](HANDOFF.txt)를 먼저 읽으세요.** 17개 절에 실행 명령·현재 상태·겪은 장애·다음 작업이 있습니다.

---

## 단계별 보고서

| 단계 | 보고서 |
|---|---|
| 데이터 감사 | [요약](reports/data_audit_summary_ko.md) · [상세](reports/data_audit.md) · [데이터 카드](reports/dataset_card.md) |
| 코호트 확정 | [근거와 판정](reports/cohort_definition_evidence.md) · [적용 범위 검토](reports/cohort_scope_evidence_ko.md) · [보류 목록](configs/source_review_holds.json) |
| **M1** 기준 모델 | [실행 결과와 한계](reports/apsel_review_and_baseline_ko.md) · [독립 검증](reports/baseline_pilot_validation.json) |
| **M2** D-MPNN | `reports/dmpnn_pilot22_20261021_v2/` |
| **M3** 벤치마크 재현 | [축소 재현 보고서](reports/sampl_repro_20261021_v2/benchmark_repro_report_ko.md) |
| **M4** 기업 문헌 | [HBE-843 카드](reports/company_paper_case_hbe843.md) · [접근 차단 증거](data/raw/m4_access_evidence_20261021/) |
| **M5** Agent | [LLM 평가 보고서](reports/agent_eval_20261021_final_openai/agent_llm_report_ko.md) |
| **M6** 서비스 | [컨테이너](reports/serving_m6_20261021/serving_report_ko.md) · [클라우드](reports/serving_m6_cloud_20261022/cloud_report_ko.md) |

전체 상태는 [`configs/portfolio_scope.json`](configs/portfolio_scope.json)에 있습니다.

---

## 실행

### 설정 점검과 단위 변환 (표준 라이브러리만)

```bash
PYTHONPATH=src python -m egfr_lab check-config
PYTHONPATH=src python -m egfr_lab plan
PYTHONPATH=src python -m egfr_lab convert-ic50 --value 10 --unit nM
PYTHONPATH=src python -m unittest discover -s tests -v
```

10 nM → pIC50 = 8입니다. `>10 nM` 같은 부등호 측정은 정확값 회귀의 정답으로 변환하지 않습니다.

### 전체 테스트 (81개)

```bash
PYTHONPATH=src .venv-serve/bin/python -m pytest tests/ -q
```

### 데이터 수집과 감사

```bash
PYTHONPATH=src .venv/bin/python -m egfr_lab collect --run-dir data/raw/chembl_full_<날짜>
PYTHONPATH=src .venv/bin/python -m egfr_lab verify-collection data/raw/chembl_full_<날짜>
PYTHONPATH=src .venv/bin/python -m egfr_lab audit data/raw/chembl_full_<날짜>
```

기존 출력을 보호하므로 재실행에는 새 폴더를 지정합니다.

### 추론 서비스

```bash
# 로컬
PYTHONPATH=src .venv-serve/bin/python -m uvicorn --factory \
    egfr_lab.serving.app:app_from_env --host 127.0.0.1 --port 8011

# 컨테이너
docker build --platform linux/arm64 -f deployment/Dockerfile -t egfr-pilot22-inference:v1 .
docker run -d --name egfr-serve -p 127.0.0.1:8010:8000 egfr-pilot22-inference:v1
curl -s http://127.0.0.1:8010/readyz
```

포트 8000은 쓰지 마십시오 — 이 기계에서 다른 프로세스가 IPv4로 점유하고 있어 요청이 그쪽으로 갑니다([겪은 일](reports/serving_m6_20261021/serving_report_ko.md)).

### 검증

```bash
PYTHONPATH=src .venv-serve/bin/python scripts/verify_serving_m6.py \
    --container-url http://127.0.0.1:8010 --container-name egfr-serve \
    --out reports/serving_m6_<날짜>
```

클라우드 배포는 [`deployment/README.md`](deployment/README.md)에 순서와 비용 통제 규칙이 있습니다.

### 환경

| 환경 | 용도 |
|---|---|
| `.venv` | P0 수집·감사 (해시 lock) |
| `.venv-ml` | M1·M2 모델 실험 |
| `.venv-repro` | Chemprop v1 재현 (분리 필수) |
| `.venv-serve` | M6 서비스·테스트·PDF |

```bash
.venv/bin/python -m pip install --require-hashes --only-binary=:all: \
    -r requirements/p0-py312-macos-arm64.txt
.venv/bin/python scripts/check_p0_environment.py
```

---

## 구조

```text
configs/
  project.json              표적·정제·평가 정책, 단계 상태
  cohort_policy.json        선정 규칙, pooling 13필드 조건
  portfolio_scope.json      마일스톤 상태와 결론
  agent_eval.json           Agent 평가 질문·축 (실행 전 고정)
  serving_m6.json           서비스 계약 (실행 전 고정)
  serving_m6_cloud.json     클라우드 단계 (실행 전 고정)
data/raw/                   원 응답·버전·수집 매니페스트
data/interim/               검토표, 정제 제외 사유
src/egfr_lab/
  config.py labels.py       설정 점검, IC50 → pIC50
  data/                     수집·재개·무결성·감사·조건 비교
  modeling/                 Dummy·RF·분할·누출·오차·cluster bootstrap
  agent/                    도구 4개, 실행기, 정책, trace
  serving/                  FastAPI 추론 API
artifacts/                  모델과 실행 매니페스트
reports/                    감사·평가·모델 카드·재현 보고서
deployment/                 Dockerfile, 배포 순서, 비용 통제
scripts/                    실행·검증·추출 스크립트
```

출력을 실행별로 보관하고 덮어쓰지 않습니다.

---

## 남은 것

### 정의했지만 실행하지 않은 것

| 항목 | 어디에 정의 | 이유 |
|---|---|---|
| **학습곡선** | `cohort_policy.json`의 `learning_curve_..._required: true` | 22건에서 샘플을 줄이면 scaffold 분할이 성립하지 않아 **곡선의 기울기를 추정할 수 없다** |
| **scaffold 커버리지** | 같은 항목 | 가능했으나 우선순위에서 밀렸다. 불가능해서가 아니다 |
| **Chemprop v2** | `docs/03_tech_stack.md` · `deep` extra | M3 재현이 v1.6.1을 요구해 M2도 같은 환경으로 통일했다. 문서를 2026-10-22에 정정 |
| BM25·임베딩 검색 | `literature`·`dense` extra | 식별자 조회로 충분했고 검색 평가 질의 집합을 만들지 않았다 |
| MLflow 상시 운영 | `tracking` extra | JSON 매니페스트로 충분. 처음부터 "필요 시" 항목 |
| model card | 관행 | 내용은 보고서에 있으나 표준 형식으로 모으지 않았다 |

학습곡선은 **기계적으로 실행하는 대신 실행이 무의미한 이유를 기록**했습니다. 예상된 결론("전 구간 구별 불가")을 하나 더 추가하는 것보다 판단 근거를 남기는 쪽을 택했습니다. 코호트가 늘어나면 이 판단은 무효입니다.

기록: [`cohort_policy.json`](configs/cohort_policy.json)의 `learning_curve_decision_20261022` · [`portfolio_scope.json`](configs/portfolio_scope.json)의 `defined_but_not_executed_20261022`

### 외부 조건이 막은 것

| 과제 | 상태 |
|---|---|
| **M4** 기업 문헌 사례 | 보류 — 원문 유료. 외부 조건이 바뀌어야 재개 |
| 코호트 확대 (furan45·patent64) | 보류 — 방법론 원문 미확보, 구조 검증 미완 |
| 보류 목록 5건 | `CHEMBL2439336` · `CHEMBL5638807/14/15` · `CHEMBL5736995` |
| 과금 금액 확정 | 2026-10-23 이후 비용 테이블 재확인 |
| M5 다음 반복 | 반올림 허용 여부, 종료 개선, 질문 집합을 다른 출처에서 작성 |

### 다음 마일스톤 후보 — 부등호 5,482건

**근본 제약**: 22건·12 scaffold로는 어떤 모델도 평균 예측을 확실히 넘지 못합니다. 회귀로 표본을 늘리려면 실험 조건 동일성을 원문으로 확인해야 하고, M4·furan45·patent64가 모두 같은 벽(유료 논문·특허 원문)에 막혀 있습니다.

우회 경로를 설계해 뒀습니다. `>10000 nM`(10 µM까지 50% 억제 없음)을 **비활성 라벨**로 쓰는 분류 과제입니다. ATP 농도가 1 µM이든 10 µM이든 10 µM에서 안 듣는 화합물은 강한 저해제가 아니므로, **회귀보다 조건 민감도가 낮습니다.** 원문 검증 없이 수천 건 규모를 쓸 수 있습니다.

단 이것도 가정이고, "조건 민감도가 낮다"를 먼저 검증해야 합니다 — 같은 화합물이 여러 assay에서 활성/비활성으로 갈리는 비율을 재면 됩니다. 그 데이터는 이미 있습니다.

---

## 라이선스와 출처

ChEMBL 원 데이터는 CC BY-SA 3.0입니다. 데이터를 공개할 때 출처·release·가공 내용·라이선스를 함께 기록합니다. 논문 원문은 별도 이용 조건을 확인합니다. [ChEMBL 공식 라이선스](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/general-questions)

유료 콘텐츠를 우회하지 않습니다. 접근할 수 없으면 접근할 수 없다고 기록합니다.
