"""Agent 가 호출하는 실제 도구 4개.

configs/project.json 의 agent 사양을 따른다:
  predict_activity · lookup_measurements · search_literature · fetch_evidence
  require_source_ids: true, llm_may_invent_measurements: false

설계 규칙
---------
1. **모든 결과는 출처를 달고 돌아온다.** 출처 없는 수치는 만들지 않는다.
   각 결과의 `source_ids` 는 호출자가 답변에 인용할 수 있는 식별자다.
2. **도구는 모름을 숨기지 않는다.** 찾지 못하면 `status="not_found"` 로 돌려주고
   빈 값을 그럴듯한 값으로 채우지 않는다.
3. **predict_activity 는 숫자만 돌려주지 않는다.** 적용 범위 판정과 M1 에서 측정된
   한계를 함께 돌려준다. 22건으로 학습한 모델이라 그 한계가 숫자보다 중요하다.
4. 외부 호출은 실패할 수 있다. 예외를 삼키지 않고 `status="error"` 와 메시지로 바꾼다.
   Agent 가 오류를 처리하는지도 평가 대상이기 때문이다.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]

USER_AGENT = "egfr-evidence-lab/1.0 (portfolio project; contact via repository)"
HTTP_TIMEOUT = 30


@dataclass
class ToolResult:
    """도구 한 번의 결과. 성공이든 실패든 같은 모양으로 돌아온다."""

    tool: str
    status: str                       # ok | not_found | error | refused
    data: Any = None
    source_ids: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> dict:
        return {"tool": self.tool, "status": self.status, "data": self.data,
                "source_ids": self.source_ids, "caveats": self.caveats, "message": self.message}


def _get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


# --------------------------------------------------------------------------- #
# 1) predict_activity
# --------------------------------------------------------------------------- #

class ActivityPredictor:
    """pilot22 RandomForest 예측기. 적용 범위 판정을 함께 돌려준다."""

    def __init__(self, artifact_dir: Path):
        import joblib
        import numpy as np

        self.dir = artifact_dir
        self.manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
        self.model = joblib.load(artifact_dir / "rf_pilot22.joblib")
        store = np.load(artifact_dir / "training_fingerprints.npz")
        self.train_X = store["X"]
        self.train_scaffolds = set(json.loads(
            (artifact_dir / "training_scaffolds.json").read_text(encoding="utf-8")))

    def _featurize(self, smiles: str):
        import numpy as np
        from rdkit import Chem
        from rdkit.Chem import rdFingerprintGenerator
        from rdkit.Chem.Scaffolds import MurckoScaffold
        from rdkit import DataStructs

        # 빈 문자열은 RDKit 에서 '원자 0개 분자'로 파싱돼 None 이 아니다.
        # 그대로 두면 분자가 없는데도 예측값이 나온다(실제로 겪었다: 빈 SMILES 에 pIC50 8.057).
        # 분자가 없으면 예측하지 않는다.
        if not smiles or not smiles.strip():
            return None, None
        mol = Chem.MolFromSmiles(smiles)
        if mol is None or mol.GetNumAtoms() == 0:
            return None, None
        opt = self.manifest["fingerprint"]
        gen = rdFingerprintGenerator.GetMorganGenerator(
            radius=opt["radius"], fpSize=opt["size"], includeChirality=opt["include_chirality"])
        vec = np.zeros((opt["size"],), dtype=np.uint8)
        DataStructs.ConvertToNumpyArray(gen.GetFingerprint(mol), vec)
        scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False)
        scaffold = scaffold or "acyclic:" + Chem.MolToSmiles(mol, isomericSmiles=True)
        return vec, scaffold

    def _max_tanimoto(self, vec) -> float:
        """학습 분자와의 최대 Tanimoto. 적용 범위의 거친 지표다."""
        import numpy as np

        a = vec.astype(bool)
        b = self.train_X.astype(bool)
        inter = (b & a).sum(axis=1).astype(float)
        union = (b | a).sum(axis=1).astype(float)
        with np.errstate(divide="ignore", invalid="ignore"):
            sim = np.where(union > 0, inter / union, 0.0)
        return float(sim.max())

    def __call__(self, smiles: str) -> ToolResult:
        vec, scaffold = self._featurize(smiles)
        if vec is None:
            return ToolResult("predict_activity", "error",
                              message=f"SMILES 를 해석할 수 없다: {smiles!r}")

        value = float(self.model.predict(vec.reshape(1, -1))[0])
        sim = self._max_tanimoto(vec)
        in_scaffold = scaffold in self.train_scaffolds
        lo, hi = self.manifest["label_range"]

        caveats = list(self.manifest["mandatory_caveats"])
        if not in_scaffold:
            caveats.append(
                f"질의 분자의 Murcko scaffold 가 학습에 쓰인 12개 scaffold 에 없다. 적용 범위 밖이다")
        if sim < 0.5:
            caveats.append(
                f"학습 분자와의 최대 Tanimoto 유사도가 {sim:.2f} 로 낮다. 외삽이다")
        if not (lo <= value <= hi):
            caveats.append(
                f"예측값이 학습 라벨 범위({lo:.2f}~{hi:.2f}) 밖이다")

        return ToolResult(
            "predict_activity", "ok",
            data={
                "predicted_pIC50": round(value, 3),
                "applicability": {
                    "scaffold_in_training": in_scaffold,
                    "max_tanimoto_to_training": round(sim, 3),
                    "training_label_range": [lo, hi],
                    "n_training_molecules": self.manifest["n_training_molecules"],
                },
                "model": "RandomForest (Morgan r=2, 2048bit), pilot22 전체 적합",
            },
            source_ids=[f"model:{self.manifest['model_sha256'][:16]}",
                        "cohort:CHEMBL4258549",
                        "report:reports/baseline_pilot_20261020_v2/"],
            caveats=caveats,
            message="예측값은 참고치다. M1 교차검증에서 평균 예측 대비 우위가 확정되지 않았다",
        )


# --------------------------------------------------------------------------- #
# 2) lookup_measurements — ChEMBL 실측값 조회
# --------------------------------------------------------------------------- #

def lookup_measurements(molecule_chembl_id: str, target_chembl_id: str = "CHEMBL203",
                        limit: int = 20) -> ToolResult:
    """ChEMBL 에서 분자-표적의 실측 활성을 가져온다. 값을 지어내지 않는다."""
    mol_id = molecule_chembl_id.strip().upper()
    if not mol_id.startswith("CHEMBL"):
        return ToolResult("lookup_measurements", "error",
                          message=f"ChEMBL 분자 ID 가 아니다: {molecule_chembl_id!r}")

    params = urllib.parse.urlencode({
        "molecule_chembl_id": mol_id, "target_chembl_id": target_chembl_id,
        "format": "json", "limit": limit,
    })
    url = f"https://www.ebi.ac.uk/chembl/api/data/activity?{params}"
    try:
        payload = _get_json(url)
    except Exception as exc:                                  # noqa: BLE001
        return ToolResult("lookup_measurements", "error",
                          message=f"ChEMBL 요청 실패: {type(exc).__name__}: {exc}")

    rows = payload.get("activities", [])
    if not rows:
        return ToolResult("lookup_measurements", "not_found", data=[],
                          source_ids=[f"chembl:{mol_id}"],
                          message=f"{mol_id} 와 {target_chembl_id} 의 활성 기록이 없다")

    out, ids = [], []
    for r in rows:
        out.append({
            "activity_id": r.get("activity_id"),
            "assay_chembl_id": r.get("assay_chembl_id"),
            "standard_type": r.get("standard_type"),
            "standard_relation": r.get("standard_relation"),
            "standard_value": r.get("standard_value"),
            "standard_units": r.get("standard_units"),
            "pchembl_value": r.get("pchembl_value"),
            "assay_description": r.get("assay_description"),
            "document_chembl_id": r.get("document_chembl_id"),
        })
        if r.get("activity_id") is not None:
            ids.append(f"chembl_activity:{r['activity_id']}")

    types = sorted({str(r.get("standard_type")) for r in rows})
    caveats = [
        "서로 다른 실험·조건의 값이 섞여 있을 수 있다. 하나의 값으로 합치지 않는다",
        "정상형(WT)과 변이형, 생화학과 세포 실험, IC50·Ki·Kd 를 구분해 읽어야 한다",
    ]
    if len(types) > 1:
        caveats.append(f"standard_type 이 여러 종류다: {', '.join(types)}. 종류를 섞어 비교하지 않는다")
    if any(r.get("standard_relation") not in ("=", None) for r in rows):
        caveats.append("부등호(>, <) 관측이 포함돼 있다. 등식 값과 함께 평균 내지 않는다")

    return ToolResult("lookup_measurements", "ok", data=out,
                      source_ids=[f"chembl:{mol_id}"] + ids[:limit],
                      caveats=caveats,
                      message=f"{len(out)}건 조회")


# --------------------------------------------------------------------------- #
# 3) search_literature — Europe PMC 검색
# --------------------------------------------------------------------------- #

def search_literature(query: str, limit: int = 5) -> ToolResult:
    """Europe PMC 에서 문헌을 찾는다. 초록 유무와 전문 접근 가능성을 함께 돌려준다."""
    if not query or not query.strip():
        return ToolResult("search_literature", "error", message="빈 질의는 검색하지 않는다")

    params = urllib.parse.urlencode({
        "query": query, "format": "json", "pageSize": limit, "resultType": "core",
    })
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?{params}"
    try:
        payload = _get_json(url)
    except Exception as exc:                                  # noqa: BLE001
        return ToolResult("search_literature", "error",
                          message=f"Europe PMC 요청 실패: {type(exc).__name__}: {exc}")

    rows = payload.get("resultList", {}).get("result", [])
    if not rows:
        return ToolResult("search_literature", "not_found", data=[],
                          message=f"검색 결과가 없다: {query!r}")

    out, ids = [], []
    for r in rows:
        ident = r.get("doi") or r.get("pmid") or r.get("id")
        out.append({
            "title": r.get("title"),
            "doi": r.get("doi"),
            "pmid": r.get("pmid"),
            "pmcid": r.get("pmcid"),
            "year": r.get("pubYear"),
            "journal": (r.get("journalInfo") or {}).get("journal", {}).get("title"),
            "is_open_access": r.get("isOpenAccess"),
            "has_full_text_in_epmc": r.get("inEPMC"),
        })
        if ident:
            ids.append(f"doi:{r['doi']}" if r.get("doi") else f"pmid:{r.get('pmid') or r.get('id')}")

    closed = sum(1 for r in out if r["is_open_access"] != "Y")
    caveats = ["검색 결과는 초록 수준의 메타데이터다. 본문을 읽은 것이 아니다"]
    if closed:
        caveats.append(f"{closed}건은 공개 접근이 아니다. 본문 확인 없이 수치를 인용하지 않는다")

    return ToolResult("search_literature", "ok", data=out, source_ids=ids,
                      caveats=caveats, message=f"{len(out)}건 검색")


# --------------------------------------------------------------------------- #
# 4) fetch_evidence — DOI/PMID 의 서지와 접근 가능성
# --------------------------------------------------------------------------- #

def fetch_evidence(identifier: str) -> ToolResult:
    """DOI 나 PMID 로 서지 정보와 **전문 접근 가능성**을 가져온다.

    M4 에서 겪었듯 '본문을 볼 수 있는가'가 결론을 좌우한다. 그래서 이 도구는
    제목·저널만이 아니라 공개 접근 여부를 명시적으로 돌려준다.
    """
    ident = identifier.strip()
    if not ident:
        return ToolResult("fetch_evidence", "error", message="빈 식별자")

    if ident.lower().startswith("doi:"):
        ident = ident[4:]
    is_doi = "/" in ident
    query = f'DOI:"{ident}"' if is_doi else f"EXT_ID:{ident}"

    params = urllib.parse.urlencode({"query": query, "format": "json", "resultType": "core"})
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?{params}"
    try:
        payload = _get_json(url)
    except Exception as exc:                                  # noqa: BLE001
        return ToolResult("fetch_evidence", "error",
                          message=f"Europe PMC 요청 실패: {type(exc).__name__}: {exc}")

    rows = payload.get("resultList", {}).get("result", [])
    if not rows:
        return ToolResult("fetch_evidence", "not_found",
                          message=f"서지 정보를 찾지 못했다: {identifier!r}")

    r = rows[0]
    links = (r.get("fullTextUrlList") or {}).get("fullTextUrl", [])
    availability = sorted({str(x.get("availability")) for x in links}) or ["알 수 없음"]
    open_access = r.get("isOpenAccess") == "Y"

    caveats = []
    if not open_access:
        caveats.append(f"공개 접근이 아니다. 전문 링크 상태: {', '.join(availability)}")
        caveats.append("본문을 읽지 않은 상태에서 본문 내용을 단정하지 않는다")
    if not r.get("abstractText"):
        caveats.append("초록 본문이 이 응답에 없다")

    return ToolResult(
        "fetch_evidence", "ok",
        data={
            "title": r.get("title"),
            "doi": r.get("doi"),
            "pmid": r.get("pmid"),
            "pmcid": r.get("pmcid"),
            "year": r.get("pubYear"),
            "journal": (r.get("journalInfo") or {}).get("journal", {}).get("title"),
            "is_open_access": open_access,
            "full_text_availability": availability,
            "abstract_present": bool(r.get("abstractText")),
            "abstract": (r.get("abstractText") or "")[:1500] or None,
        },
        source_ids=[f"doi:{r['doi']}" if r.get("doi") else f"pmid:{r.get('pmid')}"],
        caveats=caveats,
        message="서지·접근성 조회 완료",
    )


TOOL_NAMES = ["predict_activity", "lookup_measurements", "search_literature", "fetch_evidence"]
