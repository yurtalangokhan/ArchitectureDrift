from __future__ import annotations

import shlex
import subprocess
from pathlib import Path, PurePosixPath

from pydantic import (
    BaseModel,
    ConfigDict,
)

from archdrift.experiments.subjects import (
    SubjectLock,
    verify_subjects,
)
from archdrift.model.mutation import (
    load_mutation_oracle,
)
from archdrift.model.mutation_implementation import (
    MutationImplementationManifest,
)


class MutationSetValidationError(
    RuntimeError
):
    """Raised when a real mutation implementation set is invalid."""


class MutationPatchValidation(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    system_id: str
    mutation_id: str

    oracle: str
    patch: str

    patch_size_bytes: int

    touched_files: tuple[
        str,
        ...,
    ]


class MutationSetValidationReport(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    system_id: str

    baseline_commit: str

    mutation_count: int

    mutations: tuple[
        MutationPatchValidation,
        ...,
    ]


def _run_git(
    arguments: tuple[str, ...],
    *,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    command = (
        "git",
        *arguments,
    )

    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    except FileNotFoundError as exc:
        raise MutationSetValidationError(
            "Git executable was not found."
        ) from exc

    if result.returncode != 0:
        message = (
            result.stderr.strip()
            or result.stdout.strip()
            or "Unknown Git error."
        )

        raise MutationSetValidationError(
            "Git command failed.\n"
            f"Command: {' '.join(command)}\n"
            f"{message}"
        )

    return result


def _resolve_project_path(
    project_root: Path,
    relative_path: str,
) -> Path:
    root = project_root.resolve()

    resolved = (
        root
        / relative_path
    ).resolve()

    try:
        resolved.relative_to(
            root
        )

    except ValueError as exc:
        raise MutationSetValidationError(
            "Mutation implementation path "
            "escapes the project root: "
            f"{relative_path!r}"
        ) from exc

    return resolved


def _normalize_patch_path(
    value: str,
) -> str:
    candidate = value.replace(
        "\\",
        "/",
    )

    path = PurePosixPath(
        candidate
    )

    if (
        path.is_absolute()
        or ".." in path.parts
        or not path.parts
    ):
        raise MutationSetValidationError(
            "Unsafe path found in mutation patch: "
            f"{value!r}"
        )

    return path.as_posix()


def extract_patch_touched_files(
    patch: str | Path,
) -> tuple[
    str,
    ...,
]:
    """
    Return repository-relative files represented by a Git patch.

    The implementation reads only canonical ``diff --git`` headers.
    It does not infer architecture semantics from source code.
    """

    patch_path = Path(
        patch
    )

    if not patch_path.is_file():
        raise FileNotFoundError(
            f"Mutation patch not found: {patch_path}"
        )

    if patch_path.stat().st_size == 0:
        raise MutationSetValidationError(
            f"Mutation patch is empty: {patch_path}"
        )

    touched: list[
        str
    ] = []

    for raw_line in (
        patch_path.read_text(
            encoding="utf-8",
            errors="replace",
        )
        .splitlines()
    ):
        if not raw_line.startswith(
            "diff --git "
        ):
            continue

        try:
            parts = shlex.split(
                raw_line
            )

        except ValueError as exc:
            raise MutationSetValidationError(
                "Invalid diff header in mutation patch: "
                f"{raw_line}"
            ) from exc

        if (
            len(parts) != 4
            or parts[0] != "diff"
            or parts[1] != "--git"
        ):
            raise MutationSetValidationError(
                "Unexpected diff header in mutation patch: "
                f"{raw_line}"
            )

        old_path = parts[2]
        new_path = parts[3]

        if not old_path.startswith(
            "a/"
        ):
            raise MutationSetValidationError(
                "Mutation patch old path does not "
                "use Git a/ prefix: "
                f"{old_path!r}"
            )

        if not new_path.startswith(
            "b/"
        ):
            raise MutationSetValidationError(
                "Mutation patch new path does not "
                "use Git b/ prefix: "
                f"{new_path!r}"
            )

        touched.append(
            _normalize_patch_path(
                new_path[2:]
            )
        )

    normalized = tuple(
        sorted(
            set(
                touched
            )
        )
    )

    if not normalized:
        raise MutationSetValidationError(
            "Mutation patch does not contain "
            "any diff --git entries: "
            f"{patch_path}"
        )

    return normalized


def validate_mutation_set(
    *,
    project_root: Path,
    system_id: str,
    subject_lock: SubjectLock,
    implementation_manifest: (
        MutationImplementationManifest
    ),
    expected_mutation_ids: (
        frozenset[str]
        | None
    ) = None,
) -> MutationSetValidationReport:
    root = project_root.resolve()

    verify_subjects(
        lock=subject_lock,
        destination_root=(
            root
            / "subjects"
        ),
    )

    locked_subject = next(
        (
            subject
            for subject
            in subject_lock.subjects
            if subject.id == system_id
        ),
        None,
    )

    if locked_subject is None:
        raise MutationSetValidationError(
            "Mutation set references an "
            "unlocked subject: "
            f"{system_id!r}"
        )

    subject_root = (
        root
        / "subjects"
        / locked_subject.id
    ).resolve()

    implementations = tuple(
        sorted(
            (
                implementation
                for implementation
                in implementation_manifest.implementations
                if implementation.system_id
                == system_id
            ),
            key=lambda implementation: (
                implementation.mutation_id
            ),
        )
    )

    if not implementations:
        raise MutationSetValidationError(
            "No mutation implementations "
            "registered for subject: "
            f"{system_id!r}"
        )

    actual_mutation_ids = frozenset(
        implementation.mutation_id
        for implementation
        in implementations
    )

    if (
        expected_mutation_ids is not None
        and actual_mutation_ids
        != expected_mutation_ids
    ):
        missing = (
            expected_mutation_ids
            - actual_mutation_ids
        )

        unexpected = (
            actual_mutation_ids
            - expected_mutation_ids
        )

        raise MutationSetValidationError(
            "Mutation-set inventory mismatch.\n"
            f"Missing: {sorted(missing)}\n"
            f"Unexpected: {sorted(unexpected)}"
        )

    validations: list[
        MutationPatchValidation
    ] = []

    for implementation in (
        implementations
    ):
        oracle_path = (
            _resolve_project_path(
                root,
                implementation.oracle,
            )
        )

        patch_path = (
            _resolve_project_path(
                root,
                implementation.patch,
            )
        )

        oracle = load_mutation_oracle(
            oracle_path
        )

        if (
            oracle.mutation_id
            != implementation.mutation_id
        ):
            raise MutationSetValidationError(
                "Manifest/oracle mutation id "
                "mismatch.\n"
                "Manifest: "
                f"{implementation.mutation_id}\n"
                "Oracle:   "
                f"{oracle.mutation_id}"
            )

        if (
            oracle.system_id
            != implementation.system_id
        ):
            raise MutationSetValidationError(
                "Manifest/oracle system id "
                "mismatch.\n"
                "Manifest: "
                f"{implementation.system_id}\n"
                "Oracle:   "
                f"{oracle.system_id}"
            )

        if not patch_path.is_file():
            raise FileNotFoundError(
                "Mutation patch not found: "
                f"{patch_path}"
            )

        patch_size = (
            patch_path.stat().st_size
        )

        if patch_size <= 0:
            raise MutationSetValidationError(
                "Mutation patch is empty: "
                f"{patch_path}"
            )

        touched_files = (
            extract_patch_touched_files(
                patch_path
            )
        )

        _run_git(
            (
                "apply",
                "--check",
                "--whitespace=error",
                str(
                    patch_path
                ),
            ),
            cwd=subject_root,
        )

        validations.append(
            MutationPatchValidation(
                system_id=system_id,
                mutation_id=(
                    implementation.mutation_id
                ),
                oracle=(
                    implementation.oracle
                ),
                patch=(
                    implementation.patch
                ),
                patch_size_bytes=(
                    patch_size
                ),
                touched_files=(
                    touched_files
                ),
            )
        )

    return MutationSetValidationReport(
        system_id=system_id,
        baseline_commit=(
            locked_subject.commit
        ),
        mutation_count=len(
            validations
        ),
        mutations=tuple(
            validations
        ),
    )