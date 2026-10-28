# EGFR Evidence Lab

> 공개 EGFR 실험 데이터로 활성을 예측할 때, 그 예측을 어디까지 믿을 수 있는가?

**🔗 대시보드 [claude.ai/artifact](https://claude.ai/artifact/TjSsKVEvgDaXWFMGfiQqru)** · **정리 PDF [정의와 결과](output/pdf/egfr_project_definition_and_results_ko.pdf) · [학습 가이드](output/pdf/egfr_learning_guide_medical_ai_ko.pdf)** · **인수인계 [HANDOFF.txt](HANDOFF.txt)**

**결론: 엔지니어링은 수집부터 클라우드 추론까지 전부 돌아간다. 그리고 22건으로는 어떤 모델도 평균 예측을 확실히 넘지 못한다는 것이 측정 결과다.**
26,600건을 수집했지만 실험 조건이 같다고 원문으로 확인한 것이 22건뿐이었다. 성능 자랑이 아니라 근거와 한계의 기록이며, 결과의 절반이 "미확정"인 것이 의도된 산출물이다.

| | |
|---|---|
| 수집 | ChEMBL `CHEMBL203` IC50 측정 **26,600건** · 분자 14,776 · assay 2,425 · 문헌 1,299 |
| 선정 기준 통과 | **5,511건** · assay 558개 |
| 학습에 사용 | **22건** · scaffold 12개 (단일 문헌·단일 assay) |
| 단계 | M1·M2·M3·M5·M6 완료(범위 제한) · **M4 보류**(원문 유료) |
| 테스트 | **81개 통과** |

---

## 1. 해결하려 한 문제

화합물 활성 예측 모델을 만들려면 라벨이 필요하고, 공개 데이터베이스에는 수만 건이 있다. ChEMBL의 인간 EGFR(`CHEMBL203`)에는 IC50 측정이 26,600건 들어 있다. 그런데 그 숫자를 그대로 쓸 수 있는가가 이 프로젝트의 질문이다.

같은 "IC50"이라도 효소 농도·ATP 농도·기질·전처리 시간·온도·pH·검출 방식에 따라 몇 배씩 달라진다. 세포 실험과 효소 실험은 다른 양이고, 변이형과 정상형은 다른 단백질이며, `>10000 nM`은 측정값이 아니다. 이것들을 섞으면 모델이 "화합물의 저해 능력"이 아니라 "저해 능력 + 실험 조건의 뒤섞임"을 배운다.

그래서 질문을 "성능이 얼마나 나오는가"에서 **그 숫자를 어디까지 믿을 수 있는가**로 바꿨다. 각 단계는 하나의 질문에 대응한다.

| 단계 | 확인하려 한 질문 |
|---|---|
| **M1** | 공개 데이터로 만든 기준 모델이 평균 예측보다 나은가 |
| **M2** | 분자 그래프를 학습하는 D-MPNN이 수작업 fingerprint보다 나은가 |
| **M3** | 공개 논문의 벤치마크를 우리가 돌려도 비슷한 값이 나오는가 |
| **M4** | 기업이 보고한 EGFR 내성·분해제 사례를 원문 수준에서 검토할 수 있는가 |
| **M5** | LLM이 도구를 골라 쓰면서 근거 없는 수치를 만들지 않는가 |
| **M6** | 이 모델을 버전이 고정된 서비스로 만들어 클라우드에서 실제로 돌릴 수 있는가 |

모든 질문에 **"확인할 수 없으면 확인할 수 없다고 적는다"**는 조건을 붙였다.

## 2. 데이터 구성

### 원인: 실험 조건이 다르면 같은 IC50도 다른 양이다

[선정 정책](configs/cohort_policy.json)에 병합 조건으로 **13개 필수 필드**를 정의했다 — species, variant, protein_construct, enzyme_concentration, atp_uM, substrate, substrate_concentration, preincubation_minutes, reaction_minutes, temperature_C, buffer_pH, readout, inhibitor_scope. 그리고 **값이 빠진 것을 같다고 보지 않는다**(`missing_values_count_as_equal: false`)고 못박았다. 모르는 변이를 정상형으로 가정하지도 않는다(`unknown_variant_is_wild_type: false`).

### 결과: 기준은 통과했지만 합칠 수 없었다

| 단계 | 기준 | 남은 측정 | 분자 | assay | 문헌 |
|---|---|---:|---:|---:|---:|
| 0 | 수집 전체 (`CHEMBL203` · IC50) | 26,600 | 14,776 | 2,425 | 1,298 |
| 2 | 등식 값만 (부등호 제외) | 19,719 | 10,912 | 2,053 | 1,054 |
| 4 | 변이 미지정 (WT 후보) | 15,377 | 10,072 | 1,460 | 990 |
| 5 | 생화학 실험만 | 14,114 | 9,401 | 1,328 | 928 |
| 6 | 단일 단백질 형식 | 9,938 | 6,844 | 913 | 697 |
| 7 | 표적 신뢰도 9 | 6,503 | 4,939 | 649 | 513 |
| 8–9 | 품질 경고·중복 제외 | **5,511** | 4,722 | **558** | 461 |
| 10 | 단일 assay 선택 | **22** | 22 | **1** | 1 |

**558개 assay 중 실험 조건이 같다고 원문으로 확인한 조합이 하나도 없었다**(cross-assay pooling 승인 0쌍). 데이터가 없어서가 아니라 **근거가 없어서** 쓰지 않았다.

- **부등호**: `=` 19,719 / `>` 3,309 / `<` 2,067 / `<=` 87 / `>>` 11 / `>=` 8. 부등호 5,482건은 버리지 않고 보존했다
- **변이**: 2,425 assay 중 616개에 변이 표기, 12종. `L858R,T790M` 203개 · `L858R` 116개 · `UNDEFINED MUTATION` **115개**(무엇인지 모르므로 정상형으로도 특정 변이로도 쓸 수 없다) · `T790M` 70개 · `C797S` 계열 소수
- **품질 플래그**: `Outside typical range` 445건 · `Potential transcription error` 65건 · 중복 의심 2,744건
- **라벨 범위**: 학습 22건의 pIC50은 6.85~8.49(폭 1.65). 선별 단계에서 활성이 좋은 것만 IC50이 측정되는 선택 편향이 있다
- 퍼널은 **사후 재구성**이다. 실제 코호트 확정은 여러 단계의 수동 원문 검토를 거쳤고 이 필터 순서와 같지 않다
- 재현: `.venv-serve/bin/python scripts/build_portfolio_data.py --out tmp/portfolio_data`

## 3. 모델과 실험 설계

| ID | 모델 | 비고 |
|---|---|---|
| Dummy | 평균 예측 (`DummyRegressor`) | 바닥 기준. 이것을 못 넘으면 아무것도 배우지 못한 것 |
| Morgan-RF | Morgan fingerprint(r=2, 2048bit, 입체 포함) + RandomForest 300 trees | 저비용 기준선 |
| D-MPNN | Chemprop **v1.6.1** 분자 그래프 학습 | 계획은 v2였으나 M3 재현이 v1.6.1을 요구해 환경을 통일했다([정정](docs/03_tech_stack.md)) |

- **분할**: 주 지표는 **scaffold**(Murcko 골격 단위), 보조는 random. seed 42 · 123 · 2026
- **지표**: 주 MAE, 보조 RMSE · Spearman
- **통계**: **scaffold 단위** 부트스트랩 2,000회로 paired 차이의 95% 구간. 분자 단위가 아닌 이유는 같은 골격의 분자들이 독립이 아니기 때문이다
- **테스트셋 튜닝 금지**(`test_used_for_tuning: false`)

**실행 전에 설정을 동결했다.** 각 단계의 설정을 JSON으로 고정하고 SHA-256을 결과에 박았다 — `configs/{cohort_policy,baseline_pilot,dmpnn_pilot22,benchmark_repro_v2,agent_eval,serving_m6,serving_m6_cloud}.json`. 각 파일에 `forbidden` 목록을 두어 금지한 서술을 미리 적었다. 예: "최종 질문의 점수를 본 뒤 정책을 고치고 그것을 최초 결과처럼 쓰는 것", "컨테이너 검증만 하고 클라우드 배포 완료라고 쓰는 것", "과금 $0을 비용을 측정했다로 쓰는 것".

**사전 예상을 먼저 적었다.** M6에서 지연시간·콜드 스타트·이미지 크기 예상을 측정 전에 기록했고, **7개 중 4개가 틀렸다. 고치지 않고 남겼다**(`§4`).

**검증 장치**: 지표를 독립 스크립트로 재계산 · 기존 출력 폴더 덮어쓰기 거부 · 모델·코호트·설정 해시 3개를 서비스 응답에서 검증 · 테스트 81개(`PYTHONPATH=src .venv-serve/bin/python -m pytest tests/ -q`).

## 4. 최종 성능 지표

### 질문별 답

| 단계 | 답 |
|---|---|
| **M1** | **확정할 수 없다.** scaffold 분할 3 seed 모두 차이의 95% 구간이 0을 포함 |
| **M2** | **구별되지 않는다.** paired 12개 중 11개가 0 포함. 예측 표준편차 0.011~0.036 대 관측 0.377 — 상수 붕괴 |
| **M3** | **저자값과 구별되지 않는 결과.** 세 세트 모두 저자 보고값이 우리 95% 구간 안. 단 축소 조건이므로 동일 조건 재현은 아니다 |
| **M4** | **할 수 없다.** DOI `10.1002/ardp.70193` 유료. 5개 경로로 확인했고 우회하지 않았다 |
| **M5** | **도구 선택·인용·오류 처리는 통과.** 약점은 종료 판단. 규칙 8/8, gpt-4.1 5/8, gpt-5-mini 4/8 |
| **M6** | **돌아간다.** 로컬·클라우드 예측 5/5 일치. 다만 클라우드가 3.5~5.9배 느리고, 적용 범위 밖에서 모델이 상수를 돌려준다 |

### M1 — 분할 방식이 결론을 바꾼다

| 분할 | seed | RF−Dummy MAE | 95% 구간 | 판정 |
|---|---:|---:|---|---|
| **scaffold**(주 지표) | 42 | −0.0146 | −0.0819 ~ +0.0506 | 0 포함 — 미확정 |
| scaffold | 123 | −0.0095 | −0.0766 ~ +0.0639 | 0 포함 — 미확정 |
| scaffold | 2026 | −0.0170 | −0.0906 ~ +0.0513 | 0 포함 — 미확정 |
| random | 42 | −0.0525 | −0.1143 ~ **−0.0047** | **0 제외** |

random 분할 seed 42만 보면 "RF가 유의하게 낫다"고 쓸 수 있다. 주 지표를 **실행 전에** scaffold로 정해두지 않았다면 유리한 쪽을 고를 수 있었다.

### M6 — 적용 범위 밖에서 모델이 상수를 돌려준다

구조가 전혀 다른 분자 10개를 넣어본 결과다.

| 분자 | 예측 pIC50 | 환산 IC50 | 학습 분자와 최대 Tanimoto |
|---|---:|---:|---:|
| 포도당 | 8.048 | 약 9 nM | 0.045 |
| 에탄올 | 8.054 | 약 9 nM | 0.053 |
| 아스피린 | 8.055 | 약 9 nM | 0.133 |
| 카페인 | 8.057 | 약 9 nM | 0.110 |
| 니코틴 | 8.143 | 약 7 nM | 0.163 |

예측값 폭 **0.095**, 표준편차 **0.035** — 학습 라벨 표준편차 0.381의 **9%**다. 숫자만 돌려주는 API였다면 포도당이 9 nM EGFR 저해제로 보고됐을 것이다. **그래서 서비스 응답에서 적용 범위 판정과 고지를 생략할 수 없게 만들었다.** M2의 D-MPNN 상수 붕괴와 같은 뿌리로 의심된다.

### M6 — 클라우드 실행

Google Cloud Run `asia-northeast3`, 요청 241건, digest로 배포, 측정 후 자원 삭제.

| 항목 | 로컬 컨테이너 | Cloud Run | 배수 |
|---|---:|---:|---:|
| 모델 로딩 | 0.844초 | 4.998초 | 5.9배 |
| 서버 처리 p50 | 10.040 ms | 35.042 ms | 3.5배 |

런타임이 `Linux-4.19.0-gvisor-x86_64`(gVisor 샌드박스)였다. **원인을 그것 하나로 단정하지 않는다** — CPU·플랫폼·샌드박스가 섞여 있고 분리 측정하지 않았다. 클라이언트 왕복 p50 50.019 ms 중 약 15 ms가 네트워크이므로 **왕복 시간을 서버 성능으로 읽으면 틀린다**.

AWS로 먼저 계획했고 비용 추정까지 1차 출처(공개 가격 API)로 끝냈으나 계정 수준 제한으로 막혔다. **AWS에 자원을 하나도 만들지 않았다.**

### 사전 예상 대 실제 (M6)

| 항목 | 예상 | 실제 | 판정 |
|---|---|---|---|
| 서버 처리 p50 | 10~40 ms | 35.042 ms | 범위 안 |
| 왕복 p50 | 30~150 ms | 50.019 ms | 범위 안 |
| 컨테이너 모델 로딩 | 1~5초 | **0.844초** | **틀림** |
| 콜드 스타트 첫 요청 | 2~15초 | **0.13초** | **틀림** — 예상 모델 자체가 틀렸다 |
| 클라우드 모델 로딩 | 0.5~3초 | **4.998초** | **틀림** — gVisor 비용을 과소평가 |
| 이미지 push | 3~20분 | **약 1분** | **틀림** — 805MB가 아니라 압축 173.6MB |

## 5. 한계점

- **학습 표본 22건** — scaffold 12개, 단일 문헌·단일 assay. 어떤 모델도 평균 예측을 확실히 넘지 못한 1차 원인이다
- **D-MPNN을 방법으로 평가하지 못함** — 22건 규모에서 상수로 붕괴했으므로 "D-MPNN이 나쁘다"가 아니라 "이 규모에서는 평가할 수 없다"가 결론이다
- **벤치마크 재현은 축소 조건** — 에폭·앙상블 규모를 줄였고 저자 환경(Linux·NVIDIA·Python 3.7)과 다르다. "재현했다"가 아니라 "구별되지 않는 결과를 얻었다"로 쓴다
- **Agent 평가의 질문을 내가 만들었다** — 14개 질문을 규칙 정책 설계자와 같은 사람이 작성했고 표본이 8문항이다. 규칙 정책이 이긴 것을 일반화하지 않는다
- **클라우드 성능 차이의 원인 미분리** — gVisor·CPU·플랫폼이 섞여 있다. 지연시간은 순차 200회·배치 1·워커 1의 측정이며 처리량이 아니다
- **과금 금액 미확정** — 측정과 같은 날 $0으로 관측했으나 반영 지연과 구분되지 않는다. 자원은 삭제했으므로 늘어날 경로는 없다
- **정의했지만 실행하지 않은 것 6건** — 아래 [남은 것](#남은-것)에 이유와 함께 적었다

## 6. 이 프로젝트가 보여주려는 것

모델 성능은 입증되지 않았다. 그런데 이 프로젝트가 보여주는 것은 다른 것이다.

1. **공개 데이터의 함정을 실제로 밟고 기록했다** — 부등호 5,482건, 변이 미지정 115건, 품질 경고 510건, 중복 의심 2,744건, 조건 불일치로 pooling 0쌍
2. **결과를 과장하지 않는 장치를 만들고 지켰다** — 설정 사전 동결과 해시, 사전 예상 등록, 주 지표 우선 지정, 금지 목록, 독립 검산
3. **사전 예상이 틀린 것을 그대로 남겼다** — M6에서만 4건
4. **자기 결함을 기록했다** — Agent 개발 중 3건(빈 SMILES에 예측값·프로토콜 오류·평가 기준 오류), M6에서 2건, 측정 대상 오인 1건
5. **막힌 것을 막혔다고 적었다** — M4 유료 원문, 코호트 확대 2건, 과금 금액. 유료 콘텐츠를 우회하지 않았다
6. **예측값에 한계를 붙여야 하는 이유를 실증했다** — 적용 범위 밖 상수 붕괴를 측정해 서비스 설계에 반영했다

면접에서 "왜 22건인가"를 물으면 답이 준비돼 있다. **5,511건이 기준을 통과했지만 조건 동일성을 원문으로 확인하지 못해 쓰지 않았다.**

## 7. 링크와 참고 문헌

| 종류 | 링크 |
|---|---|
| 대시보드 | [claude.ai/artifact](https://claude.ai/artifact/TjSsKVEvgDaXWFMGfiQqru) — 정제 퍼널·지표·근거 추적·적용 범위 |
| 정리 PDF | [정의와 결과 12쪽](output/pdf/egfr_project_definition_and_results_ko.pdf) · [학습 가이드 14쪽](output/pdf/egfr_learning_guide_medical_ai_ko.pdf) |
| 마일스톤 상태 | [`portfolio_scope.json`](configs/portfolio_scope.json) · [`project.json`](configs/project.json) |
| 결과 보고서 | 아래 [보고서와 설계 문서](#보고서와-설계-문서) |
| 인수인계 | [HANDOFF.txt](HANDOFF.txt) — 18절, 실행 명령·겪은 장애·다음 작업 |

이 프로젝트 자체의 논문은 없다. 아래는 설계와 비교 대상의 근거로 쓴 문헌이며, 전체 목록은 [`05_references.md`](docs/05_references.md)에 있다.

- Yang et al., *Analyzing Learned Molecular Representations for Property Prediction (D-MPNN)*, J. Chem. Inf. Model. 2019 — [doi:10.1021/acs.jcim.9b00237](https://doi.org/10.1021/acs.jcim.9b00237)
- Heid et al., *Chemprop: A Machine Learning Package for Chemical Property Prediction*, J. Chem. Inf. Model. 2024 — [PMC10777403](https://pmc.ncbi.nlm.nih.gov/articles/PMC10777403/)
- Graff et al., *Chemprop v2*, J. Chem. Inf. Model. — [doi:10.1021/acs.jcim.5c02332](https://doi.org/10.1021/acs.jcim.5c02332)
- Landrum & Riniker, *Combining IC50 or Ki Values from Different Sources*, J. Chem. Inf. Model. 2024 — [doi:10.1021/acs.jcim.4c00049](https://doi.org/10.1021/acs.jcim.4c00049)
- Béquignon et al., *Papyrus: a large-scale curated dataset*, J. Cheminform. 2023 — [doi:10.1186/s13321-022-00672-x](https://doi.org/10.1186/s13321-022-00672-x)
- ChEMBL 데이터 해석 — [공식 FAQ](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/chembl-data-questions)
- 키나아제 저해제 평가 — [NCBI Bookshelf NBK91991](https://www.ncbi.nlm.nih.gov/sites/books/NBK91991/)

---

## 대시보드

[claude.ai/artifact](https://claude.ai/artifact/TjSsKVEvgDaXWFMGfiQqru) — README와 같은 내용을 두 섹션으로 나눠 담았다. 마크업에 숫자를 직접 쓰지 않고 데이터셋 9개에서만 채웠으며, 각 데이터셋에 어느 산출물에서 왔는지 적었다. 숫자를 누르면 출처와 원본 행이 보인다.

| 섹션 | 내용 |
|---|---|
| 코호트와 지표 | 정제 퍼널(26,600→22, 단계별 기준과 제외 이유) · paired 95% 구간 0선 플롯 · scaffold MAE · 관측 대 예측 · 마일스톤 · 지연시간 |
| 근거와 적용 범위 | 변이 분포(내성 계보, `UNDEFINED MUTATION` 경고) · 부등호·측정 형식·문헌 연대 · 22건 근거 체인 표(분자→측정→`activity_id`→SMILES) · 적용 범위 산점도 |

데이터 추출: [`build_portfolio_data.py`](scripts/build_portfolio_data.py). 기본이 비공개이므로 공유하려면 페이지의 Share 메뉴를 쓴다.

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

학습곡선은 **기계적으로 실행하는 대신 실행이 무의미한 이유를 기록**했다. 예상된 결론("전 구간 구별 불가")을 하나 더 추가하는 것보다 판단 근거를 남기는 쪽을 택했다. 코호트가 늘어나면 이 판단은 무효다.

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

**근본 제약**: 22건·12 scaffold로는 어떤 모델도 평균 예측을 확실히 넘지 못한다. 회귀로 표본을 늘리려면 실험 조건 동일성을 원문으로 확인해야 하고, M4·furan45·patent64가 모두 같은 벽(유료 논문·특허 원문)에 막혀 있다.

우회 경로를 설계해 뒀다. `>10000 nM`(10 µM까지 50% 억제 없음)을 **비활성 라벨**로 쓰는 분류 과제다. ATP 농도가 1 µM이든 10 µM이든 10 µM에서 안 듣는 화합물은 강한 저해제가 아니므로, **회귀보다 조건 민감도가 낮다.** 원문 검증 없이 수천 건 규모를 쓸 수 있다.

단 이것도 가정이고, "조건 민감도가 낮다"를 먼저 검증해야 한다 — 같은 화합물이 여러 assay에서 활성/비활성으로 갈리는 비율을 재면 된다. 그 데이터는 이미 있다.

## 설치

| 환경 | 용도 |
|---|---|
| `.venv` | P0 수집·감사 (해시 lock) |
| `.venv-ml` | M1·M2 모델 실험 |
| `.venv-repro` | Chemprop v1.6.1 재현 (분리 필수) |
| `.venv-serve` | M6 서비스·테스트·PDF |

```bash
.venv/bin/python -m pip install --require-hashes --only-binary=:all: \
    -r requirements/p0-py312-macos-arm64.txt
.venv/bin/python scripts/check_p0_environment.py
```

PDF를 다시 만들려면 한글이 포함된 임베딩 가능한 TTF가 필요하다. 폰트는 저장소에 넣지 않았다.

## 실행

```bash
# 설정 점검과 단위 변환 (표준 라이브러리만)
PYTHONPATH=src python -m egfr_lab check-config
PYTHONPATH=src python -m egfr_lab convert-ic50 --value 10 --unit nM   # → pIC50 = 8

# 전체 테스트 81개
PYTHONPATH=src .venv-serve/bin/python -m pytest tests/ -q

# 데이터 수집과 감사 (기존 출력을 보호하므로 새 폴더를 지정한다)
PYTHONPATH=src .venv/bin/python -m egfr_lab collect --run-dir data/raw/chembl_full_<날짜>
PYTHONPATH=src .venv/bin/python -m egfr_lab verify-collection data/raw/chembl_full_<날짜>
PYTHONPATH=src .venv/bin/python -m egfr_lab audit data/raw/chembl_full_<날짜>

# 추론 서비스
docker build --platform linux/arm64 -f deployment/Dockerfile -t egfr-pilot22-inference:v1 .
docker run -d --name egfr-serve -p 127.0.0.1:8010:8000 egfr-pilot22-inference:v1
curl -s http://127.0.0.1:8010/readyz

# 검증
PYTHONPATH=src .venv-serve/bin/python scripts/verify_serving_m6.py \
    --container-url http://127.0.0.1:8010 --container-name egfr-serve \
    --out reports/serving_m6_<날짜>
```

`>10 nM` 같은 부등호 측정은 정확값 회귀의 정답으로 변환하지 않는다. 포트 8000은 쓰지 않는다 — 이 기계에서 다른 프로세스가 IPv4로 점유하고 있어 요청이 그쪽으로 간다([겪은 일](reports/serving_m6_20261021/serving_report_ko.md)). 클라우드 배포 순서와 비용 통제 규칙은 [`deployment/README.md`](deployment/README.md)에 있다.

## 구조

```
configs/
  project.json              표적·정제·평가 정책, 단계 상태
  cohort_policy.json        선정 규칙, pooling 13필드 조건
  portfolio_scope.json      마일스톤 상태와 결론, 미실행 항목
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

출력을 실행별로 보관하고 덮어쓰지 않는다. `evaluation/`·`features/`·`literature/` 패키지는 비어 있고, 각 docstring에 실제 구현 위치를 적었다.

## 보고서와 설계 문서

| 결과 보고서 | 내용 |
|---|---|
| [`apsel_review_and_baseline_ko.md`](reports/apsel_review_and_baseline_ko.md) · [`baseline_pilot_20261020_v2/`](reports/baseline_pilot_20261020_v2/) | M1 기준 모델, 독립 검증 |
| [`dmpnn_pilot22_20261021_v2/`](reports/dmpnn_pilot22_20261021_v2/) | M2 D-MPNN 비교 |
| [`benchmark_repro_report_ko.md`](reports/sampl_repro_20261021_v2/benchmark_repro_report_ko.md) | M3 SAMPL 축소 재현 |
| [`company_paper_case_hbe843.md`](reports/company_paper_case_hbe843.md) · [`m4_access_evidence_20261021/`](data/raw/m4_access_evidence_20261021/) | M4 문헌 카드, 접근 차단 증거 |
| [`agent_llm_report_ko.md`](reports/agent_eval_20261021_final_openai/agent_llm_report_ko.md) | M5 Agent 평가 |
| [`serving_report_ko.md`](reports/serving_m6_20261021/serving_report_ko.md) · [`cloud_report_ko.md`](reports/serving_m6_cloud_20261022/cloud_report_ko.md) | M6 컨테이너·클라우드 |
| [`data_audit_summary_ko.md`](reports/data_audit_summary_ko.md) · [`cohort_scope_evidence_ko.md`](reports/cohort_scope_evidence_ko.md) | 데이터 감사, 적용 범위 검토 |

| 설계 문서 | 내용 |
|---|---|
| [`01_blueprint.md`](docs/01_blueprint.md) | 프로젝트 설계, 데이터·평가 기준 |
| [`02_bio_medical_primer.md`](docs/02_bio_medical_primer.md) | 바이오·메디컬 학습 가이드 |
| [`03_tech_stack.md`](docs/03_tech_stack.md) | 기술 스택, 선택 이유, Chemprop 버전 정정 |
| [`04_reproduction.md`](docs/04_reproduction.md) | 논문 재현 범위와 실험 기록 |
| [`05_references.md`](docs/05_references.md) | 출처와 인용 목록 |
| [`15_learning_guide_medical_ai_ko.md`](docs/15_learning_guide_medical_ai_ko.md) · [`16_project_definition_and_results_ko.md`](docs/16_project_definition_and_results_ko.md) | 정리 PDF 원고 |

## 라이선스와 출처

ChEMBL 원 데이터는 CC BY-SA 3.0이다. 데이터를 공개할 때 출처·release·가공 내용·라이선스를 함께 기록한다. 논문 원문은 별도 이용 조건을 확인한다. [ChEMBL 공식 라이선스](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/general-questions)

유료 콘텐츠를 우회하지 않는다. 접근할 수 없으면 접근할 수 없다고 기록한다.
