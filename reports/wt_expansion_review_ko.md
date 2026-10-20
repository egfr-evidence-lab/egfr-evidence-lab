# 추가 범위 반영과 학습 데이터 확대 검토

현재 실행은 M1의 데이터 확보 단계입니다. **규모만 늘려 학습하지 않고, 원문과 충돌하는 관측을 식별해 보류했습니다. 새 학습 승인 0건·새 실험 병합 승인 0쌍이며 모델 학습은 미실행입니다.**

## 이번에 실제 수행한 검토

- WT 보류 37개 assay 중 12개(기존 확대 후보 154건)를 대상으로 접근 또는 검토를 수행했습니다. 품질·구조 등 다른 보류 이유까지 포함한 원 관측 199건을 함께 추적했습니다. 37개 전부의 방법 검토가 끝난 것은 아닙니다.
- PMC 본문과 공식 ACS Figshare SI 5개를 확보했습니다. 출판사 본문 403, SI 후보 경로 404, 일부 다운로드의 HTML challenge도 실패 상태로 보존했습니다.
- SI 원 논문 DOI·공개 메타데이터·파일 해시를 연결했습니다. PDF의 핵심 방법 페이지는 텍스트 추출과 화면 렌더링으로 함께 확인했습니다.
- 화합물 번호 → 공식 ChEMBL compound_record → 문헌·assay·분자·activity ID로 11건을 대조했습니다. 값만 같은 행을 찾아 연결하지 않았습니다.
- 기존 37개 목록 밖의 대규모 미확정 실험도 사전 점검했습니다. 표적 상태·정확값·부등호·구조 보류·출처 유형을 함께 기록했습니다. 최소 80행은 검토 순서를 위한 프로젝트 선택값이며 학습 적격성 기준이 아닙니다.

## 1. 유래 문제는 일부 해결했지만 최종 학습 승인은 별개

CHEMBL2439336의 SI에서 제품 PV3872를 확인하고 공식 공급사 제품 정보·COA의 인간 EGFR과 연결했습니다. 해당 제품의 서열은 668–1210, GST tag입니다. 26개 후보의 종 유래 보류 사유를 해소할 근거가 생겼습니다. 현재 공급사 자료는 논문의 실제 사용 lot 확인과 구별합니다. [원 SI](https://acs.figshare.com/articles/journal_contribution/2362825), [공식 제품](https://www.thermofisher.com/proteins/product/Human-EGFR-ErbB1-GST-Tag-Recombinant-Protein/PV3872)

CHEMBL5638807도 논문에 적힌 Carna 08-115와 공식 문서의 인간 EGFR 669–1210을 연결했습니다. 이 실험에서 다른 사유 없이 유래만으로 보류된 후보는 1건입니다. 합계 **27건은 유래 문제의 해소 근거를 얻었으며 학습에 추가한 27건이 아닙니다.** [원문](https://pmc.ncbi.nlm.nih.gov/articles/PMC11089552/), [Carna 공식 자료](https://www.carnabio.com/profiling_pdf/p108.pdf)

## 2. 별도 실험의 조건을 복사하면 안 되는 사례

Pemberton 등의 2024년 논문은 주 ADP-Glo 실험과 ATP 농도 비교 실험을 구분합니다.

| 관측 | ChEMBL 설명 | 원문·SI 근거 | 결정 |
|---|---|---|---|
| CHEMBL5638807 | ADP-Glo, 사전 반응 15분·반응 50분 | 주 방법과 연결. ATP 최종 농도는 각주·혼합 recipe 구분 필요 | 조건 모호성 보류 |
| CHEMBL5638814 | ADP-Glo, ATP 10 µM | SI S14에는 ThermoFisher Z′-LYTE | 원 4건 보류 |
| CHEMBL5638815 | ADP-Glo, ATP 1,000 µM | 같은 SI S14의 별도 Z′-LYTE 실험 | 원 4건 보류 |

저·고 ATP 비교의 8개 pIC50는 본문 Table 2와 반올림 범위에서 일치했습니다. **숫자가 맞아도 실험법 설명은 다를 수 있습니다.** 주 ADP-Glo의 15/50분이나 Carna 제품을 별도 Z′-LYTE 실험에 전용하지 않습니다. [논문](https://doi.org/10.1021/acsmedchemlett.3c00425), [공식 SI](https://acs.figshare.com/articles/journal_contribution/25554841)

주 방법은 12 µM ATP 용액 2 µL를 효소 용액 2 µL와 섞는다고 적습니다. 그대로 계산하면 6 µM지만 표 각주는 12 µM를 제시합니다. 원 기재와 희석 계산을 별도 필드에 저장했고 최종 농도를 임의 확정하지 않았습니다.

## 3. SI 곡선 값과 본문 집계값을 구분해야 하는 사례

Zhou 등의 SI S2 Figure S1을 공식 화합물 번호로 연결했습니다.

| 화합물 | SI 곡선 IC50, nM | ChEMBL, nM |
|---|---:|---:|
| WZ4002 | 9.58 | 2.16 |
| 3q | 1.47 | 1.21 |
| 3x | 3.67 | 3.82 |

차이는 확인했지만, 반복 평균과 개별 curve fit의 관계가 본문 표에 설명돼 있을 수 있습니다. 본문 표 확인 전에 전사 오류라고 단정하거나 SI 값으로 덮어쓰지 않습니다. SI의 효소 농도 기재 `0.287 µg/µL`도 stock/final 의미와 단위 타당성 확인이 필요합니다. [원 논문](https://doi.org/10.1021/jm401045n), [공식 SI](https://acs.figshare.com/articles/journal_contribution/2362825)

## 4. 가장 큰 후보의 표적 열 혼입 정황

미확정 단일 assay CHEMBL5736995는 981건으로 컸습니다. 원 특허 US11066414B2에는 Cot 실험과 EGFR 실험이 함께 있습니다. 특허의 Table 3 직전 문장은 해당 표가 Cot 억제 결과임을 명시하고, Tables 4·5는 별도의 EGFR 열을 제시합니다. [원 특허](https://patents.google.com/patent/US11066414B2/en)

공식 compound_record의 특허 화합물 번호와 원 activity의 `record_id`·문헌·분자 ID를 연결하고 다음 결과를 얻었습니다.

| 원 관측의 수치 연결 | 건수 |
|---|---:|
| Cot Table 3 열과 일치, 명시 EGFR 열과 일치하지 않음 | 928 |
| 명시 EGFR 열과 일치 | 1 |
| 확인한 표의 정확값과 일치하지 않음 | 46 |
| 부등호·비정확값으로 별도 검토 | 6 |
| 합계 | 981 |

특히 화합물 362는 Cot IC50 **1 nM**, EGFR IC50 **3,984 nM**입니다. 동일 record 4509835에 연결된 두 값이 같은 assay에 존재합니다: activity 28404131의 1 nM와 28406027의 3,984 nM. 같은 assay ID라고 동일 표적의 반복값으로 집계하면 안 됩니다.

이는 표적 열 혼입을 의심할 구체적 근거입니다. 수치 일치만으로 모든 928건의 구조와 원 전사까지 검증한 것은 아니며, 981건 전체를 오류로 판정한 것도 아닙니다. **전체 assay를 코호트 승인에서 보류**하고, 관측별 원 표적·구조를 재검토합니다. ChEMBL 원자료는 수정하지 않았습니다. 공식 기관에 오류 확정을 받았거나 정정을 요청했다는 뜻도 아닙니다.

## 다른 공개 자료와 다음 순서

Grabe 등 SI S6에서 WT ATP 9.5 µM, 효소 0.67 nM, 기질 1 µM, 사전 반응 30분·반응 25분을 확인했습니다. 상용 효소 lot의 유래와 미분류 분자 구조는 추가 확인이 필요합니다. 결정 구조용 단백질과 측정용 상용 효소를 동일시하지 않습니다. [원 논문·SI](https://doi.org/10.1021/acsmedchemlett.2c00514)

Wu 등 SI page 2에서 HTRF, ATP 1.65 µM, 사전 반응 5분·반응 30분을 확인했으나 Sigma 제품 번호가 없어 종 유래는 미확인입니다. 사람 세포 실험의 유래를 별도 효소 실험에 옮기지 않습니다. [원 논문·SI](https://doi.org/10.1021/ml4002437)

후속 우선 검토 대상으로 Apsel 등의 공개 논문(209건 중 정확한 양수 nM 167건)을 찾고 본문·저자 공개 PDF·화합물 record를 보관했습니다. ATP 10 µM의 방사성 인산 전달 방법은 확인했으나 ChEMBL의 confidence 8·homolog 연결과 WT/유래·상세 프로토콜은 아직 해결하지 않았습니다. SI 다운로드 후보는 실패 상태입니다. 확정 학습 데이터로 사용하지 않습니다. [원 연구](https://doi.org/10.1038/nchembio.117), [공개 본문](https://pmc.ncbi.nlm.nih.gov/articles/PMC2880455/)

이 자료의 상세 단백질 근거와 남은 WT 원문 검토를 진행한 뒤 충분한 단일 맥락 데이터가 확보되면 M1의 Dummy·Morgan-RF로 넘어갑니다. 본문 확인이 불가능하거나 표본이 부족하면 그 범위를 먼저 기록합니다. 보편 합격선처럼 기준을 낮추거나 성능을 보고 코호트 규칙을 변경하지 않습니다.

## 재실행·산출물

원 검토와 이번 확대 검토를 별도 폴더에 보존했습니다. 출력 폴더가 있으면 재생성을 거절합니다.

```bash
.venv/bin/python scripts/fetch_wt_expansion.py --offline
.venv/bin/python scripts/review_wt_expansion.py --verify-only
.venv/bin/python scripts/check_wt_expansion.py
```

- `data/interim/wt_expansion_review_20261020_v1/`: CSV 6개, 근거 스냅샷, 입력·출력 해시 매니페스트.
- `data/interim/large_assay_triage_20261020/`: 대규모 후보의 정확값·출처 사전 점검.
- `data/interim/patent_target_review_20261020/`: 981건 원 표 열 대조와 매니페스트.
- [원문 검토 보류 목록](../configs/source_review_holds.json): 향후 학습 코호트 선정에서 확인할 5개 assay.
- [확대 검토 근거](../configs/wt_expansion_evidence.json): 원 기재·추론·공급사 정보·미확인 구분.

공개 SI의 라이선스는 Figshare 원 메타데이터에 기록했습니다. 원문 PDF는 Git 제외 원자료 폴더에 보관하며 보고서에서 URL과 근거 위치를 연결합니다. 사람의 독립 이중 검토·실험 재현·모델 성능 검증은 이번 산출물에 포함되지 않습니다.

검증 결과: 기존 35개와 표적 열 혼동·부등호/동일값 모호성 회귀 검사 2개를 포함해 **총 37개 테스트 통과**. 공개 응답 50개 SHA-256, SI 5개 공급자 MD5, 원문 대조·검토표 해시·ID·행수·보류 상태, 기존 감사·코호트 매니페스트 보존을 확인했습니다. [기계 검증 기록](wt_expansion_validation.json). `git diff --check`도 통과했습니다.
