from __future__ import annotations

import argparse
from pathlib import Path

from archdrift.experiments.runtime_execution import (
    RuntimeVariant,
    prepare_runtime_execution,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare one ArchitectureDrift "
            "runtime experiment execution."
        )
    )

    parser.add_argument(
        "--mutation",
        required=True,
        help="Mutation id, for example AS-M01.",
    )

    parser.add_argument(
        "--variant",
        required=True,
        choices=tuple(
            variant.value
            for variant in RuntimeVariant
        ),
    )

    parser.add_argument(
        "--replace-mutant",
        action="store_true",
        help=(
            "Replace an existing mutant "
            "worktree when preparing mutant."
        ),
    )

    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    record, record_path = (
        prepare_runtime_execution(
            project_root=(
                args.project_root
            ),
            mutation_id=args.mutation,
            variant=RuntimeVariant(
                args.variant
            ),
            replace_mutant=(
                args.replace_mutant
            ),
        )
    )

    print(
        "[OK] "
        f"system={record.system_id} "
        f"mutation={record.mutation_id} "
        f"variant={record.variant.value}"
    )

    print(
        f"Baseline SHA: {record.baseline_commit}"
    )

    print(
        f"Workspace:    {record.workspace}"
    )

    print(
        "OTLP output:  "
        f"{record.otlp_trace_file}"
    )

    print(
        f"Record:       {record_path}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )