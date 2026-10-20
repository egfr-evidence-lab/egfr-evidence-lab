# 전체 자료 감사와 원문 검토

2026-10-20에 ChEMBL_37 전체 수집 자료를 오프라인으로 감사했다. **자동 선별까지 완료했고, 학습 코호트 확정과 원문 검토는 남아 있다.**

```bash
PYTHONPATH=src .venv/bin/python -m egfr_lab audit data/raw/chembl_full_20261020
```

원 응답·Parquet를 먼저 검증하고 전체 수집 완료 상태인지 확인한다. 원자료를 수정하지 않는다. 기본 산출 폴더는 `data/interim/audit_chembl_full_20261020/`, 보고서는 `reports/`이다. 기존 결과나 작성 중인 검토표가 있으면 덮어쓰기를 거절한다. 재감사는 새 폴더 두 개를 지정한다.

```bash
PYTHONPATH=src .venv/bin/python -m egfr_lab audit data/raw/chembl_full_20261020 \
  --output-dir data/interim/audit_review_v2 --report-dir reports/audit_review_v2
```

## 산출물

| 파일 | 내용 |
|---|---|
| assay_review.csv | 2,425개 assay의 원 설명·변이 메타데이터·자동 분류·판단 근거 |
| molecule_audit.csv | 14,776개 분자의 원 SMILES·구조 파싱·분자 유형·입체 미지정·scaffold |
| activity_audit.csv | 26,600개 측정 모두, 계산 가능한 정확 pIC50, 겹치는 보류 사유와 첫 사유 |
| candidate_measurements.csv | 보수적 자동 규칙을 통과한 264건; 변이별로 분리해서 검토 |
| repeat_contexts.csv | 후보 내 같은 구조·assay·변이·문헌에서 반복되는 14개 맥락 |
| manual_review_queue.csv | 문헌 ID·DOI·PMID와 수동 검토 입력란; 모든 결정은 빈칸으로 시작 |
| audit_manifest.json | 수집 검증 결과, 입력·출력·정책 코드 SHA-256, 패키지 버전 |

CSV는 한글 열람을 위한 UTF-8 BOM 형식이다. ID·PMID·농도 원 표기는 문자열로 읽어야 한다. 활동 ID는 유일하다. 같은 분자에 여러 측정이 있다는 이유로 행을 삭제하거나 평균하지 않는다.

보고서: [전체 감사](../reports/data_audit.md), [데이터 카드](../reports/dataset_card.md), [기계 판독 요약](../reports/audit_summary.json).

독립 검증 명령:

```bash
.venv/bin/python scripts/check_data_audit.py data/interim/audit_chembl_full_20261020
```

입력·출력·코드 해시, 원 측정 ID 보존, 후보 행 전체 내용, 정확 IC50 라벨, 집계 합계를 검사한다. 수동 검토 전의 감사 초안이 대상이다. 사람이 작업한 사본은 감사 초안과 구별해 보관한다.

## 자동 규칙의 의미

`conservative-screen-v1`은 정확한 IC50 회귀 후보를 고르는 프로젝트 정책이다. ChEMBL이 모든 보류 행을 오류로 판정했다는 뜻은 아니다.

- 인간 EGFR 직접 연결(confidence 9, 관계 D, assay 종 Homo sapiens·taxon 9606)을 요구한다. 설명에 unknown origin/source가 남아 있으면 별도 보류한다.
- WT는 설명에 정상형 EGFR이 명시되고 변이 단서와 충돌하지 않아야 한다. 메타데이터 결측을 WT로 채우지 않는다. 정의된 변이는 P00533 기준 구조화 표기와 설명을 대조한다.
- B 분류·단백질/단일 단백질/무세포 형식·생화학 설명 단서가 모두 필요하다. 세포 단서나 형식 충돌은 보류한다. 발현용 세포까지 걸릴 수 있는 보수적 규칙이며 원문 재판정이 필요하다.
- 관계 `=`·양수 유한 농도·지원 몰 농도 단위에 대해서만 pIC50를 계산한다. 품질 경고·잠재 중복 인용·standard_flag 미충족은 후보에서 보류한다. 계산값이 있다고 후보인 것은 아니다.
- 단일 성분이고 Small molecule로 명시된 구조만 후보로 둔다. Unknown·결측 유형은 미확정으로 보류하고 비소분자와 구별한다. 탈염·중성화·tautomer 통합·parent 치환을 하지 않는다.
- canonical isomeric SMILES로 구조 ID를 만들며 입체·동위원소 차이를 보존한다. 입체정보가 없는 connectivity SMILES는 비교용이다. Murcko scaffold는 chirality=False이며 실제 분할은 아직 만들지 않았다.

규칙의 분류 정확도와 재현율은 원문 정답표로 평가하지 않았다. confidence 9는 실험 간 동질성의 보증이 아니다. 이 해석은 [ChEMBL assay/activity FAQ](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/chembl-data-questions), [변이 FAQ](https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/target-questions), [RDKit scaffold API](https://www.rdkit.org/docs/source/rdkit.Chem.Scaffolds.MurckoScaffold.html)를 참고했다.

## 다음 원문 검토 순서

1. WT 후보 50건·고유 구조 49개·6개 assay/문헌을 먼저 검토한다. 고리 scaffold 26개이며 한 문헌이 측정의 44%를 차지한다. 이 작은 후보를 곧바로 모델 평가에 쓰지 않는다.
2. `manual_review_queue.csv`에 논문·SI 근거 URL, 단백질 구성체, ATP 농도, 기질, 사전 반응·측정 시간, 검출법, 시간 의존성을 기록한다. 검토자와 날짜, 포함/보류 결정을 남긴다.
3. unknown origin만으로 보류된 WT 277건·37개 assay, 구조 사유만으로 보류된 WT 72건·6개 assay를 재검토한다. 같은 assay가 다른 묶음에 걸칠 수 있으므로 실험 수를 더하지 않는다. 재판정 전에는 후보 수에 합산하지 않는다.
4. 근거가 확인된 동질적 하위 코호트를 확정하고 반복값 처리·구조 그룹·scaffold 분할 정책을 고정한다. 변이 혼합이나 성능을 보고 코호트를 바꾸는 일은 피한다.

수동 검토표는 별도 작업 사본으로 관리한다. 현재 코드는 작성한 결정을 자동 학습 데이터로 적용하지 않는다. 적용 기능은 근거 검토와 정책 확정 후 추가한다. P0는 계속 `in_progress`이며 모델 학습은 다음 단계이다.
