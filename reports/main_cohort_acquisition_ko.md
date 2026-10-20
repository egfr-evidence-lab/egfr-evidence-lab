# 주 학습 데이터 확보 절차와 첫 실행 결과

후속 검토: [실제 지표와 적용 범위](cohort_scope_evidence_ko.md)에 2019년 원문 탐색·WT 특허 구조/MS 점검·예정 분할과 화학 거리 진단을 추가했다. 아래는 첫 실행 시점의 기록이며 최신 테스트는52개 통과다.

2026-10-20. [단계별 실행안](../docs/12_main_cohort_acquisition_ko.md)을 작성한 뒤 전체 자료 재집계·공개 자료 확보·7개 assay의 원문 대조를 실행했다. **새 주 학습 코호트는 아직 승인하지 않았다.** 가장 유망한 새 후보는 원 저자 CSV의 WT IC50 45건이며, human 종 유래와 인용된 상세 실험법 확인이 남았다. 기존 22건 교육 실험·209건 보류·원 ChEMBL 자료는 보존했다.

## 단계별 진행 상태

| 단계 | 이번 실행 | 상태 |
|---|---|---|
| 1. 대상·보류 고정 | 인간 WT·생화학 IC50 목적과 기존 병합 정책 유지 | 완료 |
| 2. 전체 후보 재정렬 | 26,600관측·2,425assay 재집계, 검토 대기242assay | 완료. 대기242개 모두 원문을 읽은 것은 아님 |
| 3. 원문·SI 확보 | 공개 특허3개, ACS SI PDF6개·CSV5개·XLS1개, 공식 record와 PMC 본문/XML 등 보관 | 이번 우선 후보 접근 완료. 일부 원문은 접근 제한 |
| 4. 관측별 대조 | 7assay·787관측에 수치·관계 기호·원 화합물 키 연결, 3개 저자CSV는 구조도 대조 | 이번 우선 후보 대조 완료. 구조 차이·미수록 항목은 보류 |
| 5. 중복·범주값·보류 판정 | 동일173행 블록, 원 구간 중간값180건, 원문/DB 차이를 새 등록부에 기록 | 완료. 학습 승인0건 |
| 6. 주 코호트 범위·분할 가능성 | 새45건의 구조·골격·라벨 범위 진단 | 1차 진단 완료. 조건·반복 오차·최종 분할 검토 남음 |
| 7. 학습 데이터·분할 고정 | 원문 대조 후보45건과 억제율4건을 별도 버전·해시로 보존 | 후보 버전만 고정. `training_ready=false`, 최종 시험 분할 미확정 |
| 8. 주 기준 모델 실험 | 새 자료의 모델 학습 | 미실행. 기존22건 교육 결과를 주 성능으로 바꾸지 않음 |

242개를 고른 정확값20건 기준은 검토 표를 줄이는 작업상 기준이다. 학습 승인에 필요한 보편적 최소 표본 수가 아니다. 기존에 분자 유형이 Unknown이라 scaffold가 충분히 계산되지 않은 자료도 **검토용으로만** 다시 파싱했다. 새 구조 집계로 이전 감사의 승인 상태를 바꾸지 않았다.

## 가장 유망한 후보: 2023년 furanopyrimidine 논문

대상은 *Development of Furanopyrimidine-Based Orally Active Third-Generation EGFR Inhibitors for the Treatment of Non-Small Cell Lung Cancer*, DOI [10.1021/acs.jmedchem.2c01434](https://doi.org/10.1021/acs.jmedchem.2c01434), [PMC9969398 공개 본문](https://pmc.ncbi.nlm.nih.gov/articles/PMC9969398/), assay CHEMBL5382277이다. 저자 CSV는 [공식 ACS Figshare 항목22043033](https://acs.figshare.com/articles/dataset/Development_of_Furanopyrimidine-Based_Orally_Active_Third-Generation_EGFR_Inhibitors_for_the_Treatment_of_Non-Small_Cell_Lung_Cancer/22043033)의 `resource_doi`와 제공자 MD5를 대조해 확보했다. 실제 파일ID는39124670이다. 메타데이터의 이용 조건은 CC BY-NC 4.0이며, ChEMBL 원 데이터의 CC BY-SA 3.0과 자동으로 같다고 취급하지 않는다. 이번에는 원문·저자 원 파일을 로컬 Git 제외 폴더에 보존했다.

| 항목 | 실제 확인 결과 |
|---|---|
| 저자 CSV 전체 | 49화합물 |
| 정확한 WT IC50 숫자 | 45건 |
| IC50가 아닌 항목 | 특정 농도에서의 억제율4건: 화합물16·19·22·23. 회귀 후보에서 별도 분리 |
| 수치 연결 | 공식 record→activity 연결. 43건 정확 일치 |
| 작은 정밀도 차이 | 화합물36: 저자25.3 vs DB25 nM, 화합물56:24.9 vs25 nM. 정수 반올림과 양립하지만 원인을 확정하지 않음 |
| 구조 연결 | 45/45 isomeric graph 일치. 원 저자 SMILES와 입체정보 보존 |
| 다양성 | 45고유 입체구조·43connectivity그룹·19scaffold. 최대 골격17/43그룹(39.5%) |
| 라벨 범위 | 원 저자 IC50 8–4,230nM, pIC50 폭 약2.723 |
| 현 원문에서 확인 | WT와 L858R/T790M의 구별, GST-G696–G1022 재조합 단백질, Kinase-Glo Plus, 최소2회 독립 실험·±15%라는 표 각주 |
| 남은 확인 | 단백질 human 종 유래, 상세 효소·ATP·기질·시간·온도 조건. 표 각주의 ±15%를 SD/SEM으로 해석하지 않음 |

본문 Methods는 상세법을 ref28인 [Lin 등2019, DOI10.1021/acs.jmedchem.9b00722](https://doi.org/10.1021/acs.jmedchem.9b00722)로 연결한다. 그 참조까지 추적했다. [연구기관 저장소 항목](https://ir.nhri.edu.tw/handle/3990099045/12290)의 PDF 링크는 실제로 권리·외부 원문 이동 안내 HTML을 반환했다. 2019년 ACS SI는 확보했지만 합성법·분석 자료 중심이며 상세 kinase 방법을 확인하지 못했다. **저장소에 PDF 이름이 보이거나 HTTP200을 받았다는 이유로 방법 원문 확보로 세지 않았다.** 결정학 단백질·세포 실험의 종을 효소 실험에 대신 넣지도 않았다.

별도 후보 `data/interim/furan_candidate_20261020/IC50_candidates_not_training_ready.csv`는 저자25.3·24.9를 그대로 보존한다. ChEMBL 값을 고친 파일이 아니다. 원 활동ID·원 감사 사유·두 수치 정밀도 차이·보류 이유를 함께 기록했다. `single_concentration_not_IC50.csv`에는 억제율4건이 있다. 45건은 더 넓은 라벨 범위를 가진 후보지만, 충분한 일반 EGFR benchmark를 확보했다는 뜻은 아니다.

## 큰 숫자를 그대로 학습하면 안 되는 실제 사례

**동일 자료의 두 assay ID:** CHEMBL3705421과 CHEMBL5729820은 같은 특허의 분자·관계·값173행 블록이 같다. 원 Table3의 HER-1 열·µM→nM 연결과도 맞지만 두 개의 독립173건 실험으로 세지 않는다. 각 블록의7관측에는 여러 원 화합물 번호가 연결돼 추가 구분이 필요하다. 유래·WT·원 구조 대조도 남았다. [원 특허 US8846699B2, TestExample4/Table3](https://patents.google.com/patent/US8846699B2/en).

**구간 중간값:** CHEMBL5733991의 DB 정확값 후보181건 중180건은 원 Table16의 B/C/D 구간과 연결되며, 저장값55·550·5,500nM가 그 산술 중간값이다. 나머지 정확값1건은 원 키 연결을 더 확인해야 한다. A/E 범주에 연결되는 부등호65건도 정확값 회귀에 넣지 않는다. 원 특허의 범주 표기는 A≤10, B10–100, C100–1000, D1000–10000, E≥10000nM이다. 경계 관계도 DB와 별도로 보존한다. 원문이 보고하지 않은 정확 IC50를 중간값으로 만들지 않는다. [US9987276B2, Example271/Table16](https://patents.google.com/patent/US9987276B2/en).

**조건이 명확해도 적용 범위가 좁은 경우:** CHEMBL5737421은 원문 Table3의64건(정확50·>10000nM14)이 모두 관계 기호와 수치까지 맞았다. TestExample3의 WT·ATP10µM·효소0.8ng/µL·Tyr04 2µM·25°C60분을 확인했다. PV3872의 human·GST·668–1210은 공식 공급사 catalog 근거이며 당시 lot 확인과 구별한다. 정확50건은48입체구조·47connectivity그룹·30scaffold지만 IC50가1002–9011nM에 몰린다. 원 G번호별 구조를 아직 대조하지 않았고, BTK 선택성 연구에서 얻은 약한 EGFR 활성 범위이므로 주 회귀 데이터로 자동 승인하지 않았다. [US11155546B2 TestExample3/Table3](https://patents.google.com/patent/US11155546B2/en), [PV3872 공식 정보](https://www.thermofisher.com/proteins/product/Human-EGFR-ErbB1-GST-Tag-Recombinant-Protein/PV3872).

## 다른 저자 CSV와 조건 검토

CHEMBL4038017: [DOI10.1021/acs.jmedchem.7b01612](https://doi.org/10.1021/acs.jmedchem.7b01612)의54개 합성 화합물은 원 저자 EGFR CSV 값과 일치했다. isomeric graph52건 일치·2건 차이이며 별도 대조약1건은 CSV에 없다. SI S2–S3는 정제 단백질 Z'-LYTE 방법이어서 기존 형식 보류를 다시 볼 근거가 된다. 그러나 EGFR0.287µg/µL 설명과 최종10µL 반응의 kinase0.002ng 설명의 관계가 미확정이다. 원 PDF를 렌더링해 숫자를 확인했고 이를 임의로 교정하거나 stock 농도로 확정하지 않았다.

CHEMBL4041412: [DOI10.1021/acs.jmedchem.7b00515](https://doi.org/10.1021/acs.jmedchem.7b00515)의31관측 중 저자 CSV와 수치24·isomeric graph23건이 일치했다. 1f는 CSV0.67µM vs DB3µM, 1m은 CSV3µM vs DB7.3µM로 추가 검토가 필요하다. 대조약 미수록은 수치 오류로 세지 않았다. 구조 차이도 tautomer·입체 표기·전사 등의 원인을 확인하기 전까지 오류로 단정하지 않는다.

## 보존 파일·검증

- 전체 재집계: `data/interim/main_cohort_inventory_20261020/`의 전수표·242개 검토 대기표·manifest.
- 787관측 대조: `data/interim/main_cohort_review_20261020/measurement_source_crosscheck.csv`와 manifest.
- 45건 후보·억제율4건 분리: `data/interim/furan_candidate_20261020/`와 manifest.
- 새 보류 등록부: [main_cohort_review.json](../configs/main_cohort_review.json). 기존 고정 `source_review_holds.json`과 함께 확인한다. 후속 코호트가 이 등록부의 보류를 무시하면 안 된다.
- [독립 검증 결과](main_cohort_acquisition_validation.json): 원문 응답57파일 SHA-256, 제공자 MD512파일, 입출력 해시·전수행수·중복 블록·구간값·후보 보류 상태·pIC50 재계산 통과. 기존 감사·코호트·최종 교육 실험 manifest 해시도 보존됐다.
- 전체 테스트47개 통과: 기존43개와 구간 중간값·부등호/오차·단일 농도 억제율·입체이성질체 그룹 검사의 신규4개. 로그는 `tmp/main_cohort_tests.log`에 있다.

재검증은 네트워크 없이 실행한다.

```bash
.venv/bin/python scripts/check_main_cohort_acquisition.py
```

## 다음에 해소할 근거

우선순위1은 2023년 후보의 ref28인2019년 실험법이다. 공개적으로 실제 접근 가능한 저자 원고나 정당하게 확보한 원문에서 EGFR 효소의 종·ATP·효소량·반응 조건을 확인해야 한다. 확보되면45개 IC50와 별개로4개 억제율을 유지하고, 반복 정의·단일 실험 맥락·최종 분할 가능성을 검토한다. 현재는 accession이나 공개 PDB의 인간 단백질이라는 사실만으로 그 효소가 human이라고 채우지 않는다.

우선순위2는 WT 특허64건의 화합물 구조 대조다. 원 G번호별 구조를 확인한 다음 약한 활성 영역에 제한된 별도 자료로서의 용도를 판단한다. 다른 조건의22건과 합쳐 라벨 폭만 넓히지 않는다. 둘 다 해결되지 않으면242개 대기표에서 다음 원문 접근 가능한 단일 assay를 검토한다. 확인된 원문이 없는 상태에서 최종 학습표·모델을 승인하지 않는다.

사용자가 직접 할 수 있는 일은 저자 CSV에서 `16`의 `0.1% @1uM`과 `15`의 `393nM`를 비교해 왜 같은 회귀 정답이 아닌지 설명하는 것이다. 또 `36`의25.3nM와 DB25nM를 확인하고, 원자료를 수정하는 대신 출처별 값을 함께 남기는 이유를 기록하면 된다. 권한이 필요한 원문은 임의 우회하지 않으며, 다른 사람에게 연락·전송하지 않았다.
