from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from archdrift.experiments import (
    run_suite,
    write_suite_reports,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="archdrift",
        description=(
            "Multi-evidence architecture conformance "
            "experiment runner."
        ),
    )

    commands = parser.add_subparsers(
        dest="command",
        required=True,
    )

    run_suite_parser = commands.add_parser(
        "run-suite",
        help=(
            "Run a reproducible architecture "
            "mutation experiment suite."
        ),
    )

    run_suite_parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
    )

    run_suite_parser.add_argument(
        "--suite",
        type=Path,
        default=Path(
            "cases/suite.yaml"
        ),
    )

    run_suite_parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "results/experiment-suite"
        ),
    )

    return parser


def main(
    argv: Sequence[str] | None = None,
) -> int:
    parser = _build_parser()

    args = parser.parse_args(
        argv
    )

    if args.command == "run-suite":
        result = run_suite(
            project_root=(
                args.project_root
            ),
            suite_file=args.suite,
        )

        paths = write_suite_reports(
            result=result,
            output_dir=args.output,
        )

        print(
            "ArchitectureDrift experiment suite completed."
        )

        print(
            f"Suite: {result.suite_id}"
        )

        print(
            f"Cases: {len(result.cases)}"
        )

        print(
            "Fingerprint: "
            f"{result.suite_fingerprint}"
        )

        print(
            f"JSON: {paths.result_json}"
        )

        print(
            f"CSV: {paths.summary_csv}"
        )

        print(
            f"Markdown: {paths.report_markdown}"
        )

        return 0

    parser.error(
        f"Unsupported command: {args.command}"
    )

    return 2


if __name__ == "__main__":
    raise SystemExit(
        main()
    )