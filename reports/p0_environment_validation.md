# P0 실행 환경과 의존성 고정 검증

검증일: 2026-10-20 (Asia/Seoul). **P0 실행 의존성 설치·버전 고정·기능 확인·같은 Mac의 새 가상환경 재설치를 완료했다.** 전체 데이터 수집·과학적 정제·모델 학습은 아직 수행하지 않았다.

## 환경과 범위

기존 `.venv`를 유지했다. Python 3.12.14, macOS 26.5.2, arm64이며 설치 전에는 pip 25.0.1만 존재했다. uv 0.12.21로 PyPI의 정식 릴리스와 현재 플랫폼용 wheel을 해결하고 SHA-256을 포함한 requirements 파일을 만들었다. prerelease는 허용하지 않았고 소스 빌드 대신 wheel을 사용했다.

| P0 직접 패키지 | 설치·고정 버전 | 검사한 역할 |
|---|---|---|
| httpx | 0.28.1 | 요청 인코딩·JSON·실제 HTTPS |
| numpy | 2.5.4 | RDKit fingerprint의 배열 변환 |
| pandas | 3.0.6 | nullable 자료형·CSV·Parquet |
| rdkit | 2026.9.1 | 구조 파싱·입체정보·fingerprint·scaffold |
| pyarrow | 26.0.0 | Parquet 저장·읽기 |

간접 의존성을 포함해 총 14개 패키지를 고정했다. 전체 목록은 [lock](../requirements/p0-py312-macos-arm64.txt)과 아래 JSON에 있다. Pillow는 RDKit의 간접 의존성으로 설치됐고, PDF용 ReportLab·pypdf는 이번 P0 설치에 포함하지 않았다. SciPy·scikit-learn·Chemprop·PyTorch·RAG·Agent·클라우드 의존성도 아직 설치·검증하지 않았다.

## 검증 결과

| 검사 | 결과 | 증거 |
|---|---|---|
| 기본 환경·기능 검사 | 11항목 모두 통과 | [JSON](p0_environment_validation.json) |
| 실제 ChEMBL HTTPS를 포함한 검사 | 12항목 모두 통과 | [JSON](p0_environment_online_validation.json) |
| 빈 가상환경 재설치 후 같은 검사 | 11항목 모두 통과 | [JSON](p0_environment_rebuild_validation.json) |
| 기존 단위·정책 테스트 | 3개 통과 | unittest 실행 |
| 기존 설정 검사 | 통과 | check-config 실행 |
| 이전 ChEMBL 소량 응답 재검증 | 12항목 통과 | 저장한 2026-10-19 원 응답 검사 |

기능 검사 내용:

1. Python 3.12·macOS arm64·가상환경과 lock의 패키지 버전 일치.
2. `pip check`의 의존성 충돌 없음.
3. 5개 직접 패키지 import 성공.
4. HTTPX의 모의 GET 요청·쿼리 인코딩·JSON 해석.
5. 합성 3행을 Parquet·CSV로 저장하고 읽어 값·결측·자료형 보존 확인. CSV는 읽을 때 자료형을 명시했다.
6. RDKit 정상 구조 파싱과 잘못된 SMILES 거부.
7. 입체이성질체 2개를 isomeric SMILES로 구분.
8. Morgan fingerprint 생성·NumPy 배열 연동·자기 유사도 1 확인.
9. toluene 예시에서 Murcko scaffold가 benzene 골격으로 계산되는지 확인.
10. 온라인 모드에서 HTTPS 인증서 검증을 유지한 ChEMBL 상태·CHEMBL203 조회. ChEMBL_37, release 날짜 2026-05-01, 인간 EGFR 표적을 확인했다. 측정 자료 전체 수집은 실행하지 않았다.

위 설명은 관련 기능을 묶은 목록이며 검사 항목 수와 일대일 대응하지 않는다. JSON의 `checks` 배열이 정확한 항목별 결과다. 해시와 버전 일치는 파일·환경 재현성 검사이며 데이터의 과학적 적격성을 보증하지 않는다. fingerprint 반경·길이와 scaffold 예시는 기능 확인용으로, 모델링 정책을 확정한 것이 아니다.

## 재설치 검증의 의미와 한계

기존 환경과 별개인 `tmp/p0-rebuild-20261020`을 새로 만들고, 동일 lock과 로컬 wheel 캐시로 오프라인 설치했다. 설치된 14개 버전과 기능 검사 결과가 일치했다. 같은 Mac·같은 Python 3.12.14에서 검증했으며, 다른 운영체제·아키텍처의 재현성을 주장하지 않는다.

현재 Python의 base 경로는 Codex 번들 런타임이다. 다른 컴퓨터에서는 Python 3.12를 준비해 가상환경을 새로 만들고 lock으로 패키지를 설치한다. `.venv` 디렉터리를 통째로 복사해 옮기지 않는다. Python·pip·uv 자체와 프로젝트 빌드 도구는 이 실행 패키지 lock과 별도로 관리한다.

## 재실행과 다음 작업

[설치·재생성 명령](../requirements/README.md)과 [검사 스크립트](../scripts/check_p0_environment.py)를 참고한다. 기본 검사는 네트워크를 사용하지 않고 합성 데이터를 임시 폴더에서 검사·정리한다. `--online`을 지정할 때만 실제 API 2개를 조회한다.

다음 작업은 **전체 수집기 구현**이다. 검증한 httpx·pandas·RDKit·pyarrow를 사용하되, 기존 소량 탐색 스크립트를 전체 수집이 끝난 것처럼 취급하지 않는다. 페이지 누락·재시작·버전 변경·식별자 중복·연결 누락 검사를 구현한 뒤 실제 수집·감사로 진행한다.

공식 참고: [HTTPX](https://www.python-httpx.org/), [RDKit 설치](https://www.rdkit.org/docs/Install.html), [PyArrow 설치·Python 호환성](https://arrow.apache.org/docs/python/install.html), [uv 고정 파일](https://docs.astral.sh/uv/pip/compile/). 프로젝트의 호환성 결론은 문서 설명뿐 아니라 위 실제 실행 결과에 근거한다.
