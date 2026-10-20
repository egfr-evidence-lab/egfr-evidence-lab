"""EGFR 설정·단위 변환·ChEMBL 수집 명령. 모델 학습은 후속 단계."""

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

from .config import load_config
from .labels import ic50_to_pic50


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("check-config", "plan"):
        child = sub.add_parser(command)
        child.add_argument("--config", type=Path, default=Path("configs/project.json"))
    convert = sub.add_parser("convert-ic50")
    convert.add_argument("--value", type=float, required=True)
    convert.add_argument("--unit", required=True)
    convert.add_argument("--relation", default="=")
    collector = sub.add_parser("collect", help="ChEMBL 전체 또는 제한 수집")
    collector.add_argument("--run-dir", type=Path, help="원 응답·매니페스트 실행 폴더")
    collector.add_argument("--resume", action="store_true", help="동일 조건의 기존 실행 재시작")
    collector.add_argument("--page-size", type=int, default=500, help="페이지당 요청 행 수 (기본 500)")
    collector.add_argument("--batch-size", type=int, default=50, help="상세 조회 ID 묶음 크기 (기본 50)")
    collector.add_argument("--workers", type=int, default=3, help="상세 요청 동시 작업 수 (1~3)")
    collector.add_argument("--max-pages", type=int, help="측정 페이지 제한; 지정하면 전체 완료로 기록하지 않음")
    verifier = sub.add_parser("verify-collection", help="수집 원 응답·테이블 오프라인 검증")
    verifier.add_argument("run_dir", type=Path, help="검증할 수집 실행 폴더")
    auditor = sub.add_parser("audit", help="전체 수집 자료의 실험·변이·품질·구조 자동 감사")
    auditor.add_argument("run_dir", type=Path, help="전체 수집 완료 실행 폴더")
    auditor.add_argument("--output-dir", type=Path, help="새 감사 테이블 폴더")
    auditor.add_argument("--report-dir", type=Path, help="감사 보고서를 저장할 폴더")
    args = parser.parse_args()
    try:
        if args.command == "audit":
            from .data.audit import audit
            result = audit(args.run_dir, output_dir=args.output_dir, report_dir=args.report_dir)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        if args.command in ("collect", "verify-collection"):
            from .data.collection import collect, verify_collection
            if args.command == "verify-collection":
                print(json.dumps(verify_collection(args.run_dir), ensure_ascii=False, indent=2))
            else:
                if args.resume and args.run_dir is None:
                    raise ValueError("--resume에는 --run-dir가 필요합니다.")
                run_dir = args.run_dir or Path("data/raw") / datetime.now(timezone.utc).strftime("chembl_%Y%m%dT%H%M%S%fZ")
                collect(run_dir, page_size=args.page_size, batch_size=args.batch_size, workers=args.workers,
                        max_pages=args.max_pages, resume=args.resume)
            return
        if args.command == "convert-ic50":
            print(json.dumps({"pIC50": ic50_to_pic50(args.value, args.unit, args.relation)}))
            return
        config = load_config(args.config)
        if args.command == "check-config":
            print("Configuration valid. Dataset, model and deployment are not yet validated.")
        else:
            print(json.dumps(config["phases"], ensure_ascii=False, indent=2))
    except (OSError, ValueError, ImportError) as exc:
        parser.error(str(exc))
    except KeyboardInterrupt:
        if args.command == "audit":
            parser.exit(130, "감사를 중단했습니다. 원 수집 자료는 보존되어 있습니다.\n")
        parser.exit(130, "수집을 중단했습니다. 같은 조건과 --resume으로 재개할 수 있습니다.\n")


if __name__ == "__main__":
    main()
