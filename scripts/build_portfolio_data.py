"""포트폴리오 화면용 데이터 추출.

**임의의 숫자를 만들지 않는다.** 모든 값을 실제 산출물에서 읽거나
실제 데이터에 필터를 적용해 계산하고, 출처 경로를 함께 남긴다.

퍼널은 **사후 재구성**이다. 실제 코호트 확정은 여러 단계의 수동 원문 검토를
거쳤고 이 스크립트의 필터 순서와 같지 않다. 여기서 보여주는 것은
'주요 선정 기준을 순차 적용하면 규모가 어떻게 줄어드는가'이며,
실제 정제 과정의 재현이 아니다.

사용:
  .venv-serve/bin/python scripts/build_portfolio_data.py --out tmp/portfolio_data
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FULL = ROOT / "data/interim/chembl_full_20261020"
PILOT_COHORT = ROOT / "data/interim/cohort_review_20261020/context_pilot.csv"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# 1) 코호트 정제 퍼널
# --------------------------------------------------------------------------- #

def build_funnel(m: pd.DataFrame) -> dict:
    """주요 선정 기준을 순차 적용하며 규모 변화를 기록한다."""
    steps = []

    def snap(label: str, df: pd.DataFrame, rule: str, why: str) -> None:
        steps.append({
            "step": len(steps),
            "label": label,
            "rule": rule,
            "why": why,
            "measurements": int(len(df)),
            "molecules": int(df["molecule_chembl_id"].nunique()),
            "assays": int(df["assay_chembl_id"].nunique()),
            "documents": int(df["document_chembl_id"].nunique()),
        })

    cur = m
    snap("수집 전체", cur,
         "target CHEMBL203 · standard_type=IC50",
         "ChEMBL 에서 받은 원자료 전체. 이 단계에서 이미 IC50 만 받았다")

    cur = cur[cur["target_organism"] == "Homo sapiens"]
    snap("인간", cur, "target_organism = Homo sapiens",
         "다른 종의 EGFR 을 사람 데이터와 섞지 않는다")

    cur = cur[cur["standard_relation"] == "="]
    snap("등식 값만", cur, "standard_relation = '='",
         "부등호(>, <) 관측은 '그 농도에서 효과가 없었다'는 뜻이다. 등식 값과 평균 내면 라벨이 왜곡된다")

    cur = cur[cur["standard_units"] == "nM"]
    cur = cur[cur["standard_value"].notna()]
    snap("단위·값 확정", cur, "standard_units = nM · standard_value 존재",
         "단위가 다르거나 값이 없는 행을 쓰지 않는다")

    cur = cur[cur["assay_variant_mutation"].isna()]
    snap("변이 미지정(WT 후보)", cur, "assay_variant_mutation 없음",
         "변이형과 정상형을 섞지 않는다. 다만 '미지정'이 곧 WT 라는 뜻은 아니어서 원문 검토가 따로 필요하다")

    cur = cur[cur["assay_type"] == "B"]
    snap("생화학 실험", cur, "assay_type = B",
         "세포 실험(IC50)과 효소 실험(IC50)은 다른 양이다. 섞지 않는다")

    cur = cur[cur["bao_label"] == "single protein format"]
    snap("단일 단백질 형식", cur, "bao_label = single protein format",
         "측정 형식을 하나로 고정한다")

    cur = cur[cur["assay_detail__confidence_score"] == 9]
    snap("표적 신뢰도 9", cur, "confidence_score = 9",
         "ChEMBL 의 표적 지정 신뢰도 최고값만 남긴다")

    cur = cur[cur["data_validity_comment"].isna()]
    snap("품질 경고 없음", cur, "data_validity_comment 없음",
         "'Outside typical range'·'Potential transcription error' 가 붙은 행을 제외한다")

    cur = cur[cur["potential_duplicate"] != 1]
    snap("중복 표시 제외", cur, "potential_duplicate ≠ 1",
         "같은 측정이 두 번 들어간 것으로 표시된 행을 제외한다")

    pooled = cur
    cur = cur[cur["assay_chembl_id"] == "CHEMBL4258549"]
    snap("단일 assay 선택", cur, "assay_chembl_id = CHEMBL4258549",
         "실험 조건이 같다고 확인하지 못한 assay 를 합치지 않았다(pooling 승인 0쌍). "
         "원문으로 프로토콜을 검토한 단일 assay 하나만 학습에 썼다")

    return {
        "steps": steps,
        "is_a_reconstruction": (
            "사후 재구성이다. 실제 코호트 확정은 여러 단계의 수동 원문 검토를 거쳤고 "
            "이 필터 순서와 같지 않다. 주요 기준을 순차 적용하면 규모가 어떻게 줄어드는지를 "
            "보여주는 것이고 정제 과정의 재현이 아니다"),
        "pooling_candidates_at_last_step": {
            "measurements": int(len(pooled)),
            "assays": int(pooled["assay_chembl_id"].nunique()),
            "note": ("기준을 모두 통과한 assay 가 여러 개 남지만, 실험 조건이 같다는 것을 "
                     "원문으로 확인하지 못해 합치지 않았다. 이것이 22건이라는 규모의 직접 원인이다"),
        },
        "source": "data/interim/chembl_full_20261020/measurements_joined.parquet",
    }


# --------------------------------------------------------------------------- #
# 2) 전체 데이터 맥락 (집계만. 26,600행 전체를 화면에 넣지 않는다)
# --------------------------------------------------------------------------- #

def build_context(m: pd.DataFrame, a: pd.DataFrame, d: pd.DataFrame) -> dict:
    vm = a["variant_mutation"].dropna()
    variants = [{"mutation": k, "assays": int(v)} for k, v in vm.value_counts().items()]

    years = d["year"].dropna().astype(int)
    by_decade = (years // 10 * 10).value_counts().sort_index()

    return {
        "totals": {
            "measurements": int(len(m)),
            "molecules": int(m["molecule_chembl_id"].nunique()),
            "assays": int(m["assay_chembl_id"].nunique()),
            "documents": int(m["document_chembl_id"].nunique()),
            "molecules_with_smiles": int(m["canonical_smiles"].notna().sum()),
        },
        "variants": {
            "assays_with_variant": int(len(vm)),
            "assays_total": int(len(a)),
            "distinct_labels": int(vm.nunique()),
            "rows": variants,
            "resistance_note": ("L858R 은 활성화 변이, T790M 은 1세대 저해제 내성, "
                                "C797S 는 3세대 저해제 내성과 연관돼 보고된다. "
                                "이 표는 ChEMBL assay 의 변이 표기 분포이며 임상 빈도가 아니다"),
            "undefined_note": ("'UNDEFINED MUTATION' 은 변이가 있다고만 적힌 것이다. "
                               "어떤 변이인지 모르므로 WT 로도 특정 변이로도 쓸 수 없다"),
        },
        "relations": [{"relation": k, "measurements": int(v)}
                      for k, v in m["standard_relation"].value_counts().items()],
        "assay_types": [{"type": k, "assays": int(v)}
                        for k, v in a["assay_type"].value_counts().items()],
        "assay_type_legend": {"B": "생화학(binding/enzyme)", "F": "기능(functional)",
                              "A": "ADME", "T": "독성"},
        "formats": [{"format": k, "assays": int(v)}
                    for k, v in a["bao_label"].value_counts().items()],
        "confidence": [{"score": int(k), "assays": int(v)}
                       for k, v in a["confidence_score"].value_counts().sort_index().items()],
        "quality_flags": {
            "data_validity_comment": [
                {"comment": k, "measurements": int(v)}
                for k, v in m["data_validity_comment"].value_counts().items()],
            "potential_duplicate": int((m["potential_duplicate"] == 1).sum()),
            "pchembl_present": int(m["pchembl_value"].notna().sum()),
        },
        "documents": {
            "total": int(len(d)),
            "with_doi": int(d["doi"].notna().sum()),
            "year_min": int(years.min()),
            "year_max": int(years.max()),
            "by_decade": [{"decade": int(k), "documents": int(v)}
                          for k, v in by_decade.items()],
            "top_journals": [{"journal": k, "documents": int(v)}
                             for k, v in d["journal"].value_counts().head(8).items()],
        },
        "source": "data/interim/chembl_full_20261020/*.parquet",
    }


# --------------------------------------------------------------------------- #
# 3) 학습 코호트 22건의 근거 체인
# --------------------------------------------------------------------------- #

def build_cohort_chain(m: pd.DataFrame, d: pd.DataFrame) -> dict:
    sub = m[m["assay_chembl_id"] == "CHEMBL4258549"].copy()
    doc_id = sub["document_chembl_id"].iloc[0]
    doc = d[d["document_chembl_id"] == doc_id].iloc[0]

    rows = []
    for _, r in sub.iterrows():
        rows.append({
            "activity_id": int(r["activity_id"]),
            "molecule_chembl_id": r["molecule_chembl_id"],
            "smiles": r["canonical_smiles"],
            "relation": r["standard_relation"],
            "value_nM": float(r["standard_value"]),
            "pIC50": (round(float(r["pchembl_value"]), 4)
                      if pd.notna(r["pchembl_value"]) else None),
        })
    rows.sort(key=lambda x: x["value_nM"])

    return {
        "assay_chembl_id": "CHEMBL4258549",
        "assay_description": sub["assay_description"].iloc[0],
        "assay_type": sub["assay_type"].iloc[0],
        "bao_label": sub["bao_label"].iloc[0],
        "confidence_score": int(sub["assay_detail__confidence_score"].iloc[0]),
        "variant_mutation": (None if pd.isna(sub["assay_variant_mutation"].iloc[0])
                             else sub["assay_variant_mutation"].iloc[0]),
        "document": {
            "document_chembl_id": doc_id,
            "doi": None if pd.isna(doc["doi"]) else doc["doi"],
            "pubmed_id": None if pd.isna(doc["pubmed_id"]) else str(doc["pubmed_id"]),
            "year": None if pd.isna(doc["year"]) else int(doc["year"]),
            "title": None if pd.isna(doc["title"]) else doc["title"],
            "journal": None if pd.isna(doc["journal"]) else doc["journal"],
        },
        "n_measurements": int(len(rows)),
        "measurements": rows,
        "chain": "분자 → 측정(activity_id) → assay(조건·변이·신뢰도) → 문헌(DOI·저널·연도)",
        "source": "data/interim/chembl_full_20261020/measurements_joined.parquet",
    }


# --------------------------------------------------------------------------- #
# 4) 평가지표
# --------------------------------------------------------------------------- #

def build_metrics() -> dict:
    out: dict = {}

    m1_metrics = pd.read_csv(ROOT / "reports/baseline_pilot_20261020_v2/metrics.csv")
    m1_paired = pd.read_csv(ROOT / "reports/baseline_pilot_20261020_v2/paired_comparison.csv")
    m1_pred = pd.read_csv(ROOT / "reports/baseline_pilot_20261020_v2/predictions.csv")

    out["M1"] = {
        "name": "기준 모델 (Dummy vs Morgan-RF)",
        "metrics": m1_metrics.to_dict(orient="records"),
        "paired": m1_paired.to_dict(orient="records"),
        "predictions": m1_pred[["scheme", "seed", "model", "observed_pIC50",
                                "predicted_pIC50", "absolute_error"]].to_dict(orient="records"),
        "reading": ("scaffold 분할(주 지표)에서 3개 seed 모두 RF−Dummy 차이의 95% 구간이 "
                    "0 을 포함한다. 평균 예측 대비 우위가 확정되지 않았다. "
                    "random 분할 seed 42 는 구간 상한이 −0.0047 로 0 을 넘지 않는데, "
                    "분할 방식이 결론을 바꾼다는 뜻이다. scaffold 분할이 더 엄격하다"),
        "source": "reports/baseline_pilot_20261020_v2/",
    }

    m2_metrics = pd.read_csv(ROOT / "reports/dmpnn_pilot22_20261021_v2/dmpnn_metrics.csv")
    m2_paired = pd.read_csv(ROOT / "reports/dmpnn_pilot22_20261021_v2/dmpnn_paired_comparison.csv")
    m2_sum = read_json(ROOT / "reports/dmpnn_pilot22_20261021_v2/dmpnn_scoring_summary.json")
    out["M2"] = {
        "name": "D-MPNN 비교 (Chemprop v1.6.1)",
        "metrics": m2_metrics.to_dict(orient="records"),
        "paired": m2_paired.to_dict(orient="records"),
        "summary": m2_sum,
        "reading": ("paired 비교 12개 중 11개의 95% 구간이 0 을 포함한다. "
                    "D-MPNN 이 Dummy·RF 와 구별되지 않았다. 예측 표준편차가 "
                    "관측 표준편차보다 훨씬 작아 사실상 상수에 가까운 출력이었다"),
        "source": "reports/dmpnn_pilot22_20261021_v2/",
    }

    m3 = read_json(ROOT / "reports/sampl_repro_20261021_v2/sampl_repro_result.json")
    out["M3"] = {
        "name": "SAMPL logP 축소 재현 (Heid 2024)",
        "raw": m3,
        "reading": ("세 세트 모두 저자 보고값이 우리 측정의 95% 부트스트랩 구간 안에 들어왔다. "
                    "구별되지 않는다는 뜻이고, 축소 조건이므로 동일 조건 재현이 아니다"),
        "source": "reports/sampl_repro_20261021_v2/",
    }

    m5 = read_json(ROOT / "reports/agent_eval_20261021_final_openai/summary.json")
    m5_mini = read_json(ROOT / "reports/agent_eval_20261021_final_openai_mini/summary.json")
    m5_rule = read_json(ROOT / "reports/agent_eval_20261021_final_v2/summary.json")
    out["M5"] = {
        "name": "도구 호출 Agent 평가 (final 8문항 · 6축)",
        "policies": [
            {"policy": "규칙 기반", "model": None,
             "all_passed": m5_rule["n_all_passed"], "n": m5_rule["n_questions"],
             "per_axis": m5_rule["per_axis_passed"]},
            {"policy": "LLM", "model": m5["policy"]["model"],
             "all_passed": m5["n_all_passed"], "n": m5["n_questions"],
             "per_axis": m5["per_axis_passed"]},
            {"policy": "LLM", "model": m5_mini["policy"]["model"],
             "all_passed": m5_mini["n_all_passed"], "n": m5_mini["n_questions"],
             "per_axis": m5_mini["per_axis_passed"]},
        ],
        "reading": ("규칙 기반이 점수가 높았지만 'LLM 보다 낫다'고 일반화하지 않는다. "
                    "질문 14개를 규칙 정책 설계자와 같은 사람이 만들었고, 규칙 정책은 "
                    "도구 4개 밖으로 나갈 수 없으며 표본이 8문항이다. "
                    "LLM 의 약점은 termination(언제 멈출지) 한 축에 몰렸다"),
        "source": "reports/agent_eval_20261021_final*/",
    }

    m6 = read_json(ROOT / "reports/serving_m6_20261021/verification.json")
    m6c = read_json(ROOT / "reports/serving_m6_cloud_20261022/cloud_verification.json")
    out["M6"] = {
        "name": "컨테이너 추론 API와 클라우드 실행",
        "container": {
            "verdicts": m6["verdicts"],
            "latency": m6["results"]["V5_latency"],
            "image_size_mb": m6["image"]["size_mb"],
        },
        "cloud": {
            "provider": m6c["provider"],
            "region": m6c["region"],
            "verdicts": m6c["verdicts"],
            "latency": {
                "client_round_trip_ms": m6c["results"]["C5_latency"]["client_round_trip_ms"],
                "server_process_ms": m6c["results"]["C5_latency"]["server_process_ms"],
                "network_and_overhead_p50_ms":
                    m6c["results"]["C5_latency"]["network_and_overhead_p50_ms"],
            },
            "cold_start": {
                "run1_ms": m6c["results"]["C3_cold_start"]["prior_measurement"]
                           ["first_request_round_trip_ms"],
                "run1_model_load_s": m6c["results"]["C3_cold_start"]["prior_measurement"]
                                     ["model_load_seconds"],
                "run2_ms": m6c["results"]["C3_cold_start"]["first_request_round_trip_ms"],
                "run2_model_load_s": m6c["results"]["C3_cold_start"]["model_load_seconds"],
            },
            "runtime": m6c["results"]["C2_model_identity"]["runtime"],
            "pre_registration_misses":
                m6c["results"]["pre_registration_vs_actual"]["expectations_not_met"],
        },
        "reading": ("로컬 arm64 와 Cloud Run amd64 의 예측이 소수 3자리까지 일치했다. "
                    "다만 같은 코드·모델·라이브러리 버전으로 클라우드가 3.5~5.9배 느렸다. "
                    "원인을 gVisor 샌드박스 하나로 단정하지 않는다 — CPU·플랫폼·샌드박스가 "
                    "섞여 있고 분리 측정하지 않았다"),
        "source": "reports/serving_m6_20261021/, reports/serving_m6_cloud_20261022/",
    }
    return out


# --------------------------------------------------------------------------- #
# 5) 적용 범위 판정
# --------------------------------------------------------------------------- #

def build_applicability() -> dict:
    ood = read_json(ROOT / "reports/serving_m6_20261021/out_of_domain_observation.json")
    pred_manifest = read_json(ROOT / "artifacts/agent_predictor_20261021/manifest.json")
    return {
        "model": {
            "kind": "RandomForest (Morgan r=2, 2048bit, chirality)",
            "model_sha256": pred_manifest["model_sha256"],
            "n_training_molecules": pred_manifest["n_training_molecules"],
            "n_training_scaffolds": pred_manifest["n_training_scaffolds"],
            "label_range": pred_manifest["label_range"],
            "label_std": pred_manifest["label_std"],
            "mandatory_caveats": pred_manifest["mandatory_caveats"],
        },
        "rules": {
            "scaffold_in_training": "질의 분자의 Murcko scaffold 가 학습 12개에 있는가",
            "max_tanimoto_threshold": 0.5,
            "label_range_check": "예측값이 학습 라벨 범위 안인가",
            "note": "세 기준은 거친 지표다. 통과했다고 예측이 맞다는 뜻은 아니다",
        },
        "out_of_domain": ood,
        "source": "reports/serving_m6_20261021/out_of_domain_observation.json",
    }


# --------------------------------------------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    m = pd.read_parquet(FULL / "measurements_joined.parquet")
    a = pd.read_parquet(FULL / "assays.parquet")
    d = pd.read_parquet(FULL / "documents.parquet")

    print(f"전체 측정 {len(m)}건 / assay {len(a)}개 / 문헌 {len(d)}개 읽음")

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "project": "EGFR Evidence Lab",
        "target": {"chembl_id": "CHEMBL203", "organism": "Homo sapiens",
                   "endpoint": "IC50", "label": "pIC50"},
        "data_snapshot": "ChEMBL 수집 2026-10-20 (data/interim/chembl_full_20261020)",
        "honesty": {
            "no_invented_numbers": "모든 수치는 실제 산출물에서 읽거나 실제 데이터에 필터를 적용해 계산했다",
            "funnel_is_a_reconstruction": "퍼널은 사후 재구성이며 실제 정제 과정의 재현이 아니다",
            "model_not_validated": ("이 모델은 M1 교차검증에서 평균 예측(Dummy)보다 낫다고 "
                                    "확정되지 않았다. 적용 범위 밖에서는 사실상 상수를 돌려준다"),
            "scope": "pilot22 — 22건·12 scaffold·단일 문헌·단일 assay 의 정상형 생화학 IC50",
        },
        "funnel": build_funnel(m),
        "context": build_context(m, a, d),
        "cohort_chain": build_cohort_chain(m, d),
        "metrics": build_metrics(),
        "applicability": build_applicability(),
    }

    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "portfolio_data.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    size_kb = path.stat().st_size / 1024
    print(f"저장: {path}  ({size_kb:.0f} KB)")

    print("\n=== 퍼널 ===")
    for s in payload["funnel"]["steps"]:
        print(f"  {s['step']}. {s['label']:22s} 측정 {s['measurements']:6d}  "
              f"분자 {s['molecules']:5d}  assay {s['assays']:4d}  문헌 {s['documents']:4d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
