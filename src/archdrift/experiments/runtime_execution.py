from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
)

from archdrift.experiments.mutant_workspace import (
    MutationWorkspaceManager,
)
from archdrift.experiments.subjects import (
    LockedSubject,
    load_subject_lock,
    verify_subjects,
)
from archdrift.model.mutation_implementation import (
    MutationImplementationManifest,
    load_mutation_implementation_manifest,
)


class RuntimeExecutionError(
    RuntimeError
):
    """Raised when a runtime experiment workspace cannot be prepared."""


class RuntimeVariant(StrEnum):
    BASELINE = "baseline"
    MUTANT = "mutant"


class RuntimeExecutionRecord(
    BaseModel
):
    """
    Reproducibility record for one runtime experiment execution.

    The record identifies the exact subject revision, mutation,
    workspace and expected OTLP output location.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    system_id: str
    mutation_id: str
    variant: RuntimeVariant

    baseline_commit: str

    workspace: str

    output_directory: str
    otlp_trace_file: str

    patch_sha256: str | None = None
    applied_diff_sha256: str | None = None


def _require_subject(
    *,
    system_id: str,
    subjects: tuple[
        LockedSubject,
        ...,
    ],
) -> LockedSubject:
    for subject in subjects:
        if subject.id == system_id:
            return subject

    raise RuntimeExecutionError(
        "Runtime execution references "
        "an unlocked subject: "
        f"{system_id!r}"
    )


def _relative_to_root(
    *,
    root: Path,
    path: Path,
) -> str:
    try:
        return (
            path.resolve()
            .relative_to(root)
            .as_posix()
        )

    except ValueError as exc:
        raise RuntimeExecutionError(
            "Runtime path escapes project root: "
            f"{path}"
        ) from exc


def _write_record(
    *,
    root: Path,
    record: RuntimeExecutionRecord,
) -> Path:
    record_path = (
        root
        / "results"
        / "runtime"
        / "records"
        / record.system_id
        / record.mutation_id
        / f"{record.variant.value}.json"
    )

    record_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    record_path.write_text(
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

    return record_path


def prepare_runtime_execution(
    *,
    project_root: str | Path,
    mutation_id: str,
    variant: RuntimeVariant,
    replace_mutant: bool = False,
) -> tuple[
    RuntimeExecutionRecord,
    Path,
]:
    root = Path(
        project_root
    ).resolve()

    if not root.is_dir():
        raise RuntimeExecutionError(
            "Project root does not exist: "
            f"{root}"
        )

    subject_lock = load_subject_lock(
        root
        / "cases"
        / "subjects.lock.yaml"
    )

    implementation_manifest: (
        MutationImplementationManifest
    ) = load_mutation_implementation_manifest(
        root
        / "mutations"
        / "implementation-manifest.yaml"
    )

    implementation = (
        implementation_manifest.require(
            mutation_id
        )
    )

    subject = _require_subject(
        system_id=implementation.system_id,
        subjects=subject_lock.subjects,
    )

    patch_sha256: str | None = None
    applied_diff_sha256: str | None = None

    if variant is RuntimeVariant.BASELINE:
        verify_subjects(
            lock=subject_lock,
            destination_root=(
                root
                / "subjects"
            ),
        )

        workspace = (
            root
            / "subjects"
            / subject.id
        ).resolve()

    else:
        manager = MutationWorkspaceManager(
            project_root=root,
            subject_lock=subject_lock,
            implementation_manifest=(
                implementation_manifest
            ),
        )

        mutant_record = manager.prepare(
            mutation_id=mutation_id,
            replace=replace_mutant,
        )

        workspace = Path(
            mutant_record.workspace
        ).resolve()

        patch_sha256 = (
            mutant_record.patch_sha256
        )

        applied_diff_sha256 = (
            mutant_record.applied_diff_sha256
        )

    output_directory = (
        root
        / "results"
        / "runtime"
        / "raw"
        / subject.id
        / mutation_id
        / variant.value
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    otlp_trace_file = (
        output_directory
        / "traces.otlp.json"
    )

    record = RuntimeExecutionRecord(
        system_id=subject.id,
        mutation_id=mutation_id,
        variant=variant,
        baseline_commit=subject.commit,
        workspace=_relative_to_root(
            root=root,
            path=workspace,
        ),
        output_directory=_relative_to_root(
            root=root,
            path=output_directory,
        ),
        otlp_trace_file=_relative_to_root(
            root=root,
            path=otlp_trace_file,
        ),
        patch_sha256=patch_sha256,
        applied_diff_sha256=(
            applied_diff_sha256
        ),
    )

    record_path = _write_record(
        root=root,
        record=record,
    )

    return (
        record,
        record_path,
    )