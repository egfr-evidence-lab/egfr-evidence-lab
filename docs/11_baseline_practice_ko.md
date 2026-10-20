# 직접 해보는 EGFR 데이터·기준 모델 실습

이번 목표는 숫자를 외우는 것이 아니라 **원 관측 → 학습 범위 판단 → 평균 예측 → 분자 구조 예측 → 오차 해석**을 직접 설명하는 것입니다. 현재 결과는22건 교육·탐색 실험이고 209건 논문 자료는 보류 상태입니다. [결과·근거](../reports/apsel_review_and_baseline_ko.md).

## 시작 — 터미널 위치와 환경

아래 한 줄로 프로젝트 폴더로 이동합니다. 경로의 공백 때문에 따옴표를 유지합니다.

```bash
cd '/Users/kyungduck/Documents/ChatGPT/사이드 프로젝트/egfr-evidence-lab'
```

활성화 명령 없이 `.venv-ml/bin/python`을 직접 사용합니다. 현재 Mac에는 필요한 패키지를 설치했습니다. 다른 컴퓨터에서 재구성할 경우 Python3.12 환경을 만들고 `requirements/ml-py312-macos-arm64.freeze.txt`를 설치해야 합니다. 이는 현재 Mac 버전 스냅샷이며 모든 플랫폼에서 확인한 lock이 아닙니다.

## 1. 단위 변환 — 5분

먼저 종이나 메모에 답을 적습니다.

1. 10 nM, 100 nM의 pIC50는?
2. PP20의0.17 µM는 몇 nM인가?
3. `>50 µM`를 pIC50로 표현하면 부등호 방향은?

```bash
.venv-ml/bin/python scripts/practice_basics.py --lesson units
```

확인: 각각8, 7, 170 nM. `>50 µM`이면 pIC50<4.30103입니다. 농도가 커질수록 음의 로그는 작아집니다. 정확한 값4.30103으로 학습하면 관측의 의미를 바꿉니다.

## 2. 논문 표 대조 — 10분

[저자 공개 PDF](https://shokatlab.ucsf.edu/pdfs/18849971.pdf)의 세 번째 페이지, 인쇄 쪽수693의 Figure2a를 엽니다. 아래 표를 직접 채웁니다.

| 항목 | 직접 적을 답 |
|---|---|
| 보고 있는 행 이름 | |
| 표 전체 단위 | |
| PP20 값·관계 기호 | |
| PP121 값·관계 기호 | |
| PIK-294 값·관계 기호 | |
| ATP 농도를 확인한 위치 | |

```bash
.venv-ml/bin/python scripts/practice_basics.py --lesson review
```

해설: EGFR 행, µM, PP20=0.17, PP121=0.26, PIK-294>50. Figure2 설명은 ATP10 µM입니다. 옆의 다른 kinase 행이나 세포 지표를 같은 라벨로 읽지 않습니다. 본문8건의 일치가 미확인 SI·WT·유래까지 보증하는 것은 아닙니다.

## 3. Dummy의 평균 예측 확인 — 10분

[fold_metrics.csv](../reports/baseline_pilot_20261020_v2/fold_metrics.csv)에서 `scheme=scaffold`, `fold=1`, `seed=42`, `model=Dummy`를 찾습니다. CSV는 VS Code의 텍스트로 읽어도 됩니다.

- 학습 분자 수와 평가 분자 수를 적습니다.
- `train_mean_pIC50`를 적습니다.
- [predictions.csv](../reports/baseline_pilot_20261020_v2/predictions.csv)에서 같은 fold의 Dummy 예측이 모두 그 평균인지 확인합니다.

확인: 학습11·평가11, 평균 약7.839393입니다. **평가 라벨까지 포함한 전체 평균을 쓰면 정보 누출**입니다. Dummy는 SMILES를 보고 화합물을 구별한 모델이 아닙니다.

## 4. 오차와 분할 읽기 — 10분

```bash
.venv-ml/bin/python scripts/practice_basics.py --lesson predictions
```

직접 적을 내용:

- scaffold에서 Dummy와 RF의 MAE 차이는 얼마인가?
- random으로 나누면 RF MAE가 어떻게 변하는가?
- [paired_comparison.csv](../reports/baseline_pilot_20261020_v2/paired_comparison.csv)의 scaffold·seed42 구간에0이 포함되는가?
- 평균 MAE 약0.295인데 화합물2의 개별 오차가 약0.847일 수 있는 이유는?

해설: RF−Dummy≈−0.0146, 구간[−0.0819,+0.0506]은0을 포함합니다. RF 우위를 확정하기 어렵습니다. 평균은 개별 오차의 상한이 아닙니다. random 분할은 학습과 평가에 비슷한 골격이 들어갈 수 있으므로 새 골격 평가와 질문이 다릅니다.

## 5. 코드로 scaffold 누출 점검 — 10분

아래 코드를 `tmp/check_my_split.py`에 직접 입력해 실행합니다. 파일을 읽기만 합니다.

```python
import csv
from pathlib import Path

path = Path('reports/baseline_pilot_20261020_v2/split_assignments.csv')
with path.open() as stream:
    rows = list(csv.DictReader(stream))

for fold in ('1', '2', '3'):
    selected = [r for r in rows if r['scheme'] == 'scaffold' and r['fold'] == fold]
    train = {r['scaffold'] for r in selected if r['role'] == 'train'}
    test = {r['scaffold'] for r in selected if r['role'] == 'evaluation'}
    print(fold, len(train & test))
```

```bash
.venv-ml/bin/python tmp/check_my_split.py
```

예상 출력은 fold1·2·3 모두0입니다. 마지막0이 무엇을 뜻하는지 말로 설명합니다. 이 검사만으로 화학적으로 유사한 모든 분자의 누출이나 미래 성능을 보증하지는 않습니다.

## 6. 모델 재실행 — 5분 이상

기존 결과를 보호하므로 **새 경로 두 개**를 지정합니다. 현재 설정을 그대로 재실행해도 seed와 자료가 같으면 같은 예측을 얻어야 합니다.

```bash
PYTHONPATH=src .venv-ml/bin/python -m egfr_lab.modeling.baseline \
  --run-dir artifacts/my_baseline_01 \
  --report-dir reports/my_baseline_01
```

실행 후 `reports/my_baseline_01/metrics.csv`를 최종 결과와 비교합니다. 실행 시간·시각은 달라도 됩니다. 기존 폴더가 있다는 오류가 나오면 삭제하지 말고 `my_baseline_02`처럼 두 경로를 바꿉니다.

추가 실습은 설정을 복사해 `min_samples_leaf`를2에서1로 바꾸고 새 경로로 실행하는 것입니다. 이는 튜닝 학습이며, 이미 본 평가 자료로 바꾼 결과를 독립 최종 성능이라고 부르면 안 됩니다. 기존 `configs/baseline_pilot.json`과 원 데이터를 수정하지 않습니다.

## 자가 점검과 직접 남길 결과

```bash
.venv-ml/bin/python scripts/practice_basics.py --lesson quiz
```

답은 터미널에 한국어 선택지 번호로 입력합니다. 파일 업로드나 계정·네트워크 접근은 필요하지 않습니다.

실습 후 본인 말로 다음 세 문장을 작성해 두세요.

1. “209건 중 정확한 숫자167건이 있지만 모두 학습에 쓰지 않은 이유는 …”
2. “Dummy와 RF를 같은 분할에서 비교한 이유는 …”
3. “RF MAE가 더 작아도 우위를 확정하지 않은 이유는 …”

이 세 문장과 직접 실행한 명령·결과를 개인 실습 기록으로 남기면 프로젝트에서 직접 한 부분을 구체적으로 설명할 수 있습니다. 단백질 유래·구성체 해석처럼 전문가 확인이 필요한 결론은 미확인으로 남깁니다.
