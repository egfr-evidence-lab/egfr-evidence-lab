# EGFR Evidence Lab

ChEMBL EGFR 공개 실험 데이터로 화합물 활성을 예측하고, 실험·변이·문헌 근거를 추적하는 연구 포트폴리오 프로젝트입니다.

현재 단계는 **근거 조사, 프로젝트 설계와 최소 실행 뼈대**입니다. 데이터 수집, 모델 학습, 논문 성능 재현, RAG/Agent, 클라우드 배포는 아직 수행하지 않았습니다. 회사 내부 기술 스택을 재현하는 프로젝트라는 의미도 아닙니다.

**새 터미널·다른 세션에서 이어갈 때는 [HANDOFF.txt](HANDOFF.txt)를 먼저 읽으세요.** 실행 명령, 현재 구현 상태, 다음 데이터 감사 작업과 새 세션용 시작 요청을 정리했습니다.

## 도메인 공부 자료와 VS Code

- **[한국어 도메인 학습 PDF - 14쪽](output/pdf/egfr_domain_study_guide_ko.pdf)**: EGFR·분자 구조·IC50·변이·ChEMBL·정제 연습·신약개발 맥락·문헌 읽기·문제 해설·참고문헌.
- [PDF 원고](docs/06_domain_study_guide.md) / [생성 스크립트](scripts/build_domain_guide.py).
- [VS Code 워크스페이스](egfr-evidence-lab.code-workspace)를 열면 `.venv/bin/python` 환경과 테스트·설정 점검 task를 사용할 수 있습니다. Python 확장 설치가 필요할 수 있습니다.

새로 clone한 환경에서는 Python 3.11 또는 3.12로 가상환경을 먼저 만듭니다. 현재 로컬 뼈대는 Python 3.12 가상환경으로 점검했습니다.

```bash
python3.12 -m venv .venv
PYTHONPATH=src .venv/bin/python -m egfr_lab check-config
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

PDF를 다시 만들려면 별도 PDF 의존성과 한글을 포함한 임베딩 가능한 TTF가 필요합니다. 폰트 파일은 저장소에 포함하지 않았습니다.

```bash
.venv/bin/python -m pip install '.[pdf]'
.venv/bin/python scripts/build_domain_guide.py --font /path/to/Korean.ttf
```

## 문서 읽는 순서

1. [프로젝트 설계와 데이터·평가 기준](docs/01_blueprint.md)
2. [바이오·메디컬 학습 가이드](docs/02_bio_medical_primer.md)
3. [기술 스택: 선택 이유·근거·검증](docs/03_tech_stack.md)
4. [논문 재현 범위와 실험 기록](docs/04_reproduction.md)
5. [출처와 인용 목록](docs/05_references.md)

## 실행 가능한 부분

권장 개발 환경은 Python 3.11 또는 3.12입니다. 아래는 표준 라이브러리만 사용하는 설정 점검과 정확한 IC50 단위 변환 명령입니다. 네트워크 요청이나 학습은 실행하지 않습니다. `python`은 프로젝트 가상환경의 인터프리터를 사용하세요.

```bash
PYTHONPATH=src python -m egfr_lab check-config
PYTHONPATH=src python -m egfr_lab plan
PYTHONPATH=src python -m egfr_lab convert-ic50 --value 10 --unit nM
PYTHONPATH=src python -m unittest discover -s tests -v
```

10 nM의 변환 결과는 pIC50=8입니다. `>10 nM` 같은 부등호 측정은 정확값 회귀의 정답으로 변환하지 않습니다.

ML/DL 의존성 후보는 `pyproject.toml`에 단계별로 나누었습니다. **현재 설치·호환성 검증 및 lock 파일 생성은 하지 않았습니다.** 설치 단계에서 Python 3.11 환경을 따로 만들고 의존성을 검증·고정해야 합니다. 재현용 구버전 Chemprop은 주 프로젝트와 환경을 분리합니다.

## 계획된 구조

```text
configs/project.json       # 표적, 정제·평가 정책, 단계 상태
data/raw/                  # 원 응답·버전·수집 매니페스트
data/interim/              # 실험·변이 검토표, 정제 제외 사유
data/processed/            # 학습 표와 고정 분할
src/egfr_lab/
  config.py                # 구현: 설정 점검
  labels.py                # 구현: 정확값 IC50 → pIC50
  data/                    # 계획: 수집·정제·데이터 감사
  features/                # 계획: 분자 정규화·fingerprint·scaffold
  modeling/                # 계획: 기준 모델·RF·D-MPNN
  evaluation/              # 계획: 누수 점검·오차·통계·문헌 평가
  literature/              # 계획: 문헌 메타데이터·검색·인용
  agent/                   # 계획: 제한된 도구 선택·상태 관리
artifacts/                 # 모델과 실행 매니페스트
reports/                   # 데이터 감사·평가·모델 카드·재현 보고서
deployment/                # 배포 계획, 실제 리소스 생성 없음
```

빈 기능을 성공한 것처럼 반환하는 예측·검색 데모는 포함하지 않았습니다. 데이터와 실험 결과는 이후 실제 작업으로 채웁니다.

ChEMBL 원 데이터의 공식 안내는 CC BY-SA 3.0입니다. 데이터를 공개할 때 출처·release·가공 내용·라이선스를 함께 기록합니다. 논문 원문은 별도 이용 조건을 확인합니다. [ChEMBL 공식 라이선스](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/general-questions)
