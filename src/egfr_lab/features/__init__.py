"""분자 특징 생성의 자리. 실제 구현은 다른 모듈에 있다.

이 패키지를 따로 두기로 계획했지만, 실제로는 아래 위치에 구현했다.

* Morgan fingerprint·Murcko scaffold → `egfr_lab.modeling.baseline`
* 서비스·Agent 쪽 특징 생성과 적용 범위 판정 →
  `egfr_lab.agent.tools.ActivityPredictor._featurize`

두 경로가 같은 설정(radius 2 · 2048bit · includeChirality)을 쓰도록
artifact 의 manifest 에서 값을 읽는다. 전처리를 두 번 구현하면
두 경로의 출력이 갈라지기 때문이다.
"""
