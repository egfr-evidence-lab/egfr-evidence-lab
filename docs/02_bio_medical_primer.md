# 바이오·메디컬 학습 가이드

목표는 **내가 예측하는 실험값이 무엇인지 설명하고 데이터 오류를 판별하는 것**입니다. 임상 의사결정이나 환자 치료 효과를 예측하는 프로젝트로 해석하지 않습니다.

## 1단계 — 표적과 분자를 이해하기

| 개념 | 이해할 내용 | 프로젝트에서 해볼 일 |
|---|---|---|
| 유전자·단백질 | 유전자와 그 산물인 단백질을 구분 | EGFR 유전자 변이가 단백질 정보에 어떻게 반영되는지 설명 |
| EGFR | 세포 신호와 관련된 수용체 티로신 키나아제 | 표적 단백질 활성과 세포 성장 억제를 구분 |
| 저분자·저해제 | 분자가 표적의 작용을 억제하는 실험 맥락 | 화합물 ID와 이름을 혼동하지 않고 구조 확인 |
| SMILES | 원자·결합·고리·입체화학을 문자열로 표현 | RDKit으로 구조 그림을 만들고 파싱 실패 확인 |
| fingerprint·scaffold | 국소 구조를 수치화한 표현과 분자의 핵심 골격 | 유사도 검색과 분할이 서로 다른 목적임을 설명 |
| SAR | 구조 변화와 활성 변화 사이의 관계 | 유사한 두 분자의 실험 맥락과 활성 차이를 비교 |

EGFR의 역할과 분류는 [NCI EGFR 사전](https://www.cancer.gov/publications/dictionaries/cancer-terms/def/egfr), 분자 표현·fingerprint 구현은 [RDKit 공식 입문 문서](https://www.rdkit.org/docs/GettingStartedInPython.html)에서 확인합니다. fingerprint 중요도를 인과적인 작용기전 증거로 해석하지 않습니다.

## 2단계 — 정답값과 실험을 이해하기

IC50는 정의한 실험 반응의 50% 억제에 해당하는 농도입니다. 효소·기질/ATP 조건, 시간과 실험 방식 등에 영향을 받을 수 있습니다. 서로 다른 실험의 숫자가 같아도 같은 생물학적 의미라고 단정하지 않습니다. [Assay Guidance Manual: 효소 실험](https://www.ncbi.nlm.nih.gov/books/NBK92007/), [키나아제 실험](https://www.ncbi.nlm.nih.gov/books/NBK91991/)

**변환식**

```text
pIC50 = -log10(IC50 [mol/L])
IC50가 nM이면 pIC50 = 9 - log10(IC50 [nM])
```

| IC50 | pIC50 |
|---|---|
| 1 nM | 9 |
| 10 nM | 8 |
| 100 nM | 7 |
| 1 µM = 1000 nM | 6 |

조건이 비교 가능하다면 낮은 IC50/높은 pIC50가 더 강한 억제에 해당합니다. pIC50 차이 1은 IC50 농도 10배 차이입니다. 높은 값이 좋은 약, 낮은 독성, 좋은 체내 노출을 의미하지는 않습니다.

| 값 | 구분할 점 |
|---|---|
| IC50 | 해당 실험의 억제 농도. 실험 조건과 엔드포인트 확인 |
| Ki·Kd | 억제 상수·해리 상수. IC50와 동일한 숫자로 취급하지 않음 |
| pChEMBL | 여러 농도·친화도 종류의 음의 로그 표현. IC50만 있다는 뜻이 아님 |
| `>10000 nM` | 정확히 10000이라는 뜻이 아닌 한계값/검열 관측 |
| 세포 생존·증식 IC50 | 분리된 EGFR 단백질에 대한 IC50와 구분 |

ChEMBL의 pChEMBL 정의·유효성 표시는 [공식 활성 설명](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/chembl-data-questions), IC50와 Ki의 실험적 차이는 [Assay Guidance Manual](https://www.ncbi.nlm.nih.gov/books/NBK91993/)을 참고합니다. 위 프로젝트의 실제 회귀 라벨은 IC50만 선별한 pIC50입니다.

## 3단계 — 변이·내성과 회사 연구를 연결하기

L858R은 단백질 858번 위치의 아미노산 L이 R로 치환되었다는 표기입니다. T790M·C797S도 같은 규칙으로 읽습니다. **복합 변이는 각각의 이름을 모두 보존**하고, 변이가 있다고 전부 약물 내성 변이라고 부르지 않습니다.

C797S가 특정 EGFR 억제제 AZD9291에 대한 획득 내성과 연결된다는 근거를 읽을 예시는 Thress et al.의 원 연구입니다. 해당 조건의 근거이며 모든 약물·환자에 대한 일반화가 아닙니다. [Thress et al., Nature Medicine 2015, DOI:10.1038/nm.3854](https://pubmed.ncbi.nlm.nih.gov/25939061/)

ChEMBL의 변이 식별자는 학습 코호트 구분에 사용합니다. 메타데이터·assay 설명·원 논문이 충돌하면 보류하고 근거를 기록합니다. [공식 변이 설명](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/target-questions)

| 회사 분야 용어 | 알아둘 구분 |
|---|---|
| ADC | 항체에 약물을 연결하는 접근. 항체·링커·페이로드 특성을 함께 고려 |
| TPD·PROTAC | 표적 단백질의 분해를 유도하는 접근. PROTAC은 TPD의 한 방식 |
| DC50·Dmax | 분해 능력 평가 지표. IC50만으로 대체하지 않음 |
| PK·ADME·독성 | 체내 거동·노출·안전성 문제. 표적 억제 실험과 별도 |

ADC 정의: [NCI](https://www.cancer.gov/publications/dictionaries/cancer-terms/def/antibody-drug-conjugate). 분해·결합·세포 활성의 구분: [PROTAC-DB 공식 설명](https://cadd.zju.edu.cn/protacdb/about). ADME 예측 과제: [TDC](https://tdcommons.ai/single_pred_tasks/adme/).

## 학습 완료를 확인할 질문

1. `10 µM`, `10000 nM`, `>10000 nM` 중 같은 정확값으로 변환할 수 있는 것은?
2. 같은 EGFR 표적 ID를 가진 두 행이 같은 변이를 의미하는가?
3. 정상형 단백질 실험과 변이 세포 증식 실험을 합치면 무엇을 예측하게 되는가?
4. pIC50 예측이 높으면 왜 환자에게 효과가 있다고 결론 내릴 수 없는가?
5. `confidence=9`만으로 실험 조건이 같다고 볼 수 있는가?
6. EGFR 억제 활성을 예측한 모델을 TPD 효능 모델이라고 부를 수 있는가?

순서는 1단계와 단위 변환 → 실험·변이 감사 → 구조와 활성 분석 → 회사 분야의 확장 개념을 권장합니다. 이는 프로젝트 학습 순서 제안이며 의학 교육의 전체 범위가 아닙니다.
