# 후속 원문 검토·실제 지표와 적용 범위

2026-10-20. 요청한 순서에 따라 **2019년 참조 실험법 탐색 → 대체 특허의 구조 연결 점검 → 자료·예정 분할·구조 거리 계산 → 승인과 적용 범위 판단**을 실행했다. 새 학습 승인0건이며 새 RF·D-MPNN은 학습하지 않았다. 아래 신규 수치는 데이터 적격성과 분할 진단 결과다. 모델 오차는 별도로 표시한 기존22건 교육 실험에만 있다.

## 1. 45건의 참조 실험법: 접근 상태와 새 근거

2023년 원문 Methods는 상세 효소 실험법을 Lin 등2019년 [DOI10.1021/acs.jmedchem.9b00722](https://doi.org/10.1021/acs.jmedchem.9b00722)로 연결한다. 이번에 Europe PMC·Crossref·OpenAlex의 공식 메타데이터를 추가 확인했다. Europe PMC는 해당2019년 논문을 subscription required·inPMC=N으로 표시했다. Crossref의 PDF 링크가 있다는 사실은 공개 본문 확보를 뜻하지 않는다. 이전 NHRI 링크는 권리 안내 HTML이었으며 실제 PDF로 세지 않았다.

OpenAlex는 별도 DOI를 OA 연결로 표시했지만, 실제로 따라간 [DOI10.7270/q21v5jfw](https://doi.org/10.7270/q21v5jfw)는 **BindingDB Entry50009645 데이터셋**이었다. [DataCite 공식 메타데이터](https://api.datacite.org/dois/10.7270/q21v5jfw)의 resourceTypeGeneral은 Dataset이며, ChEMBL·원 논문에서 파생됐다고 명시한다. 따라서 상세 방법 원문이나 독립된 실험 검증으로 사용하지 않았다. 이런 구분 없이 두 DB가 같은 값을 준다고 독립 검증으로 세면 출처가 순환한다.

2023년 본문에서 추가 확인한 핵심은 선별 과정이다. 10µM와1µM에서 먼저 억제율을 측정하고, 10µM에서 억제율>90%인 화합물을6점 농도반응 IC50로 평가했다. 저자 CSV49개에서 숫자 IC50 45건과 단일 농도 억제율4건을 구별했다. **45건은 이 연구의 합성·선별 과정을 거친 자료이며 임의의 전체 화합물 모집단을 대표하지 않는다.** [Li·Coumar 등2023 원문, Results and Discussion 및 Methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC9969398/).

현재 원문으로 확인된 것은 WT/변이 구별, GST-G696–G1022, Kinase-Glo Plus와 표 각주의 최소2회·±15%이다. 단백질의 human 종 유래와 상세 ATP·효소·기질·반응 조건은 아직 원문 확인 대기다. PubMed의 human 표적 색인이나 결정학 단백질을 해당 효소 실험의 직접 증거로 대신하지 않았다. `training_ready=false`를 유지했다.

## 2. WT 특허64건: 수치 일치 이후의 구조 점검

이전 검토에서 [US11155546B2 TestExample3/Table3](https://patents.google.com/patent/US11155546B2/en)의64관측은 단위·관계·수치가 맞았다. 이번에는 원 구조 그림15개를 보존·일부 시각 확인하고, G번호가 명시된 합성 표의 MS와 DB 구조의 계산 [M+H]+를 대조했다. 연속 합성 문단의 중간체 MS를 최종물에 자동 연결하지 않았다.

| 구조 점검 지표 | 실제 결과 |
|---|---:|
| 전체 관측 | 64 |
| record에 여러 원 G번호가 연결된 관측 | 5 |
| 명시적 원 G번호·합성표 MS로 점검 가능한 관측 | 35 |
| 원 MS와 연결된 DB 구조 계산값에 큰 차이가 있는 관측 | 13 / 35 |
| 그 차이에 해당하는 고유 원 G번호 | 10 |
| 차이의 범위 | 약14.0–30.0Da |
| 전체 구조 승인 | 0 |

0.25Da는 큰 차이를 찾기 위한 프로젝트 작업 기준이며 보편적인 질량분석 합격선이 아니다. [M+H]+ 비교는 중성·단일 성분에만 적용했다. 질량이 맞아도 위치이성질체·입체이성질체를 구별하지 못한다.

예를 들어 같은 DB 분자가 G-33/G-41로 연결되지만 원 표 MS는 각각499.2와513.2이며 DB 구조 계산값은 약513.242다. 원 그림의 해당 조각도 확인했으나 원 특허 자체의 분석값·그림·키 사이 관계를 추가로 해소해야 한다. G-7/G-51/G-54가 한 record로 묶인 사례도 있다. **이 결과는 구조·키 연결의 보류 근거이지 DB만 잘못됐다는 확정이나 올바른 대체 구조를 만들어도 된다는 근거가 아니다.** 현재64개 전체 구조를 독립적으로 검증했다고 표시하지 않았다.

최신 출력은 `data/interim/patent_structure_review_20261020_v2/structure_mass_review.csv`와 `source_masses.json`, manifest다. 기존 수치 대조표는 수정하지 않았다.

## 3. 실제 자료 지표

아래는 별개의 단일 문헌·assay 자료 세 개다. 합친 학습표가 아니다. 입체구조 자체는 보존하고, 분할 누출 점검에서는 입체 변형·동일 연결 구조를 같은 connectivity 그룹으로 묶었다. 특허는 정확값50건만 범위 진단에 사용하고 부등호14건은 제외했다.

| 지표 | 기존 교육22건 | furan45 후보 | 특허50 정확값 후보 |
|---|---:|---:|---:|
| 관측 / 고유 입체구조 | 22 / 22 | 45 / 45 | 50 / 48 |
| connectivity 그룹 | 22 | 43 | 47 |
| Murcko scaffold | 12 | 19 | 30 |
| 최대 scaffold 비율¹ | 50.0% | 39.5% | 19.1% |
| 집중도를 반영한 scaffold 다양성² | 3.67 | 5.39 | 14.83 |
| IC50 범위(nM) | 3.2–142.1 | 8–4,230 | 1,002–9,011 |
| pIC50 범위 폭 | 1.647 | 2.723 | 0.954 |
| pIC50 사분위 범위 | 0.626 | 0.912 | 0.512 |
| 독립 문헌 / assay | 1 / 1 | 1 / 1 | 1 / 1 |
| 주 학습 코호트 승인 | 미승인·교육 한정 | 미승인 | 미승인 |

¹중복 연결 구조를 제거한 connectivity 그룹 기준이다. 45건에서는 최대17/43그룹이다. ²각 scaffold 비율을 p라고 할 때 `1 / Σp²`인 inverse Simpson 지수다. 19개 골격이 있어도 빈도가 한쪽에 몰리면 균등한 약5.39개 골격 수준의 집중도를 보인다는 뜻이다. 독립 표본이5.39개라는 뜻이 아니다.

45건은22건보다 라벨 범위와 구조 수가 늘었지만 여전히 한 연구의 선별 계열이다. 특허는 골격 수가 더 많아도 라벨 폭이 약0.954log이고 구조 연결 문제도 남는다. 관측 수나 scaffold 수 하나만으로 데이터가 더 좋은지 결정하지 않았다. 원 저자45건의25.3·24.9nM와 DB25nM 두 차이는 보존했으며 정수 반올림 원인으로 확정하지 않았다.

## 4. 실제 예정 분할·구조 거리 진단

모델 성능을 보지 않고 [진단 설정](../configs/scope_diagnostics.json)을 먼저 고정했다. 주 진단은3-fold scaffold GroupKFold, 보조 진단은 connectivity 그룹을 seed42로 나누는 random3-fold다. 같은 연결 구조와 그 입체 변형은 어느 방식에서도 양쪽에 들어가지 않는다. 이 분할은 승인 전 진단용이며 최종 시험 세트가 아니다.

| 45건 후보의 지표 | scaffold3-fold | random connectivity3-fold |
|---|---:|---:|
| fold별 학습 / 평가 관측 | 28/17,31/14,31/14 | 30/15,30/15,30/15 |
| connectivity 중복 | 0 | 0 |
| 학습과 같은 scaffold를 가진 평가 관측³ | 0/45 | 32/45(71.1%) |
| 최근접 학습 분자 Tanimoto 중앙값³ | 0.803 | 0.845 |
| 최근접 유사도 범위³ | 0.381–0.986 | 0.381–0.986 |

³각 분자는 평가 역할을 한 번만 가지며, 그때의 학습 fold에서만 가장 가까운 분자를 찾았다. 분할별45개 값을 모아 계산했다. 유사도는 Morgan radius2·2048bit·입체정보 포함의 Tanimoto이며, 정확도80.3% 또는 성공 확률을 뜻하지 않는다. 임의의 유사도 합격선을 설정하지 않았다.

scaffold 분리에서 중복이0이어도 유사도가0.986인 분자가 존재했다. **서로 다른 Murcko 골격이라는 사실과 화학적으로 멀리 떨어져 있다는 사실은 같지 않다.** Yang 등은 산업·공개 자료 비교에서 scaffold 분할의 필요성을 보였지만, 이45건의 미래 성능이나 완전히 새 계열에 대한 적용을 보증한 연구는 아니다. 동일 데이터·분할에서 모델을 비교해야 한다는 방법론적 근거로 사용했다. [Yang 등2019, DOI10.1021/acs.jcim.9b00237](https://pmc.ncbi.nlm.nih.gov/articles/PMC6727618/).

학습28–31건·평가14–17건과 단일 문헌만으로 외부 연구·다른 화학 계열에 대한 독립 검증은 할 수 없다. 승인 후 학습곡선을 만든다면 fold 학습 부분에서 그룹별로 줄여 학습하고 같은 평가 분자를 유지해야 한다. 현재는 모델을 학습하지 않았으므로 학습곡선이나 신규 MAE를 제시하지 않았다.

## 5. 모델 성능으로 실제 제시할 수 있는 결과

아직 유일한 실제 모델 결과는 [기존22건 교육 실험](apsel_review_and_baseline_ko.md)이다. 사전 지정 seed42·scaffold3-fold에서 Dummy MAE0.3096, RF MAE0.2950, RF−Dummy=-0.0146이었다. 고정 OOF 예측의 scaffold 재표집 탐색95%구간은[-0.0819,+0.0506]으로0을 포함해 RF 우위를 확정하지 않았다. 이 조건부 구간은 학습 절차 전체나 미래 문헌의 불확실성을 포괄하지 않는다. 45건·특허50건의 성능으로 표시하면 안 된다.

데이터마다 라벨 폭이 다르므로 MAE가 작은 숫자라는 이유만으로 더 좋은 모델이라고 판단하지 않는다. 향후에는 같은 자료·분할의 Dummy 대비 paired 차이, 개별 큰 오차, seed 변동, 구조 거리와 함께 보고한다. MAE0.5나 R²0.8을 EGFR 보편 합격선으로 제시하지 않는다.

## 6. 근거에 맞는 적용 범위

| 구분 | 현재 판단 | 근거 |
|---|---|---|
| 현재 바로 가능한 것 | 출처·수치·구조·단위 대조, 선별 편향 분석, 분할·유사도 진단 | 실제 실행·입출력 해시와 검증 기록 |
| 45건의 방법 확인 후 가능한 첫 연구 | 같은 합성 계열·선별 히트·명시된 WT 효소 조건에서의 탐색적 IC50 회귀 | 단일 문헌·assay, 실제45건·19골격·작은 fold |
| 새 골격 일반화 주장 | 제한적. 골격 중복0만으로 화학적으로 먼 계열 성능을 주장하지 않음 | 실제 최근접 유사도0.986, 문헌별 외부 평가 없음 |
| 다른 ATP·반응 시간·검출법으로 이전 | 추가 비교 실험·호환성 근거 필요 | 조건 미확정, 시간 의존 endpoint·ATP 영향 고려 |
| 변이·세포·임상 결과 | WT 생화학 IC50만으로 검증되지 않음 | 라벨과 실험 맥락이 다름 |

공유결합 억제제에서 endpoint IC50는 반응 시간·사전 반응 설계와 연결된다. Mader·Keillor는 시간 의존 pre-incubation IC50 자료에서 kinact와KI를 추정하는 방법을 연구했다. 이 논문은 시간 정보를 버리지 말아야 할 근거이며 우리 EGFR 데이터에 특정 보정값이나 합격선을 제공한 것은 아니다. [Mader·Keillor2024, DOI10.1021/acsmedchemlett.4c00054](https://pmc.ncbi.nlm.nih.gov/articles/PMC11089659/).

2023년 원 연구는 변이 EGFR 억제와 WT 억제 감소를 함께 고려한 후보 최적화다. 따라서 WT IC50가 낮다는 것만으로 더 좋은 치료 후보라고 해석할 수 없다. WT 회귀 결과를 변이 선택성·세포CC50·안전성·환자 치료 효과와 구분한다. [Li·Coumar 등2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC9969398/).

## 검증·보존·다음 판단

- 원문 응답23파일 해시와 원 구조 PNG 형식, 원 MS 연결·35관측의 검사 범위·13경보를 확인했다.
- 3자료·18개 예정 fold·최근접 분자234행을 생성했다. 45건 후보의 최근접 유사도90개(분할2개)를 별도 계산으로 재검증했다. 모든 connectivity 중복0, 주 scaffold 중복0이다.
- 전체52개 테스트 통과. 새5개는 로그 농도·편중 지수·입체/반복 그룹 누출·중간체MS 오연결·동질량 이성질체를 검사한다. 로그: `tmp/cohort_scope_tests.log`.
- [독립 검증](cohort_scope_validation.json), `data/interim/cohort_scope_diagnostics_20261020/`, 최신 보류 판단 [cohort_scope_review.json](../configs/cohort_scope_review.json)에 기록했다. 기존 원문·검토표·모델은 덮어쓰지 않았다.

다음 승인 관문은45건의 실제 참조 방법 원문 또는 이를 명시적으로 대신할 수 있는 일차 자료에서 효소 human 유래와 조건을 확인하는 것이다. 특허 후보는 MS·그림·키의 차이를 해소할 자료와 독립 구조 검토가 필요하다. 현재 근거로는 주 코호트 미확정을 유지하고, 다른 조건의 자료를 합쳐 건수나 라벨 폭을 늘리지 않는다. 사용자 실습은45건의32/45 골격 중복·0.803 유사도가 각각 무엇을 뜻하는지 자신의 말로 설명하고, G-33/G-41의 원 분석값 차이를 검토 기록에 남기는 것이다.

## 7. furan45: PDB 교차확인과 Coumar 2010 SI 점검 (2026-10-20 후속)

ref28(Lin 등 2019) 본문 자체는 이번에도 확보하지 못했다. Europe PMC는 여전히 subscription required·inEPMC=N이며, OpenAlex의 OA 연결은 BindingDB 데이터셋으로 순환 출처다. NHRI 기관 레포지토리 링크(이전 세션에서 권리안내 HTML로 확인)를 다시 시도하지 않았고, National Yang Ming Chiao Tung University 레포지토리(Coumar 2010 소장)는 이번 접근에서 502 오류였다. ACS 유료 본문에 대한 우회 접근은 시도하지 않았다.

대신 본문과 **독립된 두 공개 1차 자료**를 교차확인했다.

**PDB 6JZ0.** citation의 DOI·PMID가 ref28과 정확히 일치하고 struct.title이 "화합물78(=DBPR112)과 EGFR kinase domain의 공동결정구조"로 SI Table S1과 맞는다. RCSB 공식 레코드에서: 종 Homo sapiens(taxid9606, UniProt P00533), 구성체 구간696–1021, 발현 호스트 Spodoptera frugiperda/High Five 곤충세포, 서열상858=Leu·790=Thr로 변이 카운트 필드 전부0(WT). 이 696–1021 구간은 2023년 furan45 논문이 쓴 GST-G696–G1022 구성체와 한 잔기 차이로 거의 일치한다. **다만 이것은 결정학용 단백질 준비 구성체의 확인이며, 효소 활성(IC50) 분석 자체의 반응 조건과 동일하다는 직접 증거는 아니다.** 같은 연구팀의 같은 계열 구성체라는 정황 근거로만 쓴다.

**Coumar 등 2010 SI(Lin2019의 cit28, 화합물2의 전신 문헌, DOI10.1021/jm1000198).** ACS SI(figshare 공식 호스팅, jm1000198_si_001.pdf, 제공자 MD5 일치 확인)를 12쪽 전체 직접 열람했다. 내용은 화학 합성 원료 차트, 세포실험 그림(유세포분석·웨스턴블롯), X선 공동결정 표, HPLC 순도 조건뿐이며 **kinase 효소 분석(ATP 농도·효소량·반응시간·온도·readout) 프로토콜은 없다.** 이 연구팀의 J Med Chem 논문들은 효소 분석법을 SI가 아니라 본문 Experimental Section에만 기술하는 것으로 보인다.

Lin2019 본문의 참고문헌53번이 "Reaction Biology Corporation Home Page"(상업 kinase assay CRO)인 것은 확인했지만, **이 연구가 실제로 이 CRO를 썼다는 본문 서술 자체는 확인하지 못했다.** Reaction Biology의 공개 EGFR 패널 프로토콜(ATP10µM·poly(Glu:Tyr)4:1 기질)은 참고용 정황일 뿐 이 논문의 실제 조건으로 쓰지 않는다.

**결론:** `configs/cohort_scope_review.json`의 furan45 항목에 `pdb_6JZ0_cross_check`와 `coumar2010_si_checked`를 추가했다. `protocol_fields_still_pending`(ATP농도·효소농도·기질조건·반응시간온도·readout)은 그대로 남아 있고, `training_ready=false`를 유지한다. 새 증거는 `data/raw/scope_evidence_20261020_v3/manifest.json`에 해시와 함께 기록했다. 기존 v2 파일·검토표는 변경하지 않았다.

## 8. 본문 접근 차단 사유 — 인용·경로 기록 (2026-10-20 재검증)

ref28(Lin 등 2019) 본문이 막히는 정확한 지점을 재요청해서 확인했고, 각 경로의 응답을 `data/raw/scope_evidence_20261020_v3/manifest.json`의 `access_blocked_log`에 해시와 함께 저장했다.

1. **ACS 출판사 원문.** `https://doi.org/10.1021/acs.jmedchem.9b00722` → `https://pubs.acs.org/jmcmar/article/62/22/10108/...` 로 리졸브되며 **HTTP 403**. 구독 안내 화면에도 도달하지 못하고 자동화 요청 자체가 거부된다. (`data/raw/scope_evidence_20261020_v3/acs_doi_resolve_403.html`)
2. **Europe PMC 공식 메타데이터.** `isOpenAccess=N`, `inEPMC=N`, `inPMC=N`, `hasPDF=N`, `fullTextUrlList.availability="Subscription required"`. 출판사가 이 논문을 구독 전용으로 공식 등록했다는 근거다. (`data/raw/scope_evidence_20261020_v2/ref28_epmc.json`)
3. **NHRI(National Health Research Institutes) 기관 레포지토리.** `https://ir.nhri.edu.tw/bitstream/3990099045/12290/1/NBP2019112001.pdf` 는 HTTP 200이지만 실제로는 472바이트 HTML이며, 인용하면: *"According to right of reproduction and fair use of copyright, the fulltext is only for index and search purpose... The page is going to be redirected to a external link, the original archiving system."* 즉 레포지토리가 전문을 보유하지 않고 원본(ACS)으로 안내만 한다. (`data/raw/scope_evidence_20261020_v3/nhri_bitstream_rights_notice.html`)
4. **OpenAlex OA 인덱스.** `open_access.oa_url`이 `https://doi.org/10.7270/q21v5jfw`를 가리키지만 실제로는 BindingDB Entry50009645 데이터셋(DataCite가 ChEMBL·원 논문 파생임을 명시)이다. 논문 본문이 아닌 2차 파생 데이터셋이라 순환 출처로 판단, 독립 검증으로 세지 않는다. (`data/raw/scope_evidence_20261020_v2/ref28_openalex.json`)

**결론: 차단은 저작권자(ACS)의 구독 정책에 의한 것이며, 레포지토리·인덱스 쪽에 우회 가능한 합법 사본이 존재하지 않는다.** ACS 구독 접근 우회는 시도하지 않았다(HANDOFF.txt 10번 항목 원칙 준수).

## 9. furan45 없이 프로젝트 진행이 가능한가

**가능하다.** `configs/project.json`의 `training_cohort`는 `pending_manual_assay_review_after_automatic_audit`로, 특정 후보(furan45)에 고정 의존하지 않는다. M1의 목표는 "실험 맥락이 명시된 단일 프로토콜 WT 생화학 IC50 코호트 1개 확보"이며, furan45는 그중 하나의 후보일 뿐이다. 현재 검토 중인 다른 후보들(특허64건 CHEMBL5737421 - 수치 일치, 구조검증 보류 / Apsel209건 - 전부 보류 / 981건 - assay 전체 보류)도 furan45와 독립적으로 존재한다. P0 수집·자동감사, 코드(`data/audit.py`, `data/collection.py` 등), 테스트 52개는 furan45를 전제하지 않고 이미 동작한다. 즉 **furan45가 막혀도 프로젝트 자체(P0/P1 파이프라인, M1 코호트 선정 절차)는 다른 후보로 계속 진행할 수 있다** — 막힌 것은 "45건이라는 특정 후보"이지 "프로젝트의 다음 단계" 자체가 아니다.

## 10. 본문 확보 가능한 대체 후보 5개

`data/interim/main_cohort_inventory_20261020/source_priority_queue.csv`(242 assay 큐) 전체를 다시 스캔했다. PMID가 있는 고유 문헌 134건의 Europe PMC OA 상태를 전수 재조회한 결과 `isOpenAccess=Y`는 **4건뿐**이었고, 그중 1건(PMID36749735)은 furan45 자신의 2023년 논문(이미 사용 중)이었다. 특허(PATENT) 79건은 전문이 항상 공개이지만 79건 중 78건이 `variant_unresolved`(WT/변이 혼합 표라 자동 분리 실패) 플래그를 갖고 있어, "접근 자체는 막히지 않았지만 수작업 분리가 필요한" 범주다. 실제 WT·bio 우선순위이면서 다른 중대 보류사유가 없는 신규 후보는 없었다 — 즉 **대부분의 접근 가능 후보가 "접근 문제가 아닌 다른 이유"로 아직 보류 상태**다.

이를 반영해, 접근성 기준으로 가장 현실적인 5개를 제시한다(모두 **아직 검토·승인 전**, training_ready 아님):

| # | 후보 | 접근 경로 | 규모 | 남은 과제 (접근 문제 아님) |
|---|---|---|---|---|
| 1 | CHEMBL5735051 (특허 "2,4-disubstituted pyrimidines useful as kinase inhibitors", doc CHEMBL5727636) | 특허 전문 공개(Google Patents) | 262행 중 정확값159 | Omnia Assay가 EGFR-WT(Invitrogen PV3872)와 EGFR-T790M/L858R(BPS 40350)을 같은 표에 병기 — WT행만 수작업 분리 필요. 구조 확인(struct_hold 260)도 필요 |
| 2 | CHEMBL5738142 (동일 특허군, doc CHEMBL5729139) | 특허 전문 공개 | 262행 중 정확값139 | 위와 동일한 Omnia Assay WT/변이 분리 과제 |
| 3 | CHEMBL5736750 (특허 "EGFR proteolysis targeting chimeric molecules", doc CHEMBL5728438) | 특허 전문 공개 | 187행 중 정확값153 | PROTAC(분해제) 계열이라 통상 IC50 회귀와 작용기전이 다름 — pool_ic50_ki_kd 정책과 별도 검토 필요 |
| 4 | PMID18849971 / CHEMBL1240340 ("Targeted polypharmacology: discovery of dual inhibitors...") | PMC 공식 오픈액세스 전문 | 167행, struct_hold 1(낮음) | 이미 known_source_hold=True로 등록(`target_link`·`variant_unresolved`) — 이중표적(dual) 설계라 EGFR 단일표적 WT로 보기 어려움 |
| 5 | PMID35838760 / CHEMBL5137066 (BLU-945 관련 논문) | PMC 공식 오픈액세스 전문 | 24행 | `format_not_biochemical` 플래그 — 세포 기반 형식일 가능성, struct_hold 26으로 구조도 대부분 미확인 |

**주의:** 이 5개는 "본문을 읽을 수 있다"는 조건만 만족한 것이며, 어느 것도 furan45보다 검증이 더 진행된 상태는 아니다. 1·2·3번은 본문이 100% 공개라 WT/변이 행 분리 작업만 하면 되는 반면(접근 문제 없음), 4·5번은 공개 논문이지만 기존 자동 검토에서 이미 다른 사유로 보류돼 있다. 어느 것이든 `configs/cohort_policy.json`의 `cross_assay_pooling_requires` 기준 전체를 통과해야 학습 승인된다.
