"""평가 기능의 자리. 실제 구현은 다른 모듈에 있다.

이 패키지를 따로 두기로 계획했지만, 실제로는 아래 위치에 구현했다.
빈 패키지를 남기는 이유는 계획과 실제 위치를 함께 기록하기 위해서다.

* 누출 검사·scaffold 분할·오차 분석 → `egfr_lab.modeling.baseline`
* paired cluster 부트스트랩 → `egfr_lab.modeling.baseline.paired_cluster_ci`
* 지표 계산 → `egfr_lab.modeling.baseline.metrics`
* Agent 근거 평가 → `scripts/run_agent_eval.py` 의 `score()`
* 서비스 검증 → `scripts/verify_serving_m6.py`, `scripts/verify_serving_cloud_m6.py`
"""
