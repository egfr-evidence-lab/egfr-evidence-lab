# 논문 방법 적용과 재현 프로토콜

## 인용할 논문

1. **Yang et al., 2019. Analyzing Learned Molecular Representations for Property Prediction.** DOI: [10.1021/acs.jcim.9b00237](https://doi.org/10.1021/acs.jcim.9b00237). [저자 소속기관 공개 PDF](https://people.csail.mit.edu/tommi/papers/acs.jcim.9b00237.pdf). D-MPNN과 새로운 화학 구조 평가의 이론·실험 맥락을 학습합니다.
2. **Heid et al., 2024. Chemprop: A Machine Learning Package for Chemical Property Prediction.** DOI: [10.1021/acs.jcim.3c01250](https://doi.org/10.1021/acs.jcim.3c01250). [원문](https://pmc.ncbi.nlm.nih.gov/articles/PMC10777403/). 공개 코드·분할을 이용한 재현 대상을 고릅니다.
3. **Graff et al. Chemprop v2: An Efficient, Modular Machine Learning Package for Chemical Property Prediction.** DOI: [10.1021/acs.jcim.5c02332](https://doi.org/10.1021/acs.jcim.5c02332). 주 EGFR 실험에 사용할 v2 구현과 이전 구현의 차이를 이해합니다.

## 두 작업을 분리하기

| 작업 | 입력과 조건 | 정확한 표현 |
|---|---|---|
| EGFR 주 실험 | 우리가 선별한 ChEMBL EGFR 데이터, 고정한 분할·모델 | **논문 방법을 적용한 신규 실험** |
| 공개 벤치마크 | 원 논문의 공개 데이터·분할·저자 코드·설정 | **선택한 실험의 제한적 재현** |
| 데이터나 코드 조건을 변경한 비교 | 차이를 명시한 조건 | **변경 조건에서의 비교 실험** |

EGFR에서 D-MPNN 학습에 성공했다는 이유만으로 원 논문의 성능을 재현했다고 쓰지 않습니다.

## 구체적인 재현 후보

**Heid 2024의 SAMPL 물–옥탄올 분배계수 벤치마크**를 단일 재현 후보로 선택합니다. 저자 저장소는 `sampl` 벤치마크와 데이터 배포 위치를 안내하고, 벤치마크 실행 환경으로 Chemprop v1.6.1을 명시합니다. 이는 주 EGFR 데이터셋을 대체하는 작업이 아닌, 재현 능력을 보여줄 분리된 작은 연구 트랙입니다. 실제 계산량을 확인해 범위를 확정합니다. [저자 benchmark 저장소](https://github.com/chemprop/chemprop_benchmark)

SAMPL 원 데이터와 결과의 어떤 열·표를 비교할지는 원문 SI, 스크립트, 데이터 파일을 대조한 후 확정합니다. 아직 파일을 다운로드·검토·실행하지 않았으므로 정확한 목표 성능이나 성공 허용 오차를 만들지 않습니다.

## 실행 전에 채울 재현 기록

| 항목 | 현재 상태 |
|---|---|
| 대상 논문·benchmark | Heid 2024 / `sampl` 선택 |
| 원문·SI 표/행과 지표 정의 | 미확정: 실제 파일 대조 필요 |
| 저자 코드 commit, 환경 파일 해시 | 미확정: 실행 전 고정 |
| Chemprop 버전 | 저자 README의 v1.6.1 안내 확인; 실제 commit·환경 별도 확인 |
| 데이터 DOI·배포 버전·SHA-256 | 원 논문 데이터 공개 안내 확인; 다운로드 시 고정 |
| 입력 파일·train/validation/test ID | 미확정: 저자 공개 분할 확인 필요 |
| 모델·seed·튜닝 budget·early stopping | 미확정: 저자 설정 확인 필요 |
| 평가 대상·스케일·단위·집계 방식 | 미확정: 원문과 코드 대조 필요 |
| 비교 허용 범위 | 논문의 변동·실행 비결정성 검토 후, 실행 전에 정의 |
| 재현 결과 | **미실행** |

실행 후 원 결과·우리 결과·차이·일치하지 않은 조건을 표로 남깁니다. 튜닝 횟수를 줄였거나 데이터 일부만 사용했다면 그 범위를 명시하고 원 결과와 공정한 동일 조건 비교라고 주장하지 않습니다.

구버전 환경이 현 운영체제에서 설치되지 않으면 별도 컨테이너/환경을 검토합니다. 현재 코드로 임의 대체한 결과를 동일 재현으로 기록하지 않습니다.
