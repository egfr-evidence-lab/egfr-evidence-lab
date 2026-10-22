"""M6 — 추론 API 의 방어장치 테스트.

정상 경로보다 **실패 경로**를 많이 본다. 서비스가 조용히 숫자를 만들어내는지가
이 마일스톤에서 가장 위험한 지점이기 때문이다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/serving_m6.json"
ARTIFACT = ROOT / "artifacts/agent_predictor_20261021"

pytest.importorskip("fastapi", reason="serving 추가 의존성(.venv-serve)이 필요하다")
pytest.importorskip("sklearn")

from fastapi.testclient import TestClient            # noqa: E402

from egfr_lab.serving.app import ServingConfig, build_app   # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    if not ARTIFACT.exists():
        pytest.skip("예측기 artifact 가 없다")
    return TestClient(build_app(ServingConfig(CONFIG)))


@pytest.fixture(scope="module")
def config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# 상태 엔드포인트
# --------------------------------------------------------------------------- #

def test_healthz_alive(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "alive"


def test_readyz_200_and_all_hashes_match(client: TestClient) -> None:
    r = client.get("/readyz")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ready"] is True
    # V2: 설정에 고정한 해시 3개가 모두 실제와 같아야 한다.
    for name, pair in body["hash_checks"].items():
        assert pair["match"] is True, f"{name} 불일치: {pair}"


def test_model_info_reports_frozen_hashes(client: TestClient, config: dict) -> None:
    body = client.get("/model-info").json()
    served = config["served_model"]
    assert body["model"]["model_sha256"] == served["model_sha256"]
    assert body["model"]["cohort_sha256"] == served["cohort_sha256"]
    assert body["model"]["settings_sha256"] == served["settings_sha256"]
    assert body["model"]["n_training_molecules"] == 22
    assert body["model"]["n_training_scaffolds"] == 12


def test_model_info_carries_scope_and_caveats(client: TestClient) -> None:
    body = client.get("/model-info").json()
    assert "22" in body["scope_limit"]
    caveats = body["mandatory_caveats"]
    assert caveats, "필수 고지가 비어 있으면 안 된다"
    joined = " ".join(caveats)
    # M1 에서 Dummy 대비 우위가 확정되지 않았다는 사실이 응답에 있어야 한다.
    assert "확정되지 않았다" in joined
    assert "22" in joined


def test_response_headers_identify_the_model(client: TestClient) -> None:
    r = client.get("/healthz")
    assert "X-Model-Sha256" in r.headers
    assert float(r.headers["X-Process-Time-Ms"]) >= 0


# --------------------------------------------------------------------------- #
# 정상 예측
# --------------------------------------------------------------------------- #

def _probe(config: dict, pid: str) -> str:
    return next(p["smiles"] for p in config["probe_molecules"] if p["id"] == pid)


def test_in_domain_molecule_predicts_with_caveats(client: TestClient, config: dict) -> None:
    smi = _probe(config, "P-in-1")
    r = client.post("/predict", json={"smiles": [smi]})
    assert r.status_code == 200, r.text
    body = r.json()
    res = body["results"][0]
    assert res["status"] == "ok"
    assert isinstance(res["predicted_pIC50"], float)
    # 고지를 생략할 수 없다.
    assert res["caveats"], "성공 응답에 고지가 비어 있으면 안 된다"
    assert body["mandatory_caveats"]
    # 예측값임을 응답이 스스로 밝힌다.
    assert res["value_is_a_prediction_not_a_measurement"] is True
    assert res["source_ids"]


def test_out_of_domain_molecule_is_flagged(client: TestClient, config: dict) -> None:
    """아스피린은 적용 범위 밖이다. 숫자를 주더라도 외삽임을 밝혀야 한다."""
    smi = _probe(config, "P-out-1")
    body = client.post("/predict", json={"smiles": [smi]}).json()
    res = body["results"][0]
    assert res["status"] == "ok"
    assert res["in_applicability_domain"] is False
    joined = " ".join(res["caveats"])
    assert "적용 범위 밖" in joined
    assert "외삽" in joined
    assert res["applicability"]["scaffold_in_training"] is False


def test_every_ok_result_names_the_model(client: TestClient, config: dict) -> None:
    smi = _probe(config, "P-in-1")
    body = client.post("/predict", json={"smiles": [smi, smi]}).json()
    assert body["model_sha256"] == config["served_model"]["model_sha256"]
    assert body["api_version"] == "v1"


# --------------------------------------------------------------------------- #
# 실패 경로 — 여기서 값을 만들어내면 안 된다
# --------------------------------------------------------------------------- #

def test_unparsable_smiles_has_no_value_field(client: TestClient, config: dict) -> None:
    smi = _probe(config, "P-bad-1")
    body = client.post("/predict", json={"smiles": [smi]}).json()
    res = body["results"][0]
    assert res["status"] == "error"
    # 핵심: 값 필드 자체가 없어야 한다. 0.0 이나 평균값으로 메우지 않는다.
    assert "predicted_pIC50" not in res
    assert body["n_ok"] == 0


def test_empty_string_smiles_is_rejected(client: TestClient) -> None:
    """빈 문자열은 RDKit 에서 원자 0개 분자로 파싱된다(M5 에서 실제로 겪은 결함).

    예측값이 나오면 안 된다.
    """
    body = client.post("/predict", json={"smiles": [""]}).json()
    res = body["results"][0]
    assert res["status"] == "error"
    assert "predicted_pIC50" not in res


def test_one_bad_molecule_does_not_discard_the_good_ones(client: TestClient,
                                                         config: dict) -> None:
    good = _probe(config, "P-in-1")
    bad = _probe(config, "P-bad-1")
    body = client.post("/predict", json={"smiles": [good, bad, good]}).json()
    assert [r["status"] for r in body["results"]] == ["ok", "error", "ok"]
    assert body["n_ok"] == 2
    assert [r["index"] for r in body["results"]] == [0, 1, 2]


def test_empty_batch_is_422(client: TestClient) -> None:
    assert client.post("/predict", json={"smiles": []}).status_code == 422


def test_over_max_batch_is_413(client: TestClient, config: dict) -> None:
    limit = config["api_contract"]["predict_request"]["max_batch"]
    smi = _probe(config, "P-out-2")
    r = client.post("/predict", json={"smiles": [smi] * (limit + 1)})
    assert r.status_code == 413
    assert str(limit) in r.json()["error"]


def test_missing_field_is_422(client: TestClient) -> None:
    assert client.post("/predict", json={"molecules": ["CCO"]}).status_code == 422


def test_non_json_body_is_4xx_not_500(client: TestClient) -> None:
    r = client.post("/predict", content=b"not json at all",
                    headers={"Content-Type": "application/json"})
    assert 400 <= r.status_code < 500, f"500 이 나오면 안 된다: {r.status_code}"


def test_wrong_type_is_422(client: TestClient) -> None:
    assert client.post("/predict", json={"smiles": "CCO"}).status_code == 422
    assert client.post("/predict", json={"smiles": [123]}).status_code == 422


# --------------------------------------------------------------------------- #
# 설계상 거부
# --------------------------------------------------------------------------- #

def test_no_training_endpoint_exists(client: TestClient) -> None:
    for path in ("/train", "/fit", "/retrain"):
        assert client.post(path, json={}).status_code == 404


def test_hash_mismatch_makes_service_not_ready(tmp_path: Path, config: dict) -> None:
    """설정의 해시를 바꿔 치면 서비스가 준비되지 않아야 한다.

    다른 모델을 조용히 서비스하는 쪽이 멈추는 쪽보다 나쁘다.
    """
    tampered = json.loads(CONFIG.read_text(encoding="utf-8"))
    tampered["served_model"]["model_sha256"] = "0" * 64
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(tampered, ensure_ascii=False), encoding="utf-8")

    c = TestClient(build_app(ServingConfig(path)))
    assert c.get("/readyz").status_code == 503
    # 준비되지 않으면 예측도 거부한다.
    assert c.post("/predict", json={"smiles": ["CCO"]}).status_code == 503
    assert c.get("/healthz").status_code == 200       # 살아 있다는 신호는 따로다
