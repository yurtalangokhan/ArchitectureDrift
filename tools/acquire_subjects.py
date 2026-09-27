from __future__ import annotations

import argparse
from pathlib import Path

from archdrift.experiments.subjects import (
    acquire_subjects_from_lock,
    create_subject_lock,
    load_subject_lock,
    verify_subjects,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve, acquire, and verify ArchitectureDrift "
            "case-study repositories."
        )
    )

    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
    )

    commands = parser.add_subparsers(
        dest="command",
        required=True,
    )

    lock_parser = commands.add_parser(
        "lock",
        help=(
            "Resolve configured upstream refs and write "
            "the reproducible subject lock file."
        ),
    )

    lock_parser.add_argument(
        "--manifest",
        default="cases/subjects.yaml",
    )

    lock_parser.add_argument(
        "--lock-file",
        default="cases/subjects.lock.yaml",
    )

    acquire_parser = commands.add_parser(
        "acquire",
        help=(
            "Clone/check out subjects strictly at the "
            "locked revisions."
        ),
    )

    acquire_parser.add_argument(
        "--lock-file",
        default="cases/subjects.lock.yaml",
    )

    acquire_parser.add_argument(
        "--destination",
        default="subjects",
    )

    verify_parser = commands.add_parser(
        "verify",
        help=(
            "Verify origins, exact revisions, and clean "
            "working trees."
        ),
    )

    verify_parser.add_argument(
        "--lock-file",
        default="cases/subjects.lock.yaml",
    )

    verify_parser.add_argument(
        "--destination",
        default="subjects",
    )

    return parser


def _resolve(
    root: Path,
    relative: str,
) -> Path:
    candidate = (
        root
        / relative
    ).resolve()

    try:
        candidate.relative_to(
            root
        )
    except ValueError as exc:
        raise ValueError(
            f"Path escapes project root: {relative}"
        ) from exc

    return candidate


def main() -> int:
    args = build_parser().parse_args()

    root = (
        args.project_root
        .resolve()
    )

    if not root.is_dir():
        raise ValueError(
            f"Project root does not exist: {root}"
        )

    if args.command == "lock":
        manifest = _resolve(
            root,
            args.manifest,
        )

        lock_file = _resolve(
            root,
            args.lock_file,
        )

        lock = create_subject_lock(
            manifest_path=manifest,
            lock_path=lock_file,
        )

        print(
            f"Locked {len(lock.subjects)} subjects:"
        )

        for subject in lock.subjects:
            print(
                f"  {subject.id}: "
                f"{subject.commit}"
            )

        print(
            f"Lock file: {lock_file}"
        )

        return 0

    lock_file = _resolve(
        root,
        args.lock_file,
    )

    destination = _resolve(
        root,
        args.destination,
    )

    if args.command == "acquire":
        states = acquire_subjects_from_lock(
            lock_path=lock_file,
            destination_root=destination,
        )

        print(
            f"Acquired {len(states)} subjects:"
        )

        for state in states:
            print(
                f"  {state.id}: "
                f"{state.commit}"
            )

        return 0

    if args.command == "verify":
        lock = load_subject_lock(
            lock_file
        )

        states = verify_subjects(
            lock=lock,
            destination_root=destination,
        )

        print(
            f"Verified {len(states)} subjects:"
        )

        for state in states:
            print(
                f"  {state.id}: "
                f"{state.commit} [clean]"
            )

        return 0

    raise AssertionError(
        f"Unhandled command: {args.command}"
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )