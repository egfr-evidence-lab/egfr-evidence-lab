# 논문 방법 적용과 재현 프로토콜

## 인용할 논문

1. **Yang et al., 2019. Analyzing Learned Molecular Representations for Property Prediction.** DOI: [10.1021/acs.jcim.9b00237](https://doi.org/10.1021/acs.jcim.9b00237). [저자 소속기관 공개 PDF](https://people.csail.mit.edu/tommi/papers/acs.jcim.9b00237.pdf). D-MPNN과 새로운 화학 구조 평가의 이론·실험 맥락을 학습합니다.
2. **Heid et al., 2024. Chemprop: A Machine Learning Package for Chemical Property Prediction.** DOI: [10.1021/acs.jcim.3c01250](https://doi.org/10.1021/acs.jcim.3c01250). [원문](https://pmc.ncbi.nlm.nih.gov/articles/PMC10777403/). 공개 코드·분할을 이용한 재현 대상을 고릅니다.
3. **Graff et al. Chemprop v2: An Efficient, Modular Machine Learning Package for Chemical Property Prediction.** DOI: [10.1021/acs.jcim.5c02332](https://doi.org/10.1021/acs.jcim.5c02332). v2 구현과 이전 구현의 차이를 이해합니다. **2026-10-22 정정: 주 EGFR 실험(M2)에 v2를 쓸 계획이었으나 실제로는 v1.6.1을 썼습니다.** M3 재현이 저자 환경의 v1.6.1을 요구했고, 두 실험의 환경을 통일해 버전 차이가 결과에 섞이지 않게 했습니다. v2 실행은 남은 과제입니다.

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

2026-10-20에 저자 원 자료를 실제로 확보해 아래 표를 채웠습니다. 보존 경로와 해시는
`data/raw/benchmark_source_20261020/manifest.json`입니다. **아직 데이터 다운로드·환경 설치·학습은 하지 않았습니다.**

| 항목 | 확보한 값 (2026-10-20) |
|---|---|
| 대상 논문·benchmark | Heid 등 2024, JCIM, DOI [10.1021/acs.jcim.3c01250](https://doi.org/10.1021/acs.jcim.3c01250) / `sampl`(물–옥탄올 logP, SAMPL6·7·9 예측) |
| 원문·SI 표/행과 지표 정의 | SI `ci3c01250_si_001.pdf`(36쪽, CC BY-NC 4.0, 제공자 MD5 일치) 2.2.2절(p.16), 3.1.3절·**Table S9**(p.23). 지표는 RMSE(무차원 logP) |
| 저자 보고 결과 | Table S9 — SAMPL6 **0.27**, SAMPL7 **0.49**, SAMPL9 **1.11**. 같은 표의 제출작 평균 1.51/1.44/2.11, 최고 0.38/0.49/1.12. 랜덤 테스트셋 RMSE 0.53 |
| 저자 코드 commit, 환경 파일 해시 | `chemprop/chemprop_benchmark` main `247f3eee19ae66e05374bd6ef23ffd6d900ff213`(2024-01-30, MIT). `sampl.sh` SHA-256 `e91dc841…`, `environment.yml` SHA-256 `88b94e4e…` |
| Chemprop 버전 | v1.6.1 (master 태그). 저자 환경: python 3.7.6 / torch 1.7.1 / cudatoolkit 10.2 / numpy 1.18.1 / scikit-learn 0.22.2 / hyperopt 0.2.4 (Linux·NVIDIA) |
| 데이터 DOI·배포 버전·체크섬 | Zenodo record `10078142`(concept DOI 10.5281/zenodo.8174267), `data.tar.gz` **1,632,346,035바이트**, MD5 `57fef6993e9539ed8751a630c337e841`, CC BY 4.0 |
| 입력 파일·train/validation/test | `data/logP/`의 `train.csv`·`val.csv`·`test.csv`·`logP_without_overlap.csv`와 `sampl6/7/9_experimental.csv`. 학습 23,469점, 랜덤 80/10/10. SAMPL 분자는 학습셋에서 제거됨 |
| 모델·seed·튜닝 budget | hyperopt `--num_iters 30 --epochs 50`, 탐색 대상 depth·ffn_num_layers·hidden_size·ffn_hidden_size·dropout, `--aggregation norm`. 본 학습 `--epochs 50 --ensemble_size 5`, production `--epochs 40 --ensemble_size 5` |
| 평가 대상·집계 방식 | production 앙상블로 SAMPL6/7/9 실험값 대비 RMSE. 비교 컬럼은 `logP mean`(SAMPL6·7), `new_logPexp_reviewed`(SAMPL9) |
| 비교 허용 범위 | **정의하지 않음** — 축소 조건이므로 합격/불합격 기준을 두지 않고 차이를 그대로 보고한다 |
| 재현 결과 | **실행 완료 2026-10-21** (선택 C, 축소 조건). SAMPL6 **0.3666** / SAMPL7 **0.6843** / SAMPL9 **1.0530**, 저자 분할 테스트 RMSE **0.5636**·MAE 0.3350. 보고서 `reports/sampl_repro_20261021_v2/benchmark_repro_report_ko.md` |

### 실행 결과 (2026-10-21, 선택 C 축소 조건)

설정은 실행 전에 `configs/benchmark_repro_v2.json`으로 고정했고, 결과 JSON의 `config_sha256`과
현재 설정 파일 해시가 일치함을 확인했다(실행 후 설정 수정 없음).

| 세트 | n | 우리 RMSE | 95% 부트스트랩 구간 | 저자 보고 | 차이 | 저자값이 구간 안에 있는가 |
|---|---|---|---|---|---|---|
| SAMPL6 | 11 | 0.3666 | [0.2424, 0.4724] | 0.27 | +0.0966 | 예 |
| SAMPL7 | 22 | 0.6843 | [0.3945, 0.9495] | 0.49 | +0.1943 | 예 |
| SAMPL9 | 16 | 1.0530 | [0.7324, 1.3481] | 1.11 | −0.0570 | 예 |

| 2차 지표 | 값 |
|---|---|
| 저자 분할 테스트 RMSE / MAE | 0.5636 / 0.3350 (저자 보고 랜덤 테스트셋 0.53) |
| 최적 검증 RMSE | 0.5422 (epoch 43) |

**세 세트 모두 저자 보고값이 우리 결과의 95% 구간 안에 들어온다.** 평가 세트가 11·22·16개 분자에
불과해 축소 조건의 결과와 저자 결과를 구별할 수 없다. 어느 방향으로도 우열을 주장하지 않는다.

일치하지 않은 조건: 하이퍼파라미터 탐색 생략(저자 30회×50 epoch), 앙상블 5→1,
데이터로더 워커 8→0, 실행 환경(python 3.7.6/torch 1.7.1/CUDA → 3.12.14/2.5.1/CPU).
epoch 수(split 50 / production 40)와 데이터·분할은 저자와 동일하다. 저자 코드는 수정하지 않았다.

실행 중 **계산 완료 후 프로세스가 종료되지 않는 장애**가 발생해 약 2시간 정지했다. macOS `sample`로
네이티브 스택을 수집해 인터프리터 종료 처리 중 `os.waitpid` 블록임을 확정하고, 통제 비교
(전체 데이터 1 epoch: 워커 8 → 3분 34초·미종료 / 워커 0 → 29초·정상 종료)로 원인을 특정했다.
자세한 기록은 보고서 §6에 있다.

### 이 Mac에서의 실행 가능성 (확인 결과)

**저자 환경을 그대로 재현할 수 없습니다.** 저자 `environment.yml`은 python 3.7.6 + torch 1.7.1 + cudatoolkit 10.2(Linux/NVIDIA)인데,
이 기기는 macOS arm64(Apple Silicon, 8코어)이고 NVIDIA GPU가 없습니다. torch 1.7.1에는 Apple Silicon 빌드가 없습니다.

추가로, `sampl.sh`의 RMSE 계산은 `sklearn.metrics.mean_squared_error(..., squared=False)`를 사용하는데
이 인자는 scikit-learn 1.6에서 제거되었습니다. 현재 `.venv-ml`의 scikit-learn은 1.9.1이므로 해당 줄은 그대로 실행되지 않습니다.

따라서 아래 중 하나를 선택해야 하며, 어떤 선택이든 **원 논문과 동일 조건 재현이라고 쓰지 않습니다.**

| 선택지 | 내용 | 비용·위험 |
|---|---|---|
| A | 저자 코드(v1.6.1)·데이터·분할·설정은 그대로 두고 **환경만** 최신 python/torch CPU로 교체 | 설치는 현실적. 환경 차이를 반드시 명시 |
| B | linux/amd64 컨테이너로 원 환경 복원 | 에뮬레이션으로 매우 느림. 실질적으로 비현실적 |
| C | A에 더해 **튜닝 예산·앙상블 축소** | 가장 저렴. 축소 범위를 명시하고 공정 비교로 주장하지 않음 |

실행 후 원 결과·우리 결과·차이·일치하지 않은 조건을 표로 남깁니다. 튜닝 횟수를 줄였거나 데이터 일부만 사용했다면 그 범위를 명시하고 원 결과와 공정한 동일 조건 비교라고 주장하지 않습니다.

구버전 환경이 현 운영체제에서 설치되지 않으면 별도 컨테이너/환경을 검토합니다. 현재 코드로 임의 대체한 결과를 동일 재현으로 기록하지 않습니다.
