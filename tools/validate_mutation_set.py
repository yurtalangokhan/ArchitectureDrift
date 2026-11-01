from __future__ import annotations

import argparse
from pathlib import Path

from archdrift.experiments.mutation_validation import (
    validate_mutation_set,
)
from archdrift.experiments.subjects import (
    load_subject_lock,
)
from archdrift.model.mutation_implementation import (
    load_mutation_implementation_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate real source-level "
            "ArchitectureDrift mutation patches."
        )
    )

    parser.add_argument(
        "--system",
        required=True,
        help="Subject id, for example astronomy-shop.",
    )

    parser.add_argument(
        "--expect",
        nargs="*",
        default=None,
        help=(
            "Optional exact expected mutation-id set."
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

    project_root = (
        args.project_root.resolve()
    )

    subject_lock = load_subject_lock(
        project_root
        / "cases"
        / "subjects.lock.yaml"
    )

    implementation_manifest = (
        load_mutation_implementation_manifest(
            project_root
            / "mutations"
            / "implementation-manifest.yaml"
        )
    )

    expected = (
        frozenset(
            args.expect
        )
        if args.expect
        else None
    )

    report = validate_mutation_set(
        project_root=project_root,
        system_id=args.system,
        subject_lock=subject_lock,
        implementation_manifest=(
            implementation_manifest
        ),
        expected_mutation_ids=expected,
    )

    print(
        "[OK] "
        f"system={report.system_id} "
        f"baseline={report.baseline_commit} "
        f"mutations={report.mutation_count}"
    )

    for mutation in report.mutations:
        print(
            "[OK] "
            f"{mutation.mutation_id} "
            f"bytes={mutation.patch_size_bytes} "
            "files="
            + ",".join(
                mutation.touched_files
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )