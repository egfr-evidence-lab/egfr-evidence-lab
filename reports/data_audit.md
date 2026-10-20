# EGFR 전체 데이터 감사

정책: `conservative-screen-v1`. 자동 선별 결과이며 원문 검토 완료 수는 0건이다. 학습 코호트는 미확정이다.

수집 release: ChEMBL_37 / 2026-05-01.

측정 26,600건 / 실험 2,425개 / 분자 ID 14,776개를 전수 검사했다.

## 관측값과 품질

### standard_relation

| 값 | 측정 수 |
|---|---:|
| (결측) | 1,398 |
| < | 2,067 |
| <= | 87 |
| = | 19,719 |
| > | 3,309 |
| >= | 8 |
| >> | 11 |
| ~ | 1 |

### standard_units

| 값 | 측정 수 |
|---|---:|
| (결측) | 1,259 |
| /uM | 6 |
| 10^-5 mol/L | 1 |
| 10^3 uM | 1 |
| nM | 25,244 |
| ug.mL-1 | 89 |

### data_validity_comment

| 값 | 측정 수 |
|---|---:|
| (결측) | 26,090 |
| Outside typical range | 445 |
| Potential transcription error | 65 |

### potential_duplicate

| 값 | 측정 수 |
|---|---:|
| 0 | 23,856 |
| 1 | 2,744 |

### standard_flag

| 값 | 측정 수 |
|---|---:|
| 0 | 1,409 |
| 1 | 25,191 |

### src_id

| 값 | 측정 수 |
|---|---:|
| 1 | 17,521 |
| 15 | 871 |
| 37 | 7,272 |
| 38 | 747 |
| 54 | 6 |
| 65 | 54 |
| 72 | 129 |

### document_year

| 값 | 측정 수 |
|---|---:|
| (결측) | 871 |
| 1989 | 72 |
| 1991 | 122 |
| 1992 | 130 |
| 1993 | 132 |
| 1994 | 377 |
| 1995 | 203 |
| 1996 | 300 |
| 1997 | 366 |
| 1998 | 195 |
| 1999 | 220 |
| 2000 | 116 |
| 2001 | 210 |
| 2002 | 178 |
| 2003 | 146 |
| 2004 | 202 |
| 2005 | 260 |
| 2006 | 420 |
| 2007 | 277 |
| 2008 | 1,023 |
| 2009 | 818 |
| 2010 | 570 |
| 2011 | 353 |
| 2012 | 789 |
| 2013 | 790 |
| 2014 | 870 |
| 2015 | 1,007 |
| 2016 | 1,325 |
| 2017 | 2,384 |
| 2018 | 1,398 |
| 2019 | 1,793 |
| 2020 | 1,126 |
| 2021 | 2,717 |
| 2022 | 2,163 |
| 2023 | 1,011 |
| 2024 | 1,200 |
| 2025 | 466 |

## 실험·구조 분류

### variant_by_assay

| 자동 분류 | 건수 |
|---|---:|
| C797S | 1 |
| C797S+L858R | 2 |
| C797S+L858R+T790M | 86 |
| C797S+T790M | 4 |
| G719C | 2 |
| G719S | 1 |
| L858M+T790M | 1 |
| L858R | 113 |
| L858R+T790M | 199 |
| L861Q | 9 |
| T790M | 67 |
| WT | 245 |
| unresolved | 1,695 |

### format_by_assay

| 자동 분류 | 건수 |
|---|---:|
| biochemical_candidate | 720 |
| cellular_or_conflict | 681 |
| unresolved_or_other | 1,024 |

### molecule_type

| 자동 분류 | 건수 |
|---|---:|
| (결측) | 4,466 |
| Oligosaccharide | 5 |
| Protein | 6 |
| Small molecule | 9,309 |
| Unknown | 990 |

### structure_status

| 자동 분류 | 건수 |
|---|---:|
| missing_smiles | 47 |
| molecule_type_unconfirmed_hold | 5,415 |
| multiple_fragments_hold | 284 |
| not_small_molecule_hold | 8 |
| single_component_candidate | 9,022 |

## 보류 사유

여러 사유가 한 측정에 겹칠 수 있다. 보류는 원자료 삭제를 뜻하지 않는다.

| 사유 | 해당 측정 수 |
|---|---:|
| 측정과 assay의 출처 문헌 ID 불일치 (`document_conflict`) | 1 |
| 생화학 실험 근거 미충족 또는 세포/실험 형식 충돌 (`format_not_biochemical`) | 16,605 |
| 농도 결측·비수치·비양수·비유한 값 (`invalid_value`) | 1,401 |
| 부등호·근삿값·관계 결측 (`not_exact`) | 6,881 |
| standard_flag가 1이 아님 (`not_standardized`) | 1,409 |
| ChEMBL 잠재 중복 인용 플래그 (`potential_duplicate`) | 2,744 |
| 품질 경고(원문 재검토 필요) (`quality_flag`) | 510 |
| 실험 설명에 단백질 유래 불명 표기 (`species_unclear`) | 6,476 |
| 구조 결측·파싱 실패·다성분·분자 유형 미확정/부적합 (`structure`) | 10,897 |
| 직접 인간 EGFR 연결(confidence 9, D, taxon 9606) 미충족 (`target_link`) | 7,171 |
| 지원하지 않는 단위(질량 농도 등) (`unsupported_unit`) | 1,356 |
| 정상형/단일 변이 맥락 미확정 또는 표기 충돌 (`variant_unresolved`) | 19,918 |

첫 사유만 세는 상호 배타적 흐름(총합은 전체 측정 수):

| 첫 사유 | 측정 수 |
|---|---:|
| candidate | 264 |
| format_not_biochemical | 2,530 |
| not_exact | 74 |
| potential_duplicate | 33 |
| quality_flag | 2 |
| species_unclear | 6,476 |
| structure | 102 |
| target_link | 7,171 |
| variant_unresolved | 9,948 |

## 변이별 생화학 후보

서로 다른 변이 코호트를 합치지 않는다. 같은 WT 안에서도 ATP·기질·반응 시간·검출법 차이가 남아 있다.

| 변이 | 측정 | 고유 구조 | 실험 | 문헌 | 고리 scaffold | pIC50 범위 | 최대 문헌 비율 |
|---|---:|---:|---:|---:|---:|---|---:|
| C797S+L858R+T790M | 7 | 7 | 2 | 2 | 7 | 5.102–8.921 | 57.1% |
| L858R | 31 | 31 | 4 | 4 | 17 | 6.321–10.000 | 71.0% |
| L858R+T790M | 122 | 104 | 11 | 11 | 51 | 4.896–9.745 | 25.4% |
| L861Q | 22 | 22 | 1 | 1 | 14 | 6.077–9.337 | 100.0% |
| T790M | 32 | 32 | 4 | 4 | 18 | 5.324–9.292 | 65.6% |
| WT | 50 | 49 | 6 | 6 | 26 | 4.815–9.328 | 44.0% |

## 중복·라벨 교차 확인

전체 자료에서 동일 분자 ID·assay·변이 메타데이터·문헌의 반복 맥락 595개(1,237건). 그 안에서 관계·표준값 문자열·단위까지 같은 그룹 185개(390건). 결측도 같은 표기로 묶은 기술적 집계이다. 이 수치는 반복 실험과 중복 인용을 자동 구별하지 않으며, 문자열이 다른 반올림값도 통합하지 않는다.

후보에서 동일 구조·assay·변이·문헌의 반복 맥락 14개, 해당 측정 28건. 평균·중앙값 집계나 행 삭제는 하지 않았다.

pChEMBL 교차 확인: {"compared": 19378, "difference_over_0_011": 0, "max_absolute_difference": 0.005493477406601777, "interpretation": "표준 농도로 재계산; pChEMBL 반올림 허용차 0.011로 교차 확인"}

서로 다른 assay의 같은 분자는 별도 관측으로 유지했다. 잠재 중복 인용 플래그는 보류했다. 플래그가 0이어도 독립 재측정을 보증하지 않는다.

## 사용 정책과 다음 결정

1. WT 후보를 첫 원문 검토 대상으로 제안한다. WT가 최종 학습 대상으로 확정된 것은 아니다.
2. manual_review_queue.csv에서 후보 우선으로 원문·SI를 확인한다. ATP 농도, 기질, 반응 시간, 단백질 구성체, 공유결합/시간 의존성, 검출법을 기록한다.
3. 생물학적·측정 맥락이 비교 가능한 하위 코호트를 확정한 후 반복값 처리와 scaffold 분할을 정한다. 최소 표본 수나 성능을 미리 단정하지 않는다.
4. 변이 미기재를 WT로 간주하지 않는다. unknown origin 표기는 인간 assay 메타데이터와 별개로 보류했다.
5. CELL 키워드는 발현용 세포까지 보류할 수 있다. 형식 불명 자료도 생화학 단서가 있더라도 보류하므로 누락이 존재한다. 자동 규칙의 정확도·재현율은 검증하지 않았다.
6. 분자 유형이 Small molecule로 확인된 단일 성분만 구조 후보로 둔다. 유형 결측·Unknown은 비소분자라고 단정하지 않고 별도 보류한다. 탈염·중성화·tautomer 통합·최대 조각 선택을 하지 않는다. 입체화학은 보존하고 미지정 중심을 표시한다.
7. 구조 식별자는 canonical isomeric SMILES의 SHA-256이다. connectivity SMILES는 입체·동위원소 정보 없는 비교용이며 라벨 통합에 사용하지 않는다. Murcko scaffold는 chirality=False이고 비고리 구조는 빈 scaffold로 별도 집계한다. 아직 데이터 분할은 하지 않았다.

## 산출물과 재현

감사 테이블: `/Users/kyungduck/Documents/ChatGPT/사이드 프로젝트/egfr-evidence-lab/data/interim/audit_chembl_full_20261020`. `audit_manifest.json`에 입력·출력·정책 코드 해시와 실행 환경을 기록했다.

assay_review.csv는 자동 분류표, manual_review_queue.csv는 비어 있는 수동 검토 입력칸을 포함한 작업용 사본이다. 재실행 시 기존 폴더와 보고서를 덮어쓰지 않는다.

## WT 추가 검토 대상

자동 선별 범위 밖의 WT 재검토 대상(후보 합산 금지):

| 유일한 보류 사유 | 측정 | 실험 |
|---|---:|---:|
| 실험 설명에 단백질 유래 불명 표기 | 277 | 37 |
| 구조 결측·파싱 실패·다성분·분자 유형 미확정/부적합 | 72 | 6 |

구조 보류는 유형 결측·Unknown·명시적 비소분자·다성분 등을 포함하므로 분자별 상태를 확인해야 한다.

## 공식 근거

- [ChEMBL 실험·품질](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/chembl-data-questions)
- [ChEMBL 변이·표적](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/target-questions)
- [RDKit scaffold](https://www.rdkit.org/docs/source/rdkit.Chem.Scaffolds.MurckoScaffold.html)
