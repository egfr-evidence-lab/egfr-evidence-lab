"""P0 의존성·통신·표 저장·분자 처리 환경을 작은 예제로 검증한다.

학습 코호트 정제나 모델 학습은 하지 않는다. --online을 지정할 때만
ChEMBL 상태와 표적을 소량 조회하며 HTTPS 인증서 검증을 유지한다.
"""

import argparse
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "requirements/p0-py312-macos-arm64.txt"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--online", action="store_true", help="ChEMBL 상태·표적의 실제 HTTPS 조회도 검사")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/p0_environment_validation.json",
                        help="검증 결과 JSON 경로")
    args = parser.parse_args()
    checks = []

    def run(name, action):
        try:
            detail = action()
            checks.append({"name": name, "passed": True, "detail": detail})
            print(f"통과: {name}", flush=True)
        except Exception as exc:
            checks.append({"name": name, "passed": False, "error": f"{type(exc).__name__}: {exc}"})
            print(f"실패: {name}: {exc}", flush=True)

    def runtime():
        if sys.version_info[:2] != (3, 12) or sys.platform != "darwin" or platform.machine() != "arm64":
            raise ValueError("현재 lock의 검증 대상은 Python 3.12·macOS arm64입니다.")
        if sys.prefix == sys.base_prefix:
            raise ValueError("프로젝트 또는 재설치 검증용 가상환경에서 실행하세요.")
        return {"python": platform.python_version(), "platform": platform.platform(),
                "machine": platform.machine(), "virtual_environment": True}

    lock_text = LOCK.read_text(encoding="utf-8")
    # Join continuation lines so that every exact requirement must carry a hash.
    logical_lines = lock_text.replace("\\\n", " ").splitlines()
    locked = {}
    for line in logical_lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.match(r"([A-Za-z0-9_.-]+)==([^\s;]+)", line)
        if not match or not re.search(r"--hash=sha256:[a-f0-9]{64}(?:\s|$)", line):
            raise ValueError("모든 잠금 항목은 정확 버전과 SHA-256을 포함해야 합니다.")
        locked[match.group(1)] = match.group(2)

    def versions():
        actual = {name: metadata.version(name) for name in locked}
        if actual != locked:
            raise ValueError({"expected": locked, "actual": actual})
        return actual

    def pip_check():
        result = subprocess.run([sys.executable, "-m", "pip", "check"], capture_output=True, text=True)
        if result.returncode:
            raise ValueError(result.stdout + result.stderr)
        return result.stdout.strip()

    run("Python·운영체제·가상환경", runtime)
    run("lock의 정확 버전과 설치 패키지 일치", versions)
    run("pip 의존성 충돌 검사", pip_check)

    try:
        import httpx
        import numpy as np
        import pandas as pd
        import pyarrow
        from rdkit import Chem, DataStructs, rdBase
        from rdkit.Chem import rdFingerprintGenerator
        from rdkit.Chem.Scaffolds import MurckoScaffold
    except ImportError as exc:
        checks.append({"name": "P0 패키지 import", "passed": False, "error": str(exc)})
    else:
        checks.append({"name": "P0 패키지 import", "passed": True,
                       "detail": ["httpx", "numpy", "pandas", "pyarrow", "rdkit"]})
        print("통과: P0 패키지 import", flush=True)

        def mock_http():
            def handler(request):
                if request.method != "GET" or dict(request.url.params) != {
                    "target_chembl_id": "CHEMBL203", "target_organism": "Homo sapiens", "limit": "2"
                }:
                    raise ValueError("요청 인코딩 또는 파라미터가 예상과 다릅니다.")
                return httpx.Response(200, json={"synthetic": True, "activities": [],
                                                 "page_meta": {"total_count": 0}})
            with httpx.Client(transport=httpx.MockTransport(handler), timeout=30) as client:
                response = client.get("https://www.ebi.ac.uk/chembl/api/data/activity.json", params={
                    "target_chembl_id": "CHEMBL203", "target_organism": "Homo sapiens", "limit": 2})
                response.raise_for_status()
                if response.json().get("synthetic") is not True:
                    raise ValueError("JSON 해석 실패")
            return {"mode": "모의 통신; 네트워크 요청 없음", "query_encoding": True, "json_parsing": True}

        run("HTTPX 요청 인코딩·JSON 해석", mock_http)

        # Synthetic records deliberately include a null and a censored measurement.
        frame = pd.DataFrame({"activity_id": pd.Series([1, 2, 3], dtype="Int64"),
                              "standard_relation": pd.Series(["=", ">", pd.NA], dtype="string"),
                              "standard_value": pd.Series([10, 1000, pd.NA], dtype="Float64"),
                              "canonical_smiles": pd.Series(["CCO", "c1ccccc1", pd.NA], dtype="string")})
        with tempfile.TemporaryDirectory(prefix="egfr-p0-smoke-") as temporary:
            folder = Path(temporary)

            def parquet_roundtrip():
                path = folder / "synthetic.parquet"
                frame.to_parquet(path, engine="pyarrow", index=False)
                recovered = pd.read_parquet(path, engine="pyarrow")
                pd.testing.assert_frame_equal(frame, recovered)
                return {"rows": len(frame), "nulls_preserved": True, "dtypes_preserved": True,
                        "synthetic": True, "engine": "pyarrow", "version": pyarrow.__version__}

            def csv_roundtrip():
                path = folder / "synthetic.csv"
                frame.to_csv(path, index=False)
                recovered = pd.read_csv(path, dtype=frame.dtypes.to_dict())
                pd.testing.assert_frame_equal(frame, recovered)
                return {"rows": len(frame), "nulls_preserved": True, "dtype_schema_explicit": True,
                        "synthetic": True}

            run("pandas·PyArrow Parquet 왕복 저장", parquet_roundtrip)
            run("pandas CSV 왕복 저장", csv_roundtrip)

        def structure_parsing():
            molecule = Chem.MolFromSmiles("CCO")
            with rdBase.BlockLogs():
                bad = Chem.MolFromSmiles("this_is_not_smiles")
            if molecule is None or molecule.GetNumAtoms() != 3 or bad is not None:
                raise ValueError("구조 파싱 또는 오류 구조 검출 실패")
            return {"valid_smiles": "CCO", "invalid_smiles_rejected": True,
                    "note": "파싱 기능 검사; 화학 정규화 정책 미확정"}

        def stereo():
            left = Chem.MolFromSmiles("F[C@H](Cl)Br")
            right = Chem.MolFromSmiles("F[C@@H](Cl)Br")
            strings = [Chem.MolToSmiles(m, isomericSmiles=True) for m in (left, right)]
            if strings[0] == strings[1]:
                raise ValueError("입체이성질체 표기가 사라졌습니다.")
            return {"distinct_isomeric_smiles": strings}

        def fingerprint():
            molecule = Chem.MolFromSmiles("CCO")
            generator = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
            bits = generator.GetFingerprint(molecule)
            array = np.zeros(2048, dtype=np.uint8)
            DataStructs.ConvertToNumpyArray(bits, array)
            if bits.GetNumBits() != 2048 or array.sum() == 0 or DataStructs.TanimotoSimilarity(bits, bits) != 1:
                raise ValueError("fingerprint 생성·배열 변환·자기 유사도 실패")
            return {"radius": 2, "bits": 2048, "on_bits": int(array.sum()),
                    "self_similarity": 1.0, "note": "환경 검사 예시; 모델링 설정 확정 아님"}

        def scaffold():
            result = MurckoScaffold.MurckoScaffoldSmiles(mol=Chem.MolFromSmiles("Cc1ccccc1"))
            if result != "c1ccccc1":
                raise ValueError(f"예상과 다른 골격: {result}")
            return {"input": "Cc1ccccc1", "scaffold": result,
                    "note": "분할 수행 아님; 비고리 분자 정책은 후속 작업"}

        run("RDKit 정상·오류 구조 파싱", structure_parsing)
        run("RDKit 입체정보 보존", stereo)
        run("Morgan fingerprint·NumPy 연동", fingerprint)
        run("Murcko scaffold 계산", scaffold)

        if args.online:
            def online():
                base = "https://www.ebi.ac.uk/chembl/api/data/"
                with httpx.Client(timeout=30, follow_redirects=True) as client:
                    status = client.get(base + "status.json")
                    status.raise_for_status()
                    target = client.get(base + "target/CHEMBL203.json")
                    target.raise_for_status()
                status_data, target_data = status.json(), target.json()
                if status_data.get("status") != "UP" or target_data.get("target_chembl_id") != "CHEMBL203":
                    raise ValueError("서버 상태 또는 표적 식별 불일치")
                if target_data.get("organism") != "Homo sapiens":
                    raise ValueError("표적 종 불일치")
                return {"mode": "실제 HTTPS; 인증서 검증 유지", "requests": [str(status.url), str(target.url)],
                        "chembl_db_version": status_data["chembl_db_version"],
                        "chembl_release_date": status_data["chembl_release_date"],
                        "target_chembl_id": target_data["target_chembl_id"],
                        "full_collection_performed": False}

            run("ChEMBL 실제 HTTPS 상태·표적 조회", online)

    result = {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "P0 실행 환경 검증; 전체 데이터 감사·정제·모델 학습은 미수행",
              "python": platform.python_version(), "platform": platform.platform(),
              "lock_file": str(LOCK.relative_to(ROOT)),
              "lock_sha256": hashlib.sha256(LOCK.read_bytes()).hexdigest(),
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "locked_packages": locked, "online_requested": args.online,
              "all_passed": all(c["passed"] for c in checks), "checks": checks}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"검증 {len(checks)}항목, 통과 {sum(c['passed'] for c in checks)}항목")
    print(f"결과 저장: {args.output}")
    if not result["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
