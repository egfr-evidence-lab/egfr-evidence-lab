# P0 패키지 버전 고정과 재설치

검증일: 2026-10-20. 원본 선언은 `pyproject.toml`의 `p0` extra이며, 고정 파일은 `p0-py312-macos-arm64.txt`다.

## 적용 범위

- 확인한 환경: Python **3.12.14**, macOS **26.5.2**, Apple Silicon **arm64**.
- P0 직접 의존성: httpx, pandas, numpy, rdkit, pyarrow.
- 직접·간접 의존성 총 14개를 정확 버전과 SHA-256으로 고정했다.
- 이 파일은 현재 플랫폼의 P0 실행 의존성용이다. Linux·Windows·Intel Mac·다른 Python 버전의 호환성을 검증한 공통 lock이 아니다.
- Python 인터프리터, pip, uv와 프로젝트 빌드 도구는 이 패키지 lock에 포함되지 않는다. 이번 검증의 pip는 25.0.1, lock 생성 도구 uv는 0.12.21이다.
- 프로젝트 자체를 설치한 lock이 아니다. 현재 소스 CLI는 기존처럼 `PYTHONPATH=src`로 실행한다.

## 기존 환경에 설치

프로젝트 루트에서 실행한다. 시스템 Python에 설치하지 않는다.

```bash
.venv/bin/python -m pip install --require-hashes --only-binary=:all: --index-url https://pypi.org/simple -r requirements/p0-py312-macos-arm64.txt
.venv/bin/python -m pip check
.venv/bin/python scripts/check_p0_environment.py
```

이번 실제 설치에는 다음 uv 명령을 사용했다. pip 방식과 같은 requirements 형식을 사용하며, 두 방식 모두 해시 검증을 지정한다.

```bash
uv pip install --python .venv/bin/python --require-hashes --only-binary :all: --default-index https://pypi.org/simple --cache-dir tmp/uv-cache -r requirements/p0-py312-macos-arm64.txt
```

선택적으로 실제 HTTPS 통신을 확인한다. 기본 검사는 모의 HTTP 응답과 합성 데이터만 사용해 네트워크를 호출하지 않는다.

```bash
.venv/bin/python scripts/check_p0_environment.py --online --output reports/p0_environment_online_validation.json
```

## 새 환경에서 복원

Python 3.12를 준비하고 비어 있는 새 경로에 가상환경을 만든다. 기존 `.venv`를 지우거나 덮어쓸 필요는 없다.

```bash
python3.12 -m venv tmp/p0-fresh-env
tmp/p0-fresh-env/bin/python -m pip install --require-hashes --only-binary=:all: --index-url https://pypi.org/simple -r requirements/p0-py312-macos-arm64.txt
tmp/p0-fresh-env/bin/python scripts/check_p0_environment.py --output tmp/p0-fresh-env-validation.json
```

이번 재설치 검증은 새 `tmp/p0-rebuild-20261020` 가상환경에 uv의 로컬 wheel 캐시를 사용해 **오프라인으로** 설치했다. 14개 패키지의 버전 일치·pip check·동일 기능 검사 11항목을 통과했다. 다른 컴퓨터나 운영체제에서 독립 재검증한 것은 아니다.

## 고정 파일 재생성

같은 Python·플랫폼에서 uv 0.12.21로 생성했다. 일반적인 작업 재개에는 재생성보다 기존 고정 파일로 설치하는 방식을 사용한다. 패키지를 의도적으로 갱신할 때 변경된 버전과 검증 결과를 함께 검토한다.

```bash
uv pip compile pyproject.toml --extra p0 --python .venv/bin/python --python-platform aarch64-apple-darwin --generate-hashes --only-binary :all: --prerelease disallow --default-index https://pypi.org/simple --cache-dir tmp/uv-cache --no-python-downloads --output-file requirements/p0-py312-macos-arm64.txt
```

상세 결과: [실행 환경 검증 보고서](../reports/p0_environment_validation.md).

공식 근거: [uv의 requirements 고정 방식](https://docs.astral.sh/uv/pip/compile/), [pip 해시 검사](https://pip.pypa.io/en/stable/topics/secure-installs/).

## P1 교육 실험 환경

P0 `.venv`와 별개로 `.venv-ml`을 Python 3.12.14에서 만들었습니다. macOS 26.5.2 arm64에서 scikit-learn 1.9.1·SciPy 1.18.1·RDKit 2026.9.1 등 직접·간접 패키지 27개를 설치했습니다. `pip check`, 실제 Dummy·RF 학습·저장·재로딩과 전체 테스트 43개를 통과했습니다.

`ml-py312-macos-arm64.freeze.txt`는 설치 버전 스냅샷입니다. P0 파일처럼 wheel 해시가 있는 lock이 아니며, 새 빈 환경 재설치·다른 플랫폼은 아직 검증하지 않았습니다. 복원이 필요한 경우 기존 환경을 덮어쓰지 않고 새 경로를 사용합니다.

```bash
python3.12 -m venv tmp/ml-fresh-env
tmp/ml-fresh-env/bin/python -m pip install -r requirements/ml-py312-macos-arm64.freeze.txt
tmp/ml-fresh-env/bin/python -m pip check
PYTHONPATH=src tmp/ml-fresh-env/bin/python -m unittest discover -s tests -v
```

현재 Mac의 검증 명령과 실습은 다음과 같습니다. 원 데이터·모델 파일은 Git 제외 대상이므로 새 clone에서 결과 검증을 하려면 해당 실행 산출물이 필요합니다.

```bash
PYTHONPATH=src .venv-ml/bin/python scripts/check_baseline_pilot.py
.venv-ml/bin/python scripts/practice_basics.py --lesson quiz
```

[실제 결과와 제한](../reports/apsel_review_and_baseline_ko.md), [학습·재실행 안내](../docs/11_baseline_practice_ko.md).
