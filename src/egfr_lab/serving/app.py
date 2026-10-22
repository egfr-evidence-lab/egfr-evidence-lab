"""추론 API 본체.

configs/serving_m6.json 의 계약을 그대로 따른다:

* 응답마다 어떤 모델이 답했는지(`model_sha256`)와 필수 고지를 넣는다.
* 분자 하나가 실패해도 나머지를 버리지 않는다. 실패한 분자는 값 없이 오류로 돌아온다.
* 해석 불가 SMILES 를 0 이나 평균값으로 메우지 않는다.
* 고지를 생략하는 옵션은 제공하지 않는다.
* 학습 엔드포인트는 없다. 서비스는 추론만 한다.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[3]

API_VERSION = "v1"
SERVICE_NAME = "egfr-pilot22-inference"

log = logging.getLogger("egfr_lab.serving")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def runtime_versions() -> dict[str, str]:
    """응답에 실을 런타임 버전. 호스트와 컨테이너의 차이를 추적하기 위해 남긴다."""
    out: dict[str, str] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
    }
    for name, mod in (("numpy", "numpy"), ("scipy", "scipy"), ("sklearn", "sklearn"),
                      ("joblib", "joblib"), ("rdkit", "rdkit")):
        try:
            out[name] = __import__(mod).__version__
        except Exception:                                      # noqa: BLE001
            out[name] = "unavailable"
    return out


# --------------------------------------------------------------------------- #
# 요청·응답 스키마
# --------------------------------------------------------------------------- #

class PredictRequest(BaseModel):
    smiles: list[str] = Field(..., description="SMILES 문자열 배열")


class ServingConfig:
    """configs/serving_m6.json 을 읽어 고정값을 들고 있는다.

    해시 기대값이 설정에 있고 실제 파일 해시를 시작 시 계산해 맞춰 본다.
    어긋나면 준비되지 않은 것으로 본다(`/readyz` 503). 다른 모델을 조용히
    서비스하는 쪽이 멈추는 쪽보다 나쁘다.
    """

    def __init__(self, config_path: Path, artifact_dir: Path | None = None):
        self.config_path = config_path
        self.raw = json.loads(config_path.read_text(encoding="utf-8"))
        served = self.raw["served_model"]
        self.artifact_dir = artifact_dir or (ROOT / served["artifact_dir"])
        self.expected = {
            "model_sha256": served["model_sha256"],
            "cohort_sha256": served["cohort_sha256"],
            "settings_sha256": served["settings_sha256"],
        }
        self.model_file = served["model_file"]
        self.scope_limit = served["scope_limit"]
        self.max_batch = int(self.raw["api_contract"]["predict_request"]["max_batch"])
        self.config_sha256 = sha256_file(config_path)


class _State:
    """로딩 결과. 실패해도 프로세스는 살려 두고 /readyz 로 알린다."""

    def __init__(self) -> None:
        self.predictor: Any = None
        self.manifest: dict = {}
        self.model_sha256: str = ""
        self.hash_checks: dict[str, Any] = {}
        self.ready: bool = False
        self.load_error: str = ""
        self.load_seconds: float = 0.0
        self.loaded_at_utc: str = ""


def build_app(config: ServingConfig) -> FastAPI:
    # ActivityPredictor 는 M5 의 도구 코드다. 서비스 전용 사본을 만들지 않는다.
    from egfr_lab.agent.tools import ActivityPredictor

    state = _State()
    app = FastAPI(title=SERVICE_NAME, version=API_VERSION,
                  description="pilot22(22건) 범위의 EGFR WT 생화학 pIC50 예측. "
                              "연구·포트폴리오 목적이며 의사결정 근거로 쓰지 않는다")

    def _load() -> None:
        t0 = time.perf_counter()
        try:
            model_path = config.artifact_dir / config.model_file
            state.model_sha256 = sha256_file(model_path)
            predictor = ActivityPredictor(config.artifact_dir)
            manifest = predictor.manifest

            # 설정에 고정한 해시와 실제 값이 같은지 본다.
            checks = {
                "model_sha256": {
                    "expected": config.expected["model_sha256"],
                    "actual": state.model_sha256,
                },
                "cohort_sha256": {
                    "expected": config.expected["cohort_sha256"],
                    "actual": manifest.get("cohort_sha256", ""),
                },
                "settings_sha256": {
                    "expected": config.expected["settings_sha256"],
                    "actual": manifest.get("settings_sha256", ""),
                },
            }
            for name, pair in checks.items():
                pair["match"] = pair["expected"] == pair["actual"]
            state.hash_checks = checks
            state.predictor = predictor
            state.manifest = manifest
            state.ready = all(p["match"] for p in checks.values())
            if not state.ready:
                bad = [k for k, p in checks.items() if not p["match"]]
                state.load_error = f"해시 불일치: {', '.join(bad)}"
                log.error("모델 해시가 설정과 다르다: %s", bad)
        except Exception as exc:                               # noqa: BLE001
            # 예외 메시지에 경로 외 내부 값을 싣지 않는다.
            state.load_error = f"{type(exc).__name__}: {exc}"
            state.ready = False
            log.exception("모델 로딩 실패")
        state.load_seconds = time.perf_counter() - t0
        state.loaded_at_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        log.info("모델 로딩 %s (%.3fs)", "성공" if state.ready else "실패", state.load_seconds)

    # 앱을 만들 때 바로 로딩한다. FastAPI 의 on_event 는 폐기 예정이고,
    # lifespan 을 쓰면 테스트 클라이언트를 context manager 로 열지 않은 경우
    # 모델이 로딩되지 않은 앱이 조용히 돌아간다. 로딩 실패는 예외로 올리지 않고
    # /readyz 503 으로 알린다.
    _load()

    @app.middleware("http")
    async def _timing(request: Request, call_next):
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:                               # noqa: BLE001
            ms = (time.perf_counter() - t0) * 1000
            # 요청 본문(SMILES)은 로그에 남기지 않는다. 경로·상태·예외 종류만 남긴다.
            log.error("%s %s -> 500 %.1fms %s", request.method, request.url.path,
                      ms, type(exc).__name__)
            raise
        ms = (time.perf_counter() - t0) * 1000
        response.headers["X-Process-Time-Ms"] = f"{ms:.3f}"
        response.headers["X-Model-Sha256"] = state.model_sha256[:16]
        log.info("%s %s -> %d %.1fms", request.method, request.url.path,
                 response.status_code, ms)
        return response

    # ----------------------------------------------------------------- #

    @app.get("/healthz")
    def healthz() -> dict:
        """프로세스가 살아 있는지만 본다. 모델 상태는 /readyz 가 답한다."""
        return {"status": "alive", "service": SERVICE_NAME, "api_version": API_VERSION}

    @app.get("/readyz")
    def readyz() -> JSONResponse:
        body = {
            "ready": state.ready,
            "model_loaded": state.predictor is not None,
            "hash_checks": state.hash_checks,
            "load_seconds": round(state.load_seconds, 3),
            "error": state.load_error or None,
        }
        return JSONResponse(body, status_code=200 if state.ready else 503)

    @app.get("/model-info")
    def model_info() -> JSONResponse:
        if state.predictor is None:
            return JSONResponse(
                {"error": "모델이 로딩되지 않았다", "detail": state.load_error or None},
                status_code=503)
        m = state.manifest
        return JSONResponse({
            "service": SERVICE_NAME,
            "api_version": API_VERSION,
            "model": {
                "kind": "RandomForest (Morgan r=2, 2048bit, chirality)",
                "model_sha256": state.model_sha256,
                "cohort_sha256": m.get("cohort_sha256"),
                "settings_sha256": m.get("settings_sha256"),
                "artifact_created_at_utc": m.get("created_at_utc"),
                "trained_on": m.get("trained_on"),
                "n_training_molecules": m.get("n_training_molecules"),
                "n_training_scaffolds": m.get("n_training_scaffolds"),
                "training_label_range": m.get("label_range"),
                "random_state": m.get("random_state"),
            },
            "scope_limit": config.scope_limit,
            "measured_limits_from_m1": m.get("measured_limits_from_m1"),
            "mandatory_caveats": m.get("mandatory_caveats", []),
            "applicability_rules": {
                "scaffold_in_training": "질의 분자의 Murcko scaffold 가 학습 12개에 있는가",
                "max_tanimoto_threshold": 0.5,
                "label_range_check": "예측값이 학습 라벨 범위 안인가",
                "note": "세 기준은 거친 지표다. 통과했다고 예측이 맞다는 뜻은 아니다",
            },
            "config": {
                "path": str(config.config_path.name),
                "sha256": config.config_sha256,
                "max_batch": config.max_batch,
            },
            "runtime": runtime_versions(),
            "loaded_at_utc": state.loaded_at_utc,
            "refused_by_design": config.raw["api_contract"]["refused_by_design"],
        })

    @app.post("/predict")
    def predict(req: PredictRequest) -> JSONResponse:
        if state.predictor is None or not state.ready:
            return JSONResponse(
                {"error": "모델이 준비되지 않았다. 예측하지 않는다",
                 "detail": state.load_error or None}, status_code=503)

        n = len(req.smiles)
        if n == 0:
            return JSONResponse({"error": "smiles 가 비어 있다"}, status_code=422)
        if n > config.max_batch:
            return JSONResponse(
                {"error": f"한 번에 {config.max_batch}개까지만 받는다. 요청 {n}개"},
                status_code=413)

        results = []
        for i, smi in enumerate(req.smiles):
            t0 = time.perf_counter()
            try:
                tr = state.predictor(smi)
            except Exception as exc:                           # noqa: BLE001
                log.error("예측 중 예외 index=%d %s", i, type(exc).__name__)
                results.append({"index": i, "smiles": smi, "status": "error",
                                "message": f"예측 실패: {type(exc).__name__}"})
                continue
            ms = (time.perf_counter() - t0) * 1000

            if tr.status != "ok":
                # 값을 만들지 않는다. predicted_pIC50 필드 자체를 넣지 않는다.
                results.append({"index": i, "smiles": smi, "status": tr.status,
                                "message": tr.message, "predict_ms": round(ms, 3)})
                continue

            data = tr.data
            results.append({
                "index": i,
                "smiles": smi,
                "status": "ok",
                "predicted_pIC50": data["predicted_pIC50"],
                "value_is_a_prediction_not_a_measurement": True,
                "applicability": data["applicability"],
                "in_applicability_domain": bool(
                    data["applicability"]["scaffold_in_training"]
                    and data["applicability"]["max_tanimoto_to_training"] >= 0.5),
                "caveats": tr.caveats,
                "source_ids": tr.source_ids,
                "predict_ms": round(ms, 3),
            })

        return JSONResponse({
            "api_version": API_VERSION,
            "model_sha256": state.model_sha256,
            "n_requested": n,
            "n_ok": sum(1 for r in results if r["status"] == "ok"),
            "results": results,
            "scope_limit": config.scope_limit,
            "mandatory_caveats": state.manifest.get("mandatory_caveats", []),
        })

    return app


def app_from_env() -> FastAPI:
    """uvicorn 진입점. 설정·artifact 경로를 환경변수로 받는다."""
    logging.basicConfig(
        level=os.environ.get("EGFR_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout)
    config_path = Path(os.environ.get("EGFR_SERVING_CONFIG",
                                      str(ROOT / "configs/serving_m6.json")))
    artifact_env = os.environ.get("EGFR_ARTIFACT_DIR")
    return build_app(ServingConfig(config_path,
                                   Path(artifact_env) if artifact_env else None))
