"""한국어 EGFR·모델 결과 읽기 실습. 파일·모델을 변경하지 않는다."""

import argparse
import csv
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lesson", choices=["units", "review", "predictions", "quiz"], default="units",
                        help="units=단위, review=원문 대조, predictions=결과 읽기, quiz=자가 점검")
    args = parser.parse_args()
    if args.lesson == "units":
        print("단위 실습: pIC50 = -log10(몰 농도) = 9 - log10(nM 농도)")
        for nM in (10, 100, 170, 260):
            print(f"{nM:>3} nM → {9-math.log10(nM):.6f}")
        print("직접 계산: 0.17 µM = 170 nM. >50 µM는 정확한 pIC50=4.30103이 아니라 pIC50<4.30103입니다.")
    elif args.lesson == "review":
        path = ROOT / "data/interim/apsel_review_20261020/figure2_crosscheck.csv"
        with path.open() as stream:
            for row in csv.DictReader(stream):
                print(f"{row['compound_key']}: 원문 {row['relation']}{row['value_uM']} µM → DB {row['relation']}{row['value_nM']} nM; 일치={row['matched']}")
        print("직접 확인: 원문 Figure 2a의 EGFR 행과 비교하세요. 일치 8건이 전체 209건의 조건 검증 완료를 뜻하는지 설명해 보세요.")
    elif args.lesson == "predictions":
        directory = ROOT / "reports/baseline_pilot_20261020_v2"
        with (directory / "metrics.csv").open() as stream:
            for row in csv.DictReader(stream):
                if row["seed"] == "42":
                    print(f"분할={row['scheme']}, 모델={row['model']}, MAE={float(row['MAE']):.4f}, RMSE={float(row['RMSE']):.4f}")
        print("직접 확인: 작은 MAE가 어느 모델인지, 분할을 바꾸면 차이가 어떻게 바뀌는지 적어 보세요.")
        print("결과는 22건 탐색 실험입니다. 일반 EGFR 성능·임상 성과로 확대하지 않습니다.")
    else:
        questions = [
            ("10 nM의 pIC50는? ① 7  ② 8  ③ 9", "2", "몰 농도 10^-8의 음의 로그는 8입니다."),
            (">50 µM를 정확값 회귀에 넣어도 될까요? ① 예  ② 아니오", "2", "억제가 50%에 도달한 정확한 농도를 모릅니다."),
            ("Dummy의 평균은 어디서 계산하나요? ① 전체 자료  ② 해당 학습 fold", "2", "평가 라벨이 평균에 들어가면 정보가 샙니다."),
            ("같은 골격이 양쪽에 있으면 새 골격 평가인가요? ① 예  ② 아니오", "2", "random 분할과 scaffold 분할의 질문이 다릅니다."),
        ]
        score = 0
        for question, answer, explanation in questions:
            print(question)
            try:
                response = input("선택지 번호를 입력하세요: ").strip()
            except EOFError:
                print("대화형 터미널에서 다시 실행하면 답을 입력할 수 있습니다.")
                return
            correct = response == answer
            score += int(correct)
            print(("정답입니다. " if correct else f"정답은 {answer}번입니다. ") + explanation)
        print(f"자가 점검 결과: {score}/{len(questions)}. 채용 평가가 아닌 학습용 문항입니다.")


if __name__ == "__main__":
    main()
