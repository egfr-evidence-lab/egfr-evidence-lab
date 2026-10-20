# P0 도메인·기술 학습 노트 PDF 검수

검수일: 2026-10-19. 산출물: `output/pdf/egfr_p0_domain_tech_ko.pdf`.

- 16쪽 A4 한국어 학습 자료. 표지·목차, 도메인, 실제 API 사례, 현재 IT 스택, 도입 계획, 문제 8개·해설, 참고문헌으로 구성.
- 원고의 수치와 현재 코드·API 검증 보고서 대조. 원자료 기록 수와 학습 표본 수, 표본 일관성 검사와 모델 성능 평가를 구분.
- 현재 사용한 Python 표준 라이브러리와 미도입 ML·RAG·Agent·클라우드 기술을 구분.
- 본문 오타·용어·단위·변환식·변이 표기 점검. 폰트가 지원하는 그리스 문자 μ로 단위를 통일.
- Poppler로 전체 16쪽 렌더링 후 이미지 검토. 표 열 너비와 API 예시 줄바꿈을 수정하고 재생성·재검토.
- pypdf 검사: 16쪽, 제목과 페이지 순서 일치, 링크 annotation 20개, 대체 문자·검은 사각형 없음.
- Poppler 단어 경계 검사: 페이지 여백 밖 텍스트 0건. 주요 데이터 수치·단위·식별자 추출 확인.
- 최종 PDF SHA-256: `cc2b025b9d70fd23aa403ca4cfdcd28c1438ceb525e6ad40c9e38cc002e24231`.
- 생성에는 Codex 번들 Python의 ReportLab·pypdf·Pillow와 시스템 Poppler를 사용. 프로젝트 `.venv`에 패키지를 추가하지 않음.
- 로컬 AppleGothic TTF를 사용했으며 폰트 파일은 저장소에 복사하지 않음. 다른 환경에서는 임베딩 가능한 한글 TTF를 준비해야 함.

원고: `docs/07_p0_domain_and_tech_notes.md`.

생성 스크립트: `scripts/build_p0_learning_guide.py --font <한글 TTF 경로>`.
