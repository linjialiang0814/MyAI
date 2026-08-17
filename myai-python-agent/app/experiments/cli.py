from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.experiments.runner import run_experiment, validate_experiment


DEFAULT_SPEC = Path(__file__).resolve().parents[2] / "experiments" / "specs" / "thesis_core_v1.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run reproducible MyAI graduation-thesis experiments.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="Validate the frozen spec and dataset.")
    validate.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    validate.add_argument("--live", action="store_true", help="Probe the configured local runtime and embedding.")
    validate.add_argument("--exploratory", action="store_true", help="Allow hardware or dirty-tree mismatch.")

    run = subparsers.add_parser("run", help="Run memory and/or RAG ablations.")
    run.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    run.add_argument("--suite", choices=("all", "memory", "rag"), default="all")
    run.add_argument("--output-dir", type=Path)
    run.add_argument("--repeats", type=int)
    run.add_argument("--max-cases", type=int)
    run.add_argument("--exploratory", action="store_true", help="Produce diagnostic, non-publishable evidence.")

    args = parser.parse_args()
    if args.command == "validate":
        payload = validate_experiment(args.spec, live=args.live, exploratory=args.exploratory)
    else:
        payload = run_experiment(
            args.spec,
            suite=args.suite,
            output_dir=args.output_dir,
            repeats=args.repeats,
            max_cases=args.max_cases,
            exploratory=args.exploratory,
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
