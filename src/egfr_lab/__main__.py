"""Small offline commands; collection, training and agents are planned modules."""

import argparse
import json
from pathlib import Path

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
    args = parser.parse_args()
    try:
        if args.command == "convert-ic50":
            print(json.dumps({"pIC50": ic50_to_pic50(args.value, args.unit, args.relation)}))
            return
        config = load_config(args.config)
        if args.command == "check-config":
            print("Configuration valid. Dataset, model and deployment are not yet validated.")
        else:
            print(json.dumps(config["phases"], ensure_ascii=False, indent=2))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
