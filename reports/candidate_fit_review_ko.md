# 주 학습 코호트 후보 적합성 검증

2026-10-20. 질문: **"지금까지의 후보 중 어느 것이 프로젝트에 가장 잘 맞는가."**
새 수집·새 학습은 하지 않았다. 기존 동결 산출물만 읽고, 프로젝트 자신의 기준으로 대조했다.
**이 검증의 결과는 학습 승인이 아니다.** 승인 건수는 여전히 0이다.

## 1. 검증 방법

### 1.1 게이트의 출처

판정 기준을 새로 만들지 않고 프로젝트에 이미 있는 불변 규칙에서 가져왔다.
`configs/cohort_policy.json`(wt-biochemical-context-v1), `configs/project.json`의 `curation`,
`HANDOFF.txt` 7번 "바꾸지 말아야 할 과학적 구분"이 출처다.

| 게이트 | 근거 규칙 |
|---|---|
| variant_confirmed_WT | `unknown_variant_is_wild_type: false` — 변이 미기재를 WT로 채우지 않음 |
| format_biochemical | `pool_cell_and_biochemical_assays: false` — 생화학/세포 혼합 금지 |
| species_human | primary_task "인간 WT EGFR" — 종 미확인은 보류 |
| structures_verified | `chemistry.unknown_molecule_type_needs_structure_review: true` |
| no_duplicates | `repeats.never_aggregate_across_unverified_assays: true` |
| exact_only | 부등호·구간 측정을 정확값 회귀 라벨로 변환 금지 |
| primary_text_accessible | "기술 선택·도메인 해석에 공식 문서·원 논문 인용" |
| quantitative_conditions_known | `critical_fields`의 atp_uM·temperature_C·readout 등 |
| no_source_conflict | "원자료·제외 사유 보존, 충돌은 보류" |

### 1.2 입력과 재현

```bash
PYTHONPATH=src .venv-ml/bin/python scripts/review_candidate_fit.py \
    --output-dir data/interim/candidate_fit_review_20261020
```

입력(해시는 `data/interim/candidate_fit_review_20261020/manifest.json`):
`data/interim/main_cohort_inventory_20261020/source_priority_queue.csv`(242 assay),
`data/interim/cohort_scope_diagnostics_20261020/cohort_metrics.csv`, `configs/cohort_policy.json`.

5개 게이트(변이·형식·구조·중복·정확값)는 동결 CSV에서 **기계적으로** 계산했다.
4개 게이트(종·원문접근·정량조건·충돌)는 사람이 확인한 근거를 경로·인용과 함께 스크립트에 명시했고,
확인하지 않은 항목은 `pass`가 아니라 `unknown`으로 남겼다.

### 1.3 모집단

242 assay 전체에서 자동 보류 사유가 **완전히 빈 행은 2건뿐**이다
(`CHEMBL5737421`, `CHEMBL4258549`). `variant_screen=WT` **그리고** `format_screen=biochemical_candidate`인
행은 12건이며, 그중 10건은 `species_unclear` 또는 `target_link`가 남아 있다.

## 2. 결과

| 후보 | 통과/실패/미확인 | n(정확값) | scaffold | 최대골격비 | pIC50 폭 |
|---|---|---:|---:|---:|---:|
| **pilot22 `CHEMBL4258549`** | **9 / 0 / 0** | 22 | 12 | 0.500 | 1.647 |
| patent64 `CHEMBL5737421` | 6 / 3 / 0 | 50 | 30 | 0.191 | 0.954 |
| 981건 `CHEMBL5736995` | 5 / 4 / 0 | 975 | 218 | 0.131 | 3.984 |
| BLU-945 `CHEMBL5141216` | 4 / 4 / 1 | 24 | 6 | 0.478 | 1.569 |
| Apsel209 `CHEMBL1243977` | 3 / 3 / 3 | 167 | 58 | 0.381 | 3.699 |
| furan45 `CHEMBL5382277` | 3 / 4 / 2 | 45 | 19 | 0.395 | 2.723 |

**9개 게이트를 모두 통과한 후보는 `CHEMBL4258549`(pilot22) 하나뿐이다.**
(DOI 10.1039/C7MD00571G, PMID 30108918, Europe PMC `pmcid=PMC6083791`, `inEPMC=Y`, availability에 `Free` 포함 — 2026-10-20 재확인.)
ChEMBL assay 설명이 **"Inhibition of Wild type human EGFR using poly(Glu, Tyr) 4 : 1 as substrate after 1 hr by ELISA"**로
종·변이·형식·기질·시간을 모두 명시하고, 원문에서 ATP 5 µM·37 °C·60분·ELISA를 확인했으며,
구조 보류 0·중복 0·부등호 혼입 0(raw 22 = exact 22)이다.

실패 사유 요약:
- **patent64**: 구조 보류 64건, raw 64 중 정확값 50(부등호 14 혼입), 원 MS와 DB 구조 계산값이 35관측 중 13관측에서 약 14–30 Da 차이.
- **981건**: Table 3 앞 문장이 Cot 결과이고 928건이 Cot 열과 일치 — 표적 열 혼입 정황으로 assay 전체 보류.
- **furan45**: 종 미확정, 정량 조건 미확인, 실험법을 위임한 ref28 본문이 구독 전용(ACS 403 / Europe PMC "Subscription required" / NHRI 권리안내 HTML).

## 3. 이번 검증에서 새로 나온 두 가지 사실

### 3.1 ChEMBL이 ref28 본문의 assay를 이미 큐레이션해 두었다

242 큐에 `pmid=31560541`(= ref28, Lin 2019) 행이 두 개 있다.

| assay | 설명 | 정확값 |
|---|---|---:|
| `CHEMBL4416105` | "Inhibition of GST-tagged **human** EGFR kinase domain (696 to 1022 residues) using poly(Glu, Tyr) 4:1 substrate incubated for 60 mins by kinase-Glo plus luminescent kinase assay" | 25 |
| `CHEMBL4416106` | 같은 문헌의 **L858R/T790M 변이** 기록, 기질·시간 다름(120 mins) | 20 |

furan45(`CHEMBL5382277`)의 설명은
"GST-tagged recombinant wild type EGFR (G696 to G1022 residues) **(unknown origin)** … poly(Glu, Tyr) 4:1 … 60 mins … kinase-glo plus"이다.
**GST 태그·696–1022 구간·poly(Glu,Tyr) 4:1·60분·Kinase-Glo Plus가 모두 일치하고 종 표기만 다르다.**
여기에 PDB 6JZ0(같은 논문, Homo sapiens/P00533/696–1021/858=Leu·790=Thr)이 독립적으로 일치한다.

**그러나 이것으로 furan45의 `species_unclear`를 자동 해제하지 않았다.** `CHEMBL4416105`는 별개의 assay 기록이고,
"프로토콜 문자열이 같으니 효소 유래도 같다"는 것은 기록 간 추론이다.
`unknown_variant_is_wild_type: false`와 "불명확한 변이·종 추정 금지" 규칙에 따라 **사람의 독립 검토 대상으로만 올린다.**
다만 해소 경로가 하나에서 둘(ChEMBL 큐레이션 + PDB)로 늘었고, 두 근거가 서로 충돌하지 않는다.

### 3.2 BLU-945는 DB 설명이 원문을 넘어선다 — 새 충돌

BLU-945 논문은 오픈액세스이고 전문 XML이 로컬에 있다(`data/raw/protocol_discovery_20261020_v2/PMC9340769.xml`).
원문 "Inhibition of EGFR Mutant Biochemical Enzymatic Activity" 절은 조건을 완전히 기술한다:
기질 2.5 µM, **ATP 1 mM**, 10 mM MgCl₂, 0.015% Brij-35, 1 mM DTT, 1% DMSO, 100 mM HEPES **pH 7.5**, **25 °C**,
억제제 **10분 사전배양**, Caliper EZReader 2, 인산화 10–20%에서 EDTA로 정지.

그런데 두 가지가 어긋난다.

1. **기질 펩타이드 불일치** — 원문은 `5-FAM-EEPLYWSFPAKKK-CONH2`, ChEMBL 설명은 `5-FAM-EEPLYINSFPAKKK-CONH`.
2. **원문에 없는 정보가 DB 설명에 있음** — 원문 전체에 `GST`, `Sf9`, `insect`가 **한 번도 나오지 않는다**. 효소는 `WT and mutant EGFR enzymes (SignalChem)`로만 적혀 있다. ChEMBL 설명의 "N-terminal GST tagged … baculovirus infected Sf9 insect cells"는 공급사 제품정보에서 온 것으로 보이나 원문 근거가 아니다.

어느 쪽이 옳은지 확정하지 않는다. **DB 설명을 원문으로, 원문을 DB 오류로 단정하지 않고 양쪽을 보존한 채 보류**한다.
또한 이 실험은 ATP 1 mM로 pilot22(5 µM)·patent64(10 µM)와 실험 맥락이 다르므로 **어떤 경우에도 합치지 않는다**.

참고로 이 assay의 자동 보류 사유 `format_not_biochemical`은, 설명에 있는 "Sf9 insect **cells** expression system"(발현용 세포)
때문에 걸렸을 가능성이 있다. HANDOFF.txt가 예고한 보수적 규칙의 과검출 후보다. 분류 정확도는 여전히 평가하지 않았다.

## 4. 해석 — "가장 잘 맞는다"의 한계

pilot22가 유일한 전 게이트 통과 후보라는 사실은 **검증 품질 기준**의 결과이지 **데이터가 충분하다**는 뜻이 아니다.
`data/interim/cohort_scope_diagnostics_20261020/cohort_metrics.csv`의 동결 수치로 보면:

| 지표 | pilot22 | furan45 | patent50 |
|---|---:|---:|---:|
| 관측 / 고유 입체구조 | 22 / 22 | 45 / 45 | 50 / 48 |
| connectivity 그룹 | 22 | 43 | 47 |
| scaffold | 12 | 19 | 30 |
| 최대 골격 비율(connectivity 기준) | 50.0% | 39.5% | 19.1% |
| inverse Simpson scaffold | 3.67 | 5.39 | 14.83 |
| pIC50 폭 / IQR | 1.647 / 0.626 | 2.723 / 0.912 | 0.954 / 0.512 |

**검증은 가장 깨끗하지만 다양성은 가장 좁다.** 22건 중 11건이 한 scaffold이고 inverse Simpson은 3.67이다.
기존 교육용 실험에서 seed42 scaffold 3-fold의 RF−Dummy MAE 차이가 −0.0146,
탐색 95% 구간 [−0.0819, +0.0506]으로 0을 포함해 우위가 확정되지 않았던 것은
**모델의 실패가 아니라 이 표본 크기·골격 편중에서 기대되는 결과**로 읽는 편이 일관된다.
(이 해석은 기존 수치의 재해석이며 새 실험이 아니다.)

## 5. 결론과 선택지

**검증된 사실**
- 242 assay 중 9개 게이트를 모두 통과한 단일 assay는 `CHEMBL4258549`(pilot22) 1건이다.
- 자동 보류 사유가 빈 행은 242건 중 2건이며, 다른 1건(patent64)은 구조·부등호·MS 충돌에서 탈락한다.
- furan45의 종 문제는 해소 **경로**가 2개(ChEMBL `CHEMBL4416105`, PDB 6JZ0)로 늘었고 서로 충돌하지 않는다.
- BLU-945에서 DB-원문 충돌 1건을 새로 발견했다.

**설계 제안(승인 아님)** — 세 갈래 중 선택이 필요하다.
1. **pilot22를 주 코호트로 승격**하고, 적용 범위를 "단일 문헌·22건·12골격의 탐색적 회귀"로 명시해 M1을 닫는다. 장점은 모든 게이트가 이미 통과라는 것, 단점은 교육용으로 쓴 자료와 주 코호트가 같아져 새 증거가 늘지 않는 것이다.
2. **furan45의 종 보류를 사람 검토로 해제 시도** — `CHEMBL4416105` 설명과 PDB 6JZ0을 근거로 삼되, 정량 조건(ATP 농도 등)은 끝내 미확인으로 남는다는 점을 명시한다. n=45·19골격·폭 2.723으로 pilot22보다 넓다.
3. **둘 다 하지 않고 큐의 `species_unclear` 9건을 추가 조사** — 다만 이들 대부분은 구독 전용 문헌이다(이번 재검증에서 PMID 보유 134문헌 중 Europe PMC 오픈액세스는 4건뿐).

**미확인으로 남는 것**: 어떤 선택을 해도 cross-assay pooling 승인은 0쌍을 유지한다.
서로 다른 ATP 농도(5 µM / 10 µM / 1 mM)와 readout(ELISA / TR-FRET / Caliper)을 한 라벨로 합치지 않는다.
사람의 독립 이중 검토는 아직 수행하지 않았다.

## 6. 포트폴리오(사이드 프로젝트) 용도로 지금 쓸 수 있는가

질문을 분리한다. **"EGFR 활성을 신뢰성 있게 예측하는 모델인가"는 아니다**(22건·12골격·단일 문헌).
**"공개 바이오 데이터를 수집·정제·검증할 수 있음을 보이는 포트폴리오인가"는 그렇다.** 근거는 아래와 같다.

### 6.1 프로젝트 자신의 M1 완료 기준 대조 — 4/4 충족

`configs/portfolio_scope.json`의 M1 `completion_evidence` 네 항목에 대응 산출물이 실재한다.

| M1 완료 기준 | 대응 산출물 | 상태 |
|---|---|---|
| 원문 근거가 연결된 코호트 결정과 제외·보류표 | `reports/cohort_definition_evidence.md`, `configs/source_review_holds.json`, `data/interim/audit_chembl_full_20261020/manual_review_queue.csv`(2,425행) | 있음 |
| 분자·scaffold 누출 검사와 고정 분할 | `prospective_fold_metrics.csv`의 pilot22 scaffold 3-fold: 골격중복 0·connectivity중복 0·평가행 중 학습골격 보유 0 (fold별 11/11, 16/6, 17/5) | 있음 |
| Dummy와 Morgan-RF의 동일 시험 자료 평가 | `reports/baseline_pilot_20261020_v2/`, `artifacts/.../v2`(저장 모델 36개), 독립 검증 `baseline_pilot_validation.json` `passed=true` | 있음 |
| 오차·불확실성·실패 사례·적용 범위 보고 | `apsel_review_and_baseline_ko.md`, `dataset_card.md`, 본 보고서 4절 | 있음 |

포트폴리오 보고서 5절의 **우선순위 1번**("확정 데이터 + Dummy/Morgan-RF의 최소 완결 실험",
완료 판단 = 누출 검사·고정 분할·기준 모델 대비 오차와 95% 구간·데이터 한계) 역시 네 요소가 모두 충족된다.

### 6.2 실제 차별점은 모델 성능이 아니라 검증 깔때기

동결 자료에서 직접 계산한 수치다.

| 단계 | 수 | 비율 |
|---|---:|---:|
| 원 측정(ChEMBL_37, CHEMBL203/human/IC50) | 26,600 | 100% |
| 고유 분자 / assay / 문헌 | 14,776 / 2,425 / 1,299 | — |
| 자동 감사 통과 후보 | 264 | 0.99% |
| 원문 검토 대기 assay 큐 | 242 | — |
| 자동 보류 사유 0건 assay | 2 | — |
| 9게이트 전부 통과 assay | 1 | — |
| **최종 완전 검증 측정값** | **22** | **0.083%** |

**26,600건에서 방어 가능한 22건을 남기는 과정 자체가 산출물이다.** 이는 "데이터가 있다"와
"데이터를 신뢰할 근거가 있다"를 구분할 수 있음을 보여주며, 채용 공고의 전처리·통계 검증 요건과 직접 연결된다.
적합성 보고서 1절이 이 항목을 이미 "공개 데이터 경험의 실물 증거 있음"으로 판정했다.

### 6.3 재현 가능성 증거

테스트 52개 통과, 스크립트 27개, 모든 산출물에 입력·출력 SHA-256 manifest, 독립 검증 스크립트
(`check_baseline_pilot.py`, `check_main_cohort_acquisition.py`, `check_cohort_scope.py`) 통과,
저장 모델 36개 재로딩 후 OOF 264행 예측 일치 확인.

### 6.4 조건 — 이렇게 제시해야 한다

| 제시 방식 | 판정 |
|---|---|
| "ChEMBL EGFR 26,600건에서 출처·실험조건을 검증해 방어 가능한 22건을 특정하고, 누출 없는 분할로 기준 모델을 평가했다" | **적합** |
| "EGFR 활성 예측 모델을 만들었다" / "RF가 더 좋았다" | **부적합** — n=22이고 RF−Dummy 95% 구간 [−0.0819, +0.0506]이 0을 포함한다 |

RF가 Dummy를 못 이긴 것은 숨길 약점이 아니라 **표본 22건·최대 골격 50%에서 예상되는 결과**이며,
그것을 그대로 보고한 것이 오히려 통계 해석 역량의 증거다. 면접에서 먼저 말하는 편이 낫다.

### 6.5 이 포트폴리오가 아직 덮지 못하는 것

공고 우대사항 중 **딥러닝(M2)·논문 재현(M3)·Agent(M5)·클라우드(M6)는 여전히 미실행**이다.
pilot22로 닫히는 것은 우선순위 1번 하나다. `src/egfr_lab`의 `agent/`·`evaluation/`·`features/`·`literature/`는 빈 뼈대다.

**결론: 사이드 프로젝트 포트폴리오로 지금 사용해도 된다. 단 헤드라인은 "검증 파이프라인"이고 "예측 모델"이 아니다.**

## 7. 본문 추출 작업 종료 기록

ref28(Lin 2019) 본문 확보 시도를 여기서 종료한다. 종료 시점의 상태는 다음과 같다.

- **확보 불가 확정**: ACS 구독 정책(403 / "Subscription required" / 기관 레포지토리 권리안내).
  경로별 인용·해시는 `data/raw/scope_evidence_20261020_v3/manifest.json#access_blocked_log`.
- **대신 확보한 것**: PDB 6JZ0(저자 기탁, human/P00533/696–1021/WT), Coumar 2010 SI 전문(분석법 없음 확인),
  그리고 **ChEMBL이 큐레이션한 ref28 자체의 assay 기록**.
- **추가 확인**: ref28의 측정 52건(`CHEMBL4416105` WT 26행, `CHEMBL4416106` L858R/T790M 26행,
  관계 `=` 45 / `>` 7)이 **이미 우리 동결 수집본 `activity_audit.csv`에 들어 있다.**
  즉 본문 PDF는 못 얻었지만 그 논문의 측정값과 큐레이션된 실험 조건은 이미 프로젝트 안에 있다.
- **남는 미확인**: ATP 농도·효소량·기질 농도·온도·buffer pH. 이는 본문에만 있으며 접근 불가로 확정한다.

더 이상 같은 경로를 재시도하지 않는다. 새로운 공개 원고나 저자 제공 자료가 나타날 때만 재개한다.
