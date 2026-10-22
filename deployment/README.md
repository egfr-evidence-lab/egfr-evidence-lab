# 배포 (M6)

**현재 상태: 컨테이너까지 완료, 클라우드 미실행.**

AWS 자원·이미지 레지스트리·실제 추론 요청은 만들지 않았습니다. 비용은 추정만 있습니다. 보고서: `reports/serving_m6_20261021/serving_report_ko.md`

설정은 실행 전에 고정했습니다: `configs/serving_m6.json`

---

## 1. 추론 서비스

```text
GET  /healthz     프로세스 생존. 모델 상태와 무관
GET  /readyz      모델 로딩 + 해시 3개 일치 시 200, 아니면 503
GET  /model-info  모델·코호트·설정 해시, 학습 규모, 라벨 범위, 고지, 런타임 버전
POST /predict     SMILES 배열(최대 32) → 분자별 예측·적용 범위 판정·고지
```

코드: `src/egfr_lab/serving/app.py` · 테스트: `tests/test_serving_app.py` (18개)

서비스는 M5 의 `ActivityPredictor` 를 그대로 호출합니다. 전처리와 적용 범위 판정을 서비스에서 다시 구현하면 두 경로의 출력이 갈라집니다.

**학습 엔드포인트는 없습니다.** 고지를 생략하는 옵션도 없습니다 — 적용 범위 밖에서 이 모델은 사실상 상수(8.048~8.143)를 돌려주므로, 숫자만 주는 응답은 포도당을 EGFR 억제제로 보고하게 됩니다.

## 2. 로컬 실행

```bash
# 호스트에서 직접
PYTHONPATH=src .venv-serve/bin/python -m uvicorn --factory \
    egfr_lab.serving.app:app_from_env --host 127.0.0.1 --port 8011

# 컨테이너
docker build --platform linux/arm64 -f deployment/Dockerfile -t egfr-pilot22-inference:v1 .
docker run -d --name egfr-serve -p 127.0.0.1:8010:8000 egfr-pilot22-inference:v1
curl -s http://127.0.0.1:8010/readyz
```

포트 8000 은 쓰지 마십시오. 이 기계에서는 다른 프로세스가 IPv4 로 점유하고 있어 `127.0.0.1:8000` 요청이 그 프로세스로 갑니다(보고서 7절).

## 3. 검증

```bash
PYTHONPATH=src .venv-serve/bin/python scripts/verify_serving_m6.py \
    --container-url http://127.0.0.1:8010 --container-name egfr-serve \
    --out reports/serving_m6_<날짜>
```

V1 parity · V2 model identity · V3 restart · V4 error handling · V5 latency · V6 logging 을 순서대로 실행하고 사전 예상과 대조합니다. 출력 폴더가 비어 있지 않으면 거부합니다.

## 4. 클라우드 — 실행하기 전에

```text
고정 모델 파일 → 이미지에 포함 (324KB. S3 를 쓸 규모가 아니다)
FastAPI 추론 코드 → Docker image → ECR
ECS Fargate ARM64, 0.25 vCPU / 0.5 GB → /readyz · /model-info · /predict
실행 로그·지연시간·오류 → CloudWatch Logs (보존 기간 설정 필수)
```

### 순서

1. `aws login --profile skn33` — 사용자가 직접 (브라우저 인증)
2. `.venv-serve/bin/python scripts/check_cloud_access_m6.py --profile skn33 --out reports/serving_m6_<날짜>`
   - **읽기 전용입니다. 자원을 만들지 않습니다.** 배포에 필요한 동작 23개를 권한 시뮬레이션으로 점검합니다
   - 배포를 바로 시도했다가 중간에 실패하면 어디까지 만들어졌는지 추적하기 어렵고 남은 자원이 과금됩니다
3. 판정이 `ready` 면 **비용 승인을 받은 뒤** 배포
4. 막히면 차단 증거를 남기고 보류합니다 (M4 와 같은 방식)

### 비용 추정 (서울 리전, 0.25 vCPU / 0.5 GB / ARM64)

```bash
.venv-serve/bin/python scripts/estimate_cloud_cost_m6.py \
    --region ap-northeast-2 --out reports/serving_m6_<날짜>
```

요율을 손으로 적지 않고 AWS 공개 가격 API 에서 받아 응답 SHA-256 과 함께 보존합니다.

| 시나리오 | 추정 |
|---|---|
| 검증 1회 (1시간) | $0.0172 |
| 하루 운용 | $0.3960 |
| 한 달 상시 | $12.02 |

시간당 $0.016468 = Fargate $0.011358 + 공용 IPv4 $0.005 + ECR 저장 $0.000111.

**추정입니다.** 실제 과금은 Cost Explorer·청구서로만 확인됩니다.

### 비용 통제 규칙

- 측정 직후 task 를 중지합니다
- Elastic IP 를 따로 만들지 않습니다. 공용 IPv4 는 task 와 함께 사라집니다
- CloudWatch 로그 그룹에 보존 기간을 설정합니다. 무기한 보존은 저장 비용이 쌓입니다
- 만든 자원은 삭제하고 삭제 사실을 기록합니다
- NAT Gateway·로드 밸런서를 쓰지 않는 설계입니다. 쓰면 시간당 요금이 따로 붙습니다

### 배포 후 확인할 것

1. 로컬·컨테이너·클라우드의 같은 입력에 같은 출력 (현재 로컬·컨테이너 일치 확인됨)
2. `/model-info` 의 해시 3개가 고정값과 일치
3. 재시작 후 모델 로딩, 유효하지 않은 SMILES·배치 초과·실패 처리
4. 요청 수·p50/p95 지연·실패율. **측정 조건과 표본 수를 함께 적습니다**
5. 서비스 역할 최소 권한. API 키는 저장소에 넣지 않고 배포 환경의 secret 기능을 씁니다
6. 실제 청구액 (Cost Explorer)

## 5. 이미지

| 항목 | 값 |
|---|---|
| 태그 | `egfr-pilot22-inference:v1` |
| 크기 | 829 MB · linux/arm64 |
| 베이스 | `python:3.12.14-slim-bookworm@sha256:eb5be8e5...0333` (digest 고정) |
| 실행 사용자 | non-root (uid 10001) |
| 직접 의존성 | `requirements-serve.txt` |
| 실제 설치 목록 | `requirements-serve.lock.txt` (컨테이너 내부 `pip freeze` 추출) |

베이스 이미지를 digest 로 고정한 이유: 태그는 같은 이름으로 내용이 바뀔 수 있고, 그러면 "다시 만들 수 있다"는 말이 성립하지 않습니다.

`.dockerignore` 는 허용 목록 방식입니다 — 전부 제외하고 필요한 것만 되돌립니다. 거부 목록이면 새 폴더가 생길 때마다 빌드 컨텍스트에 섞입니다. 이 저장소는 공개이고 `data/`(247MB)에 원자료가 있습니다. 이미지에 자격증명과 원자료를 넣지 않습니다.

ARM64 로 빌드한 이유는 로컬 Docker 가 aarch64 이고, `linux/amd64` 를 QEMU 에뮬레이션으로 빌드하면 지연시간 측정이 왜곡되기 때문입니다. amd64 로 배포하려면 따로 빌드하고 지연시간을 다시 측정해야 합니다.

## 6. 범위에 없는 것

MLflow 서버의 클라우드 상시 운영은 초기 범위에 넣지 않습니다. 로컬 실험 추적 후 필요성이 생기면 확대합니다. [MLflow Tracking](https://mlflow.org/docs/latest/ml/tracking/)

참고: [AWS Fargate](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html) · [S3 Versioning](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html)
