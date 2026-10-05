from __future__ import annotations

import argparse
import json
from pathlib import Path

from archdrift.experiments.mutant_workspace import (
    MutationWorkspaceManager,
)
from archdrift.experiments.subjects import (
    load_subject_lock,
)
from archdrift.model.mutation_implementation import (
    load_mutation_implementation_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--mutation",
        required=True,
    )

    parser.add_argument(
        "--replace",
        action="store_true",
    )

    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
    )

    args = parser.parse_args()

    root = (
        args.project_root
        .resolve()
    )

    subject_lock = (
        load_subject_lock(
            root
            / "cases"
            / "subjects.lock.yaml"
        )
    )

    implementation_manifest = (
        load_mutation_implementation_manifest(
            root
            / "mutations"
            / "implementation-manifest.yaml"
        )
    )

    manager = (
        MutationWorkspaceManager(
            project_root=root,
            subject_lock=subject_lock,
            implementation_manifest=(
                implementation_manifest
            ),
        )
    )

    record = manager.prepare(
        mutation_id=args.mutation,
        replace=args.replace,
    )

    record_file = (
        root
        / "workspaces"
        / "records"
        / record.system_id
        / f"{record.mutation_id}.json"
    )

    record_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    record_file.write_text(
        json.dumps(
            record.model_dump(
                mode="json"
            ),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        f"Mutation:       {record.mutation_id}"
    )

    print(
        f"Subject:        {record.system_id}"
    )

    print(
        f"Baseline SHA:   {record.baseline_commit}"
    )

    print(
        f"Patch SHA-256:  {record.patch_sha256}"
    )

    print(
        "Diff SHA-256:   "
        f"{record.applied_diff_sha256}"
    )

    print(
        f"Workspace:      {record.workspace}"
    )

    print(
        f"Record:         {record_file}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )