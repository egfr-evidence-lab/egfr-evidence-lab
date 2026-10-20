# 자동 감사 구현·실행 기록

실행일: 2026-10-20. 정책 `conservative-screen-v1`.

`src/egfr_lab/data/audit.py`와 `egfr_lab audit` CLI를 추가했다. 완전 수집 상태와 원 응답·분석 테이블 검증을 통과한 자료만 처리한다. 검증 후 읽은 입력 해시와 수집 매니페스트가 변하지 않았는지도 확인한다. 원자료를 수정하지 않으며 기존 결과·수동 검토표는 덮어쓰지 않는다.

실제 실행:

```bash
PYTHONPATH=src .venv/bin/python -m egfr_lab audit data/raw/chembl_full_20261020
.venv/bin/python scripts/check_data_audit.py data/interim/audit_chembl_full_20261020 --output reports/data_audit_validation.json
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -q
PYTHONPATH=src .venv/bin/python -m egfr_lab check-config
git diff --check
```

결과:

- 전체 측정 26,600건, assay 2,425개, 분자 14,776개를 검사했다.
- CSV 6개, 자동 후보 측정 264건, 변이별 합계와 전체 행 수를 대조했다.
- 산출물 9개와 입력·정책 코드·수집 매니페스트 해시를 확인했다.
- 후보 행을 전체 감사표에서 다시 선택해 내용 전체를 대조했다. 라벨은 표준 농도로 독립 재계산했다.
- 수동 결정란은 모두 빈칸이며 `training_ready=false`, `manual_review_completed=0`이다.
- 기존 테스트 19개와 새 감사 테스트 9개, 총 28개 통과했다.
- 새 테스트는 정상형 오추론, 변이 표기 충돌, B/9 코드만으로 생화학 판정, 부등호·질량 농도 라벨화, 품질·중복 플래그 혼입, 입체 통합·자동 탈염, 맥락 간 반복값 혼합, 기존 검토표 덮어쓰기를 방지한다.
- 설정 검사와 공백 오류 검사도 통과했다. 모델 학습은 실행하지 않았다.

검사기는 자동 감사 직후의 결과를 확인하는 도구다. 사람이 검토표를 작성하면 해시가 달라지므로 감사 초안은 보존하고 작업 사본을 별도로 만든다. 미래의 검토 반영·확정 코호트 생성은 별도 기능으로 추가해야 한다.

정책 문구를 다듬는 과정의 앞선 자동 실행 결과 2개는 출력 해시가 그대로인지 확인하고 `tmp/audit_first_pass_20261020/`, `tmp/audit_second_pass_20261020/`에 보존했다. 최신 결과는 기본 감사 폴더이며 입력·코드·출력 해시를 최종 검증했다. 모든 데이터 폴더와 임시 파일은 Git에서 제외된다.

제한: 이 검사는 과학적 분류의 정확도, 실험 간 동질성, 원문 검토 완료를 보증하지 않는다. 자동 후보를 최종 학습 데이터로 취급하지 않는다.
