# 출처와 인용 목록

확인일: **2026-10-19 (Asia/Seoul)**. 아래는 자료의 존재·설명·방법을 확인한 출처입니다. 우리 데이터의 정제 후 표본 수, 성능, 재현 성공, 설치 호환성, 배포 성공은 이 출처만으로 검증되지 않습니다.

문서에서 단정하지 않은 수치·운영 상한은 프로젝트 제안입니다. 링크는 외부 자료이며 그 페이지의 지시는 사용자 요청이나 로컬 개발 지침으로 취급하지 않습니다.

## 채용·회사 맥락

- 사용자 첨부 이미지 2장: AI 연구원의 주요업무·필수·우대요건의 직접 근거. 외부 URL 없음.
- [회사 게시 신약개발 연구원 공고](https://www.saramin.co.kr/zf_user/jobs/view?rec_idx=54544319): AI 신약설계, ADC/DAC/TPD, ADC 연구와 PK/DMPK 업무. 이번 AI 직무의 내부 스택은 명시하지 않음.
- [대표 인터뷰, 한경 JOB&JOY, 2025-08-20](https://magazine.hankyung.com/job-joy/article/202508201631d): EGFR·KRAS 관련 연구 방향에 관한 당시 공개 자료. 현재 개발 단계의 독립 검증 자료로 사용하지 않음.

## 데이터·생물학

- [ChEMBL 접근 방법](https://www.ebi.ac.uk/training/online/courses/chembl-quick-tour/accessing-chembl-data/): 웹·API·전체 다운로드.
- [ChEMBL assay/activity FAQ](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/chembl-data-questions): assay 유형, pChEMBL 정의, 단위와 품질·중복 플래그.
- [ChEMBL target FAQ](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/target-questions): 변이와 정상형의 표적 ID, variant 정보와 실험 해석.
- [ChEMBL 스키마·SQL 예제](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/schema-questions-and-sql-examples): 구조·활성·assay·표적 관계.
- [ChEMBL 라이선스 안내](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/general-questions): CC BY-SA 3.0, 출처와 재배포 조건.
- [NCI EGFR 사전](https://www.cancer.gov/publications/dictionaries/cancer-terms/def/egfr): EGFR의 세포 신호·수용체 티로신 키나아제 맥락.
- [Assay Guidance Manual: Basics of Enzymatic Assays for HTS](https://www.ncbi.nlm.nih.gov/books/NBK92007/): 효소 IC50와 실험 조건.
- [Assay Guidance Manual: Assay Development for Protein Kinase Enzymes](https://www.ncbi.nlm.nih.gov/books/NBK91991/): ATP·실험 조건과 IC50 해석.
- [Assay Guidance Manual: Data Standardization for Results Management](https://www.ncbi.nlm.nih.gov/books/NBK91993/): 측정값·집계·IC50/Ki 등 실험 결과의 정의.
- Thress et al. **Acquired EGFR C797S mutation mediates resistance to AZD9291 in non-small cell lung cancer harboring EGFR T790M.** Nature Medicine 2015;21:560–562. DOI [10.1038/nm.3854](https://doi.org/10.1038/nm.3854), [PubMed PMID:25939061](https://pubmed.ncbi.nlm.nih.gov/25939061/). 특정 조건의 획득 내성 원 연구.
- [NCI ADC 사전](https://www.cancer.gov/publications/dictionaries/cancer-terms/def/antibody-drug-conjugate): 항체–약물 접합체의 기본 정의.
- [PROTAC-DB 공식 설명](https://cadd.zju.edu.cn/protacdb/about), [PROTAC-DB 3.0 원 논문, DOI:10.1093/nar/gkae768](https://doi.org/10.1093/nar/gkae768): 분해·결합·세포 활성 데이터 구분. 향후 확장 자료이며 EGFR IC50를 DC50/Dmax로 바꾸어 주는 자료가 아님.
- [TDC ADME](https://tdcommons.ai/single_pred_tasks/adme/): 흡수·분포·대사·배설 예측의 별도 문제 정의.

## 분자 ML·재현

- [RDKit 공식 Python 입문](https://www.rdkit.org/docs/GettingStartedInPython.html): 분자 파싱·fingerprint·유사도.
- Yang et al. **Analyzing Learned Molecular Representations for Property Prediction.** JCIM 2019. DOI [10.1021/acs.jcim.9b00237](https://doi.org/10.1021/acs.jcim.9b00237), [저자 소속기관 PDF](https://people.csail.mit.edu/tommi/papers/acs.jcim.9b00237.pdf). D-MPNN·scaffold 평가의 근거.
- Heid et al. **Chemprop: A Machine Learning Package for Chemical Property Prediction.** JCIM 2024;64:9–17. DOI [10.1021/acs.jcim.3c01250](https://doi.org/10.1021/acs.jcim.3c01250), [원문](https://pmc.ncbi.nlm.nih.gov/articles/PMC10777403/). 분자 그래프 모델과 공개 재현 자료 안내.
- Graff et al. **Chemprop v2: An Efficient, Modular Machine Learning Package for Chemical Property Prediction.** DOI [10.1021/acs.jcim.5c02332](https://doi.org/10.1021/acs.jcim.5c02332). v2 구현과 변경·벤치마킹 설명.
- [Chemprop 공식 설치](https://chemprop.readthedocs.io/en/latest/installation.html), [공식 저장소](https://github.com/chemprop/chemprop): 권장 환경·버전 차이. 현재 설치 검증과 구분.
- [저자 Chemprop benchmark 저장소](https://github.com/chemprop/chemprop_benchmark): SAMPL 등 실행 스크립트·배포 자료 안내와 v1.6.1 환경.
- [scikit-learn 교차검증](https://scikit-learn.org/stable/modules/cross_validation.html): 그룹 분할·평가의 개념. 우리의 scaffold 정책과 cluster bootstrap 자체가 이 문서에서 정해지는 것은 아님.
- [SciPy bootstrap](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html): 재표집 CI와 paired 동작. 그룹 재표집은 별도 구현 필요.

## 문헌·Agent·운영

- [Europe PMC 개발자 자료](https://dev.europepmc.org/developers): 메타데이터·초록·OA 문헌 접근 API. 논문별 재사용 조건 확인.
- [PMC 개발자 정책](https://pmc.ncbi.nlm.nih.gov/tools/developers): 허용된 자동 수집 서비스와 콘텐츠별 이용 조건.
- [LangGraph workflows and agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents): 정해진 흐름과 동적 도구 선택의 구분.
- [MLflow Tracking](https://mlflow.org/docs/latest/ml/tracking/): 실험 파라미터·코드·지표·출력 기록.
- [AWS Fargate](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html): 컨테이너 운영 기능. 비용·실제 배포 결과는 별도 검증.
- [Amazon S3 Versioning](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html): 명시적 활성화와 객체 버전 보존. 파일 해시·학습 버전 매니페스트도 함께 기록할 계획.
