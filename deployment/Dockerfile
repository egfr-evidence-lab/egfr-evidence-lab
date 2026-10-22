# M6 — pilot22 추론 API 컨테이너
#
# 빌드(저장소 루트에서):
#   docker build -f deployment/Dockerfile -t egfr-pilot22-inference:v1 .
#
# 베이스 이미지를 digest 로 고정한다. 태그는 같은 이름으로 내용이 바뀔 수 있고,
# 그러면 "이 이미지를 다시 만들 수 있다"는 말이 성립하지 않는다.
#
# 아래는 manifest **인덱스**(multi-platform) digest 다. --platform 플래그에 따라
# 그 안에서 플랫폼별 이미지가 선택되므로 한 줄로 두 플랫폼을 고정한다.
# python:3.12.14-slim-bookworm, 2026-10-21 확인:
#   index  sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e
#   arm64  sha256:eb5be8e5b4d0a159c237946bbdd06356dda5d19c30fc4f7843e8046d3a590333
#   amd64  sha256:1aaa65a85fda306ffb8b910824d4e93bdce61e212c7e87168123ea3073b41a1a
#
# 2026-10-22 변경: 처음에는 arm64 digest 를 직접 썼다. Cloud Run 이 x86-64 만
# 받기 때문에 amd64 빌드가 필요해졌고, 인덱스 digest 로 바꿨다. arm64 를 다시
# 빌드해 이전 이미지와 같은지 확인한 뒤 바꿨다(보고서에 결과를 적는다).
FROM python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src \
    EGFR_SERVING_CONFIG=/app/configs/serving_m6.json \
    EGFR_ARTIFACT_DIR=/app/artifacts/agent_predictor_20261021

WORKDIR /app

COPY deployment/requirements-serve.txt /app/deployment/requirements-serve.txt
RUN pip install --no-cache-dir -r /app/deployment/requirements-serve.txt

# 실제로 설치된 간접 의존성까지 이미지 안에 남긴다. 이미지에서 꺼내
# deployment/requirements-serve.lock.txt 로 보존한다.
RUN pip freeze > /app/deployment/installed-freeze.txt

# 서비스에 필요한 것만 복사한다. data/·reports/·.venv* 는 .dockerignore 가 막는다.
# 원자료와 자격증명을 이미지에 넣지 않는다.
COPY src/egfr_lab/__init__.py src/egfr_lab/config.py src/egfr_lab/labels.py /app/src/egfr_lab/
COPY src/egfr_lab/agent /app/src/egfr_lab/agent
COPY src/egfr_lab/serving /app/src/egfr_lab/serving
COPY configs/serving_m6.json /app/configs/serving_m6.json
COPY artifacts/agent_predictor_20261021 /app/artifacts/agent_predictor_20261021

# root 로 돌리지 않는다.
RUN useradd --create-home --uid 10001 serve && chown -R serve:serve /app
USER serve

EXPOSE 8000

# 모델 해시가 설정과 어긋나면 /readyz 가 503 이고 health check 가 실패한다.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=4).status==200 else 1)"

# 워커 1개. 지연시간 측정을 단순하게 두기 위한 선택이고, 처리량 설정이 아니다.
CMD ["python", "-m", "uvicorn", "--factory", "egfr_lab.serving.app:app_from_env", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--log-level", "info"]
