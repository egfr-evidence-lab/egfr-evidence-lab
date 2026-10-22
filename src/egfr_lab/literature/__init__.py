"""문헌 조회의 자리. 실제 구현은 Agent 도구에 있다.

이 패키지를 따로 두기로 계획했지만, 실제로는 아래 위치에 구현했다.

* Europe PMC 검색 → `egfr_lab.agent.tools.search_literature`
* DOI·PMID 서지와 전문 접근 가능성 → `egfr_lab.agent.tools.fetch_evidence`
* 접근 차단 증거 수집 → `scripts/fetch_scope_evidence.py` 등

BM25·임베딩 기반 검색은 실행하지 않았다. 현재 범위에서는 정확한
식별자 조회로 충분했고, 검색 품질을 평가할 질의 집합을 만들지 않았다.
"""
