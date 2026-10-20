# EGFR Evidence Lab / 도메인과 기술 학습 노트

다음 단계: 전체 데이터 수집과 감사

2026.10.19 · 한국어 학습 자료 · P0 준비 편

> 학습 목표: 우리가 예측하려는 값이 무엇인지, 어떤 데이터를 함께 써도 되는지, 현재 코드가 무엇을 확인했는지를 자신의 말로 설명한다.

## 읽는 순서

| 쪽 | 내용 |
|---|---|
| 02-05 | EGFR, IC50, 실험 맥락, 변이와 신뢰도 |
| 06-08 | ChEMBL 구조, 실제 조회 결과, 분자 데이터 정제 |
| 09-11 | 현재 IT 스택, API 통신, 재현성과 검증 |
| 12-14 | 이후 기술의 역할, P0 준비, 문제와 해설 |
| 15-16 | 공식 출처와 다시 찾아볼 자료 |

## 현재 진행 상태

공식 API 확인과 소량 응답의 교차검증을 마쳤다. 전체 데이터 수집·정제·학습 코호트 확정·모델 학습은 아직 수행하지 않았다. 이 노트의 수치는 저장한 2026-10-19 API 응답 기준이다.

이 자료는 기존 도메인 학습 가이드를 보완한다. 이미 수행한 API 확인을 이해하고, 바로 다음 P0 작업을 판단하는 데 초점을 맞췄다.

<!-- page -->

# 01 / 무엇을 예측하는 프로젝트인가

## 유전자, 단백질, 화합물을 구분하기

**유전자**는 단백질을 만드는 정보와 관련되고, **단백질**은 세포에서 기능을 수행한다. EGFR은 유전자명으로도 쓰이며, 여기서 실험 표적은 그 유전자가 암호화하는 EGFR 단백질이다.

EGFR은 세포 표면의 수용체 티로신 키나아제다. EGF 같은 신호 물질을 받아 세포 분열·생존과 관련된 신호 전달에 관여한다. 저해제는 특정 실험에서 표적의 작용을 줄이는 화합물이다. [R01]

!flow 유전자 정보 | EGFR 단백질 | 억제 실험 | IC50 측정

## 입력, 정답, 예측의 관계

| 구분 | 이 프로젝트에서 뜻하는 것 |
|---|---|
| 입력 X | 화합물의 분자 구조를 컴퓨터가 처리할 수 있게 표현한 정보 |
| 정답 y | 적격한 IC50 측정값을 변환한 pIC50 |
| 예측 | 학습한 관계로 새 화합물의 pIC50를 추정한 값 |
| 근거 조회 | 실제 측정값과 관련 assay·변이·문헌을 찾아 보여주는 기능 |

**연구 질문:** 해석 가능한 하나의 EGFR 실험 집단에서 구조로 pIC50를 예측할 수 있는가? 처음 보는 분자 골격에서는 오차가 얼마나 달라지는가?

> 실험의 억제 활성을 잘 예측해도 환자 치료 효과, 체내 노출, 독성 또는 단백질 분해 효능이 확인된 것은 아니다. 먼저 예측 대상의 범위를 정확하게 말해야 한다.

출처: [R01] NCI EGFR 설명. 입력·평가 범위는 프로젝트 설계안.

<!-- page -->

# 02 / IC50와 pIC50 읽는 법

IC50는 정해진 실험에서 억제 효과가 50%에 해당하는 농도다. 억제하는 대상과 측정 방식이 무엇인지 함께 읽어야 한다. Ki는 억제 상수, Kd는 해리 상수다. 서로 다른 측정 개념이므로 IC50와 한 회귀 정답으로 합치지 않는다. [R02]

## 농도 단위와 로그 변환

- 1 M = 1 mol/L. nM은 M의 10억분의 1이다.
- 1 μM = 1,000 nM. 같은 농도라도 단위에 따라 숫자는 달라진다.
- pIC50 = -log10(IC50 [mol/L]).
- nM 단위라면 pIC50 = 9 - log10(IC50 [nM]).

| IC50 | mol/L로 표현 | pIC50 |
|---|---|---|
| 1 nM | 10^-9 M | 9 |
| 10 nM | 10^-8 M | 8 |
| 100 nM | 10^-7 M | 7 |
| 1 μM = 1,000 nM | 10^-6 M | 6 |

10 nM을 예로 들면 9 - log10(10) = 8이다. pIC50가 1 높아지면 IC50 농도는 10분의 1이다. **조건이 비교 가능할 때** 낮은 IC50와 높은 pIC50는 더 적은 농도에서 억제가 나타났다는 뜻이다.

## 숫자 앞의 기호도 데이터다

`>10,000 nM`은 정확히 10,000 nM라는 뜻이 아니다. 이 농도보다 큰 IC50라는 하한 정보이며 pIC50로는 5보다 작다는 방향이 된다. 현재 변환 함수는 부등호를 정확값으로 받아들이지 않는다.

pChEMBL은 여러 종류의 농도·친화도 측정을 음의 로그로 나타낸 필드다. IC50를 선별한 적격 기록에서 pIC50와 비교할 수 있지만, 모든 pChEMBL을 pIC50라고 부르면 안 된다. [R02]

출처: [R02] ChEMBL 측정·단위·pChEMBL 공식 설명. 변환 정책: src/egfr_lab/labels.py.

<!-- page -->

# 03 / 같은 IC50도 다른 실험이다

**Assay(실험)**는 무엇을 어떤 조건과 방식으로 측정했는지 나타내는 단위다. 표적 ID가 같고 측정 이름이 IC50라고 해서 같은 실험이 되는 것은 아니다.

## 실제 데이터에서 발견한 사례

동일 화합물 CHEMBL68920, 동일 논문 CHEMBL1134862에 다음 측정들이 함께 있다. 각 값은 저장한 ChEMBL 응답 기준이다.

| 측정 내용 | IC50 | 계산한 pIC50 |
|---|---|---|
| 단일 단백질 형식의 EGFR 인산화 억제 | 41 nM | 약 7.387 |
| A431 세포에서 EGFR 자가인산화 억제 | 300 nM | 약 6.523 |
| EGFR 발현 3T3 세포의 증식 억제 | 7,820 nM | 약 5.107 |

단백질 실험은 표적 기능에 가까운 반응을 보고, 세포 실험은 세포 안의 반응이나 증식을 본다. 서로 다른 결과를 무조건 평균내면 모델이 예측해야 하는 정답의 의미가 흐려진다.

## 실험 설명과 분류를 함께 읽기

| API 정보 | 읽는 방법 |
|---|---|
| assay_type | B는 Binding, F는 Functional이라는 실험 분류 |
| bao_format·bao_label | single protein format, cell-based format 같은 실험 형식 |
| description | 단백질·세포·인산화·증식 등 실제 측정 맥락을 확인 |
| assay_parameters | 제공되는 경우 조건 검토에 사용; 모든 조건이 채워진 것은 아님 |

> B 또는 F 하나만으로 학습 코호트를 확정하지 않는다. 구조화된 분류와 설명을 함께 보고, 모호한 것은 검토 대상으로 남긴다.

출처: 실제 기록 activity 32260·32263·32265, assay CHEMBL674637·CHEMBL621151·CHEMBL615325. [R02, R04]

<!-- page -->

# 04 / 변이, 정상형, confidence

## 변이 표기부터 정확히 읽기

L858R은 기준 단백질 서열의 858번 아미노산이 L(류신)에서 R(아르기닌)으로 바뀌었다는 뜻이다. L861Q도 같은 규칙이다. L858R,T790M처럼 여러 변이가 있으면 조합 전체를 보존한다.

ChEMBL은 정상형과 변이형에 같은 표적 ID를 사용할 수 있다. 그래서 CHEMBL203이라는 표적 ID만으로 정상형을 구분할 수 없다. [R03]

| 실제 확인 항목 | 결과와 의미 |
|---|---|
| CHEMBL387187의 L858R 실험 | IC50 63 nM |
| 같은 화합물의 L861Q 실험 | IC50 4 nM |
| 두 assay의 표적 | 모두 CHEMBL203 |
| 서열 대조 | UniProt 기준 서열과의 차이가 각각 변이 표기와 일치 |

API의 assay에는 variant_sequence 객체가 있고, activity에는 assay_variant_mutation 같은 요약 필드가 있다. **변이 주석이 null이면 정상형 후보를 검토할 수 있지만, 프로젝트에서는 설명과 근거가 불명확한 자료를 정상형으로 확정하지 않는다.**

## confidence는 무엇에 대한 신뢰도인가

confidence_score는 assay와 표적을 연결한 신뢰도다. 모든 실험 조건이 동일하다는 점수나 예측 정확도는 아니다. 9는 직접적인 단일 단백질 표적 연결, 8은 상동 단일 단백질 연결을 뜻한다. [R02]

실제 표본의 단백질 assay는 confidence 8·실험 종 null·관계 H였고, 세포 assay는 confidence 9였다. 표적 종이 인간이어도 실험에 사용한 단백질의 종이 확실하다고 단정할 수 없다. 표적 단백질 종과 실험 세포의 기원도 구분한다.

출처: [R02, R03, R04, R05]. 변이 표본 assay CHEMBL939338·CHEMBL939339.

<!-- page -->

# 05 / ChEMBL 데이터는 어떻게 연결되나

ChEMBL은 화합물·실험·활성 측정·문헌·표적을 연결한 데이터베이스다. API에서 보이는 각 측정 행은 화합물 자체와 구분되는 하나의 activity다. 같은 화합물에 여러 activity가 생길 수 있다.

!flow 화합물 구조 | 실험 assay | 측정 activity | 출처 document

이 그림은 읽는 순서다. 실제 연결은 activity의 분자·실험·문헌 ID와 assay의 표적·문헌 ID를 사용한다.

| 정보 | 식별자 또는 실제 필드 | 역할 |
|---|---|---|
| 측정 | activity_id | 개별 측정 기록을 추적 |
| 분자 | molecule_chembl_id | 분자 구조·이름·모체 관계 연결 |
| 실험 | assay_chembl_id | 실험 설명·형식·표적·변이 연결 |
| 문헌 | document_chembl_id | DOI·PMID·제목·연도 연결 |
| 표적 | target_chembl_id | 표적 유형·생물종·단백질 연결 |
| 단백질 | accession=P00533 | UniProt 기준 정보와 대조 |

## 원값과 표준값을 모두 보존하기

activity 32260의 원값은 value=0.041, units=uM이다. ChEMBL 표준값은 standard_value=41.0, standard_units=nM이다. 같은 농도를 다른 단위로 표현한 것이다.

원값은 추적·오류 검토에, 표준값은 일관된 분석에 필요하다. 둘 중 하나를 지워 버리면 단위 변환이 맞았는지 나중에 확인하기 어렵다.

우리 분석용 normalized_smiles·compound_group_id·variant_review_status·split은 ChEMBL이 그대로 제공하는 필드가 아니다. 앞으로 정책에 따라 생성하고 처리 이력을 남겨야 한다.

출처: [R04] 공식 API 사용법과 실제 activity 스키마. 로컬 제안 스키마: docs/01_blueprint.md.

<!-- page -->

# 06 / 이번에 확인한 데이터의 범위

API 버전은 ChEMBL_37, API 날짜 필드는 2026-05-01이었다. 고정 release notes의 준비 날짜와 전체 DB 건수가 일치했다. 공식 공지 게시일은 2026-05-29로 날짜의 의미가 다르다. 조회 전후 API status도 같았다. [R06]

## 인간 EGFR + IC50 조건의 API 집계

| 구분 | 측정 기록 수 | 해석 |
|---|---|---|
| 전체 | 26,600 | 정제 전 기록; 분자 수가 아님 |
| 정확값 관계 = | 19,719 | 학습 적격성은 아직 미확정 |
| 부등호 <, >, <=, >= | 5,471 | 정확값 회귀와 별도 처리 |
| 관계값 null | 1,398 | 수치 없는 Not active 사례 존재 |
| 근사 관계 ~ | 1 | 정확값과 구분 |
| 나머지 관계 미확인 | 11 | 전체 감사에서 종류 확인 예정 |

별도로 변이 문자열 non-null IC50 기록은 5,025건이다. 위 분류와 겹치므로 합산하지 않는다. 나머지를 자동으로 정상형이라고 부르지 않는다.

## 무엇을 교차검증했나

주 표본은 ID 오름차순 첫 10행으로 6분자·5실험·3문헌이다. 변이 2행을 추가해 총 12행의 상세 연결을 대조했다. 원 단위·표준 단위, pChEMBL, 분자·실험·문헌 연결, 변이 서열 등을 검사했다. 문헌 3편은 Europe PMC의 PMID·DOI·제목·연도와 일치했다. [R07]

> 표본 검사 12항목 통과는 전체 데이터 정제 완료를 의미하지 않는다. 전체 26,600행을 수집·검산하지 않았고 원 논문의 표에 적힌 측정 수치도 직접 대조하지 않았다. 모델 성능 교차검증을 수행한 것도 아니다.

출처: reports/chembl_api_verification.md, 공개 매니페스트·검증 JSON, [R06, R07].

<!-- page -->

# 07 / 분자 구조와 정제의 기본

## SMILES는 구조를 담은 문자열이다

SMILES는 원자·결합·고리·입체화학을 문자열로 표현한다. 예를 들어 CCO는 에탄올 구조를 나타낸다. 분자 이름이나 화합물 ID와는 다르다. 같은 구조가 다른 문자열로 적힐 수 있어 문자열 일치만으로 동일 분자를 판별하면 안 된다. [R08]

| 개념 | 쉬운 설명 | 앞으로의 처리 원칙 |
|---|---|---|
| 파싱 | 문자열을 분자 객체로 해석 | 실패한 구조를 기록하고 보류 |
| 염·혼합물 | 한 기록에 여러 성분이 있을 수 있음 | 모체 선택 정책을 정하고 원 구조 보존 |
| 입체화학 | 연결이 같아도 공간 배치가 다를 수 있음 | 의도 없이 입체이성질체를 합치지 않음 |
| 정규화 | 비교할 기준 구조를 일관되게 생성 | RDKit 버전과 처리 순서 기록 |
| 반복 측정 | 같은 분자를 여러 번 측정 | 같은 실험·변이 맥락인지 먼저 확인 |

## fingerprint와 scaffold를 구분하기

Morgan fingerprint는 분자 주변의 국소 구조 패턴을 수치화한 특징이다. 모델의 입력이나 유사도 계산에 사용할 수 있다. Scaffold는 분자의 핵심 골격을 기준으로 묶는 방법이며, 본 프로젝트에서는 평가 분할에 사용한다. 두 개념은 역할이 다르다. [R08]

학습과 테스트에 같은 분자가 들어가면 새 분자에 대한 성능을 과대평가할 수 있다. 비슷한 골격을 양쪽에 나누는 random 분할도 평가를 쉽게 만들 수 있다. 주 평가는 scaffold 그룹을 분리하고 random 분할은 비교용으로 둔다. [R09]

> 정제는 보기 좋은 표를 만드는 작업을 넘어, 모델이 어떤 분자·실험 집단에 대해 말할 수 있는지 정하는 일이다. 아직 RDKit 정제와 scaffold 계산은 실행하지 않았다.

출처: [R08] RDKit, [R09] Yang et al. 2019. 구체적인 정제·분할 정책은 프로젝트 설계안.

<!-- page -->

# 08 / 현재 실제로 사용한 IT 스택

현재 수집 전 탐색과 검증 코드는 **Python 표준 라이브러리**로 실행했다. httpx·pandas·RDKit·scikit-learn을 이미 사용해 전체 수집·학습한 상태가 아니다.

| 기술·모듈 | 쉬운 역할 | 이번 실제 사용 |
|---|---|---|
| Python 3.12.14·venv | 코드 실행기와 격리된 패키지 공간 | 프로젝트 .venv에서 탐색·검증 실행 |
| argparse | 터미널 입력 옵션 해석 | CLI와 --resume 경로 처리 |
| urllib.request·parse | HTTP 요청·URL 인코딩 | 공식 API 호출, 타임아웃 설정 |
| json | 구조화된 응답 읽기·쓰기 | 원 응답 해석, 매니페스트·검증 결과 |
| pathlib | 파일·폴더 경로 관리 | 원자료 저장·읽기 |
| hashlib·SHA-256 | 파일 내용의 요약값 계산 | 저장 응답의 변경 여부 검사 |
| datetime·timezone | 시간과 시간대 기록 | UTC 기준 조회 시각 저장 |
| ThreadPoolExecutor | 독립 요청을 제한해 병렬 실행 | 최대 3개 작업 스레드로 조회 |
| math·re·Counter | 수치 계산·패턴·집계 | 단위 비교, 메타데이터·표본 검사 |
| unittest | 코드 동작의 회귀 검사 | 기존 수치·정책 테스트 3개 통과 |
| Git·GitHub·VS Code | 변경 이력·원격 저장·편집 | 저장소와 실행·테스트 환경 관리 |

## 외부 데이터 서비스도 역할이 다르다

ChEMBL은 측정·실험·분자·문헌 연결의 주 자료원, UniProt은 단백질 기준 정보 대조, Europe PMC는 논문 메타데이터 대조에 사용했다. 이 셋의 결과를 합칠 때는 이름보다 식별자를 우선한다.

출처: 현재 scripts/probe_chembl_api.py·check_chembl_probe.py, [R04, R05, R07, R10-R13].

<!-- page -->

# 09 / API 통신과 페이지네이션

API는 프로그램이 서버에 정해진 형식으로 질문하고 응답을 받는 접점이다. HTTP GET은 자료 조회에 사용했고, HTTPS로 통신했다. JSON은 응답을 담는 형식이며 데이터베이스 자체나 모델은 아니다. [R04, R10]

!flow 조건을 URL로 | HTTP GET 요청 | JSON 응답 저장 | 연결·수치 검사

## 한 번의 조회를 나누어 읽기

| 요소 | 예시 | 의미 |
|---|---|---|
| 자원 경로 | /chembl/api/data/activity.json | activity를 JSON으로 조회 |
| 표적 조건 | target_chembl_id=CHEMBL203 | EGFR 표적 선택 |
| 측정 조건 | standard_type=IC50 | IC50만 선택 |
| 생물종 조건 | target_organism=Homo sapiens | 표적 종 조건; 실험 종과 구분 |
| 정렬 | order_by=activity_id | 페이지 조회 순서 명시 |
| 페이지 크기 | limit=5 | 응답에 최대 5행 요청 |

전체가 26,600행이어도 limit=5 요청은 5행과 페이지 정보를 돌려준다. page_meta.total_count는 서버가 집계한 전체 조건 일치 건수다. next는 다음 페이지 URL이며 실제 응답에서는 상대 경로였다. 호스트와 결합해 따라가야 한다.

## 실패해도 데이터가 조용히 빠지지 않게

현재 탐색 스크립트는 30초 타임아웃과 최대 3회 시도를 두고, 실패 기록을 남긴다. 일시 오류는 대기 후 재시도하지만 일반적인 4xx 오류는 반복하지 않는다. 429는 재시도 대상이다. 이는 현재 구현 정책이며 공식 최적값이 아니다.

전체 수집기에는 페이지 누락·ID 중복·재시작·버전 변경 점검을 더 갖춰야 한다. 이번 소량 탐색 도구를 완성된 전체 수집기로 설명하지 않는다.

출처: [R04, R10]. 현재 구현: scripts/probe_chembl_api.py.

<!-- page -->

# 10 / 재현성과 검증은 무엇이 다른가

## 매니페스트는 수집 기록표다

원 응답은 실제로 받은 내용이고, 매니페스트는 어디서 언제 어떤 조건으로 받았는지 적은 기록이다. 둘을 함께 보관해야 결과를 추적할 수 있다.

| 보관 정보 | 필요한 이유 |
|---|---|
| 요청 URL·조건 | 무엇을 선택했는지 복원 |
| release·조회 전후 status | 서로 다른 버전 자료의 혼합 감지 |
| UTC 조회 시각·HTTP 상태 | 언제 어떤 응답을 받았는지 추적 |
| 파일명·크기·SHA-256 | 보관 파일을 찾고 내용 변경 확인 |
| 재시도·오류 | 실패한 요청을 성공한 것처럼 처리하지 않기 |
| 실행 코드 해시·Python 버전 | 어떤 코드·환경에서 실행했는지 기록 |

SHA-256은 파일 바이트로 계산한 요약값이다. 내용이 바뀌었는지 확인하는 데 쓰지만, 자료가 과학적으로 옳거나 원 논문의 숫자와 일치한다는 보증은 아니다. [R11]

## 서로 다른 검증을 구분해서 말하기

| 검증 종류 | 이번 상태 |
|---|---|
| 코드 테스트 | 단위 변환·일부 정책에 대한 기존 테스트 3개 통과 |
| 소량 데이터 일관성 | 원 응답 37개와 표본 연결 등 12개 검사 항목 통과 |
| 전체 데이터 감사 | 미수행; 전체 분포·중복·누락을 앞으로 확인 |
| 모델 성능 평가 | 미수행; 학습·검증·테스트 분할부터 필요 |
| 원 논문 수치 재현 | 미수행; 원 데이터·환경·설정 대조가 별도로 필요 |

venv는 환경을 나누는 도구이고 lock은 재설치할 버전을 고정하는 기록이다. 가상환경이 있다는 사실만으로 전체 의존성 재현성이 확보되는 것은 아니다. Git에는 코드·설정·보고서를 두고, 비밀정보·가상환경·큰 원자료는 구분해 관리한다. [R12, R13]

출처: [R11-R13]. 현재 매니페스트와 검증 기록은 reports/chembl_api_probe_*.json.

<!-- page -->

# 11 / 이후 도입할 기술의 역할

다음 기술들은 **프로젝트의 도입 후보 또는 계획**이다. 이 노트를 만들었다고 설치·학습·배포가 완료된 것은 아니다. 전체 설치 호환성과 버전 고정은 아직 남아 있다.

| 단계 | 후보 기술 | 왜 필요한가 |
|---|---|---|
| P0 수집·표 처리 | httpx, pandas, pyarrow | 통신·테이블 감사·Parquet 저장 |
| P0/P1 분자 처리 | RDKit | 구조 파싱·정규화·Morgan fingerprint·scaffold |
| P1 기준 모델 | scikit-learn | 평균 예측 Dummy와 Random Forest 비교 |
| P1 통계 | NumPy, SciPy + 그룹 재표집 코드 | 오차·모델 차이·불확실성 계산 |
| P2 딥러닝 | Chemprop v2, PyTorch | 원자·결합 그래프를 이용한 D-MPNN 비교 |
| P3 검색·RAG | Europe PMC, BM25, LLM 호출 계층 | 문헌 검색과 근거를 인용한 설명 |
| P4 Agent | LangGraph | 결과에 따라 도구 선택·재검색·종료 |
| P5 서비스 | FastAPI, Docker, AWS | 추론 API·배포·모델 버전·로그 관리 |

## 가장 먼저 이해할 ML 평가 용어

Dummy는 학습 라벨 평균 같은 단순 기준이다. Random Forest는 여러 의사결정나무의 회귀 예측을 결합한다. D-MPNN은 방향성 결합을 따라 정보를 전달하며 분자 표현을 학습하는 신경망 방법이다. 복잡한 모델이 더 좋다는 결론은 실험 후에 내린다. [R09, R14, R15]

주 지표 MAE는 예측과 관측의 절대 오차 평균이다. 예측 7.5, 관측 8.0이면 해당 절대 오차는 0.5다. 보조 지표는 RMSE·Spearman이다. 테스트는 모델·튜닝 선택에 사용하지 않는다.

RAG는 검색한 근거를 바탕으로 답변하는 방식이고, Agent는 상황에 따라 도구를 선택하는 실행 방식이다. 둘 다 실제 측정값을 만들어 내는 근거가 될 수 없다. [R16]

출처: [R08, R09, R14-R16]. 기술 채택·단계 구분은 프로젝트 설계안.

<!-- page -->

# 12 / 다음 P0 작업을 이해하는 기준

## 먼저 정할 것은 데이터 선택의 근거다

코호트는 같은 분석 목적 아래 함께 다룰 자료 집단이다. 이 프로젝트의 첫 후보는 해석 가능한 단일 변이 상태의 생화학 실험이다. 정상형은 우선 후보지만, 표본 감사 전에 확정하지 않는다.

!flow 전체 자료 보존 | 실험·변이 감사 | 적격 코호트 | 모델 범위 결정

| 다음 작업 | 확인할 질문 | 남길 결과 |
|---|---|---|
| 환경 검증·버전 고정 | 설치·import가 실제로 되는가? | 버전 기록·lock 방식 |
| 전체 수집 | 모든 페이지·연결이 수집됐는가? | 원 응답·매니페스트·누락 기록 |
| 분포 감사 | 결측·단위·부등호·중복은 얼마나 있는가? | data_audit 보고서 |
| assay 검토 | 무엇을 어떤 변이·형식으로 측정했는가? | assay_review.csv |
| 구조 정제 | 같은 분자를 일관되게 구분했는가? | 처리 구조·그룹·제외 이유 |
| 코호트 제안 | 학습 질문과 자료가 맞는가? | dataset_card·선택 근거 |

## 아직 결론을 내리면 안 되는 것

- 26,600건을 확보했으니 모델 학습이 충분하다고 단정하지 않는다.
- 정확값 19,719건을 최종 학습 분자 수라고 부르지 않는다.
- 변이 필드가 비어 있는 자료를 전부 정상형으로 바꾸지 않는다.
- 같은 분자·다른 논문·다른 실험의 값을 자동 평균내지 않는다.
- API 원 응답을 저장했다는 이유만으로 누락·품질 검증을 끝내지 않는다.

Dataset card는 자료의 출처·버전·선정·제외·처리·적용 범위·한계를 설명하는 문서다. 다음 담당자가 같은 판단을 검토할 수 있어야 한다. 현재 미확인 관계값 11건도 전체 감사의 확인 대상이다.

출처: docs/01_blueprint.md와 HANDOFF.txt의 프로젝트 정책. 보편적 최소 표본 수나 확정된 모델 성과를 제시하지 않는다.

<!-- page -->

# 13 / 이해도 확인과 해설

먼저 답을 가리고 자신의 말로 설명해 본다. 이 문제들은 학습용이며 모델 평가 데이터가 아니다.

## 문제

- 1. 0.01 μM와 10 nM은 같은 농도인가? pIC50는 얼마인가?
- 2. >10,000 nM를 pIC50=5라는 정확값으로 넣어도 되는가?
- 3. CHEMBL203·IC50·confidence 9라면 생화학 정상형 코호트인가?
- 4. 26,600건 중 변이 주석이 없는 기록을 모두 정상형으로 불러도 되는가?
- 5. 같은 화합물의 41·300·7,820 nM을 평균내면 무엇이 문제인가?
- 6. JSON·API·SHA-256·venv는 각각 무엇을 담당하는가?
- 7. 소량 검사 12항목 통과와 모델 성능 검증은 같은 의미인가?
- 8. 다음 단계에서 코딩 외에 반드시 남겨야 할 문서는 무엇인가?

## 해설

1. 같다. 0.01 μM = 10 nM = 10^-8 M이므로 pIC50는 8이다.

2. 안 된다. pIC50가 5보다 작다는 한계 정보다. 현재 정확값 회귀에는 넣지 않고 원값·부등호를 보존한다.

3. 아니다. confidence는 표적 연결 신뢰도다. 실험 형식·설명·변이 근거를 별도로 확인해야 한다.

4. 안 된다. 미기재·해석 불명확을 정상형 확정으로 바꾸지 않는다. 검토 상태와 근거를 남긴다.

5. 단백질 억제·세포 내 반응·증식이라는 서로 다른 정답을 섞게 된다. 실험 맥락을 먼저 구분해야 한다.

6. JSON은 자료 형식, API는 프로그램의 자료 접근 접점, SHA-256은 파일 내용 요약값, venv는 Python 패키지 환경을 격리하는 도구다.

7. 다르다. 이번 검사는 소량 자료의 연결·수치 일관성 확인이다. 모델은 아직 학습하지 않았다.

8. 수집 매니페스트, assay 검토표, 정제·제외 기록, data_audit와 dataset_card다. 선택 근거가 재검토 가능해야 한다.

<!-- page -->

# 14 / 출처: 도메인과 실제 자료

확인 기준일: 2026-10-19. 링크는 클릭할 수 있다. 문서의 프로젝트 수치는 이 날짜에 저장한 원 응답을 기준으로 하며, 최신 API를 다시 호출하면 달라질 수 있다.

## 공식 설명과 데이터

[R01] [NCI - EGFR 용어 설명](https://www.cancer.gov/publications/dictionaries/cancer-terms/def/egfr). EGFR 단백질과 수용체 티로신 키나아제의 기본 역할.

[R02] [ChEMBL - Assay and Activity Questions](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/chembl-data-questions). 실험 분류·confidence·단위·pChEMBL·품질 플래그.

[R03] [ChEMBL - Target Questions](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/target-questions). 표적과 변이의 관계, 변이 주석 해석.

[R04] [ChEMBL 공식 API 사용법](https://chembl.gitbook.io/chembl-interface-documentation/web-services/chembl-data-web-services) / [activity 스키마](https://www.ebi.ac.uk/chembl/api/data/activity/schema.json) / [EGFR 표적](https://www.ebi.ac.uk/chembl/api/data/target/CHEMBL203.json). 조회·연결·페이지네이션·필터.

[R05] [UniProt P00533 원 응답](https://rest.uniprot.org/uniprotkb/P00533.json). EGFR 유전자명·생물종·기준 단백질 서열 대조.

[R06] [ChEMBL 상태 API](https://www.ebi.ac.uk/chembl/api/data/status.json) / [37 고정 release notes](https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/releases/chembl_37/chembl_37_release_notes.txt) / [공식 37 공지](https://chembl.blogspot.com/2026/05/chembl-37-is-here-bigger-cleaner-and.html). API 버전·날짜·전체 DB 건수의 대조.

[R07] [Europe PMC 문헌 메타데이터 조회](https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=%28EXT_ID%3A12127526%20OR%20EXT_ID%3A2552117%20OR%20EXT_ID%3A13678409%29%20AND%20SRC%3AMED&format=json&resultType=core&pageSize=3). 주 표본 문헌 3편의 식별자·제목·연도 확인.

## 프로젝트 내부 근거

reports/chembl_api_verification.md: 실제 조회·사례·한계를 정리한 보고서.

reports/chembl_api_probe_manifest.json 및 chembl_api_probe_validation.json: 요청·해시·수치·연결 검사 기록.

data/raw/api_probe_20261019T141453676518Z/: 보관 원 응답 37개. Git 제외 자료이므로 다른 컴퓨터에서 clone만 해서는 생기지 않는다.

<!-- page -->

# 15 / 출처: 기술과 다시 볼 코드

[R08] [RDKit 공식 Python 입문 문서](https://www.rdkit.org/docs/GettingStartedInPython.html). SMILES·분자 객체·fingerprint·구조 처리. 현재 도입 예정이며 정제는 미실행.

[R09] [Yang et al. 2019 - Analyzing Learned Molecular Representations for Property Prediction](https://pmc.ncbi.nlm.nih.gov/articles/PMC6727618/). D-MPNN과 분자 표현·평가 분할의 연구 맥락. DOI: 10.1021/acs.jcim.9b00237.

[R10] [Python 3.12 urllib.request](https://docs.python.org/3.12/library/urllib.request.html). HTTP 요청·타임아웃·응답 처리.

[R11] [Python 3.12 hashlib](https://docs.python.org/3.12/library/hashlib.html). SHA-256 등 해시 계산.

[R12] [Python 3.12 venv](https://docs.python.org/3.12/library/venv.html). 가상환경의 역할과 재생성.

[R13] [Git 공식 문서](https://git-scm.com/docs). 코드·설정·보고서 변경 이력 관리.

[R14] [scikit-learn 평가 지표 공식 문서](https://scikit-learn.org/stable/modules/model_evaluation.html). MAE·RMSE 등 모델 평가 지표. 실제 설치 버전은 이후 고정.

[R15] [Chemprop 공식 문서](https://chemprop.readthedocs.io/en/latest/). 분자 그래프 기반 예측 구현. 주 프로젝트는 v2 도입 계획이며 과거 논문 재현 환경은 분리.

[R16] [LangGraph 공식 Workflows and Agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents). 고정 workflow와 결과에 따른 도구 선택의 구분. 현재 미구현.

## 프로젝트에서 연결해 볼 코드

scripts/probe_chembl_api.py: 소량 API 조회, 원 응답·매니페스트, 제한된 재시도·병렬 요청.

scripts/check_chembl_probe.py: 저장 자료의 오프라인 해시·연결·수치·문헌 대조.

src/egfr_lab/labels.py 및 tests/test_contracts.py: 정확값 단위 변환과 일부 연구 정책 검사.

## 문서 제작과 검수

ReportLab으로 PDF를 생성하고 pypdf로 텍스트·링크를 확인한다. Poppler로 페이지를 이미지로 변환해 한글·표·줄바꿈·잘림·페이지 번호를 시각 검수한다. 이 도구들은 문서 제작용이며 EGFR 예측 모델의 학습 스택과 구분한다.
