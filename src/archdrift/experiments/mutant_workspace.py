from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
)

from archdrift.experiments.subjects import (
    LockedSubject,
    SubjectLock,
    verify_subjects,
)
from archdrift.model.mutation import (
    load_mutation_oracle,
)
from archdrift.model.mutation_implementation import (
    MutationImplementation,
    MutationImplementationManifest,
)


class MutationWorkspaceError(
    RuntimeError
):
    """Raised when an isolated mutant workspace cannot be prepared."""


class MutationWorkspaceRecord(
    BaseModel
):
    """
    Reproducibility record for one applied source mutation.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    system_id: str

    mutation_id: str

    baseline_commit: str

    oracle: str

    patch: str

    patch_sha256: str

    applied_diff_sha256: str

    workspace: str


def _run_git(
    arguments: tuple[str, ...],
    *,
    cwd: Path,
    check: bool = True,
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
        raise MutationWorkspaceError(
            "Git executable was not found."
        ) from exc

    if (
        check
        and result.returncode != 0
    ):
        message = (
            result.stderr.strip()
            or result.stdout.strip()
            or "Unknown Git error."
        )

        raise MutationWorkspaceError(
            "Git command failed.\n"
            f"Command: {' '.join(command)}\n"
            f"{message}"
        )

    return result


def _sha256_bytes(
    value: bytes,
) -> str:
    return hashlib.sha256(
        value
    ).hexdigest()


def _sha256_file(
    path: Path,
) -> str:
    return _sha256_bytes(
        path.read_bytes()
    )


def _current_commit(
    repository: Path,
) -> str:
    result = _run_git(
        (
            "rev-parse",
            "HEAD",
        ),
        cwd=repository,
    )

    return (
        result.stdout
        .strip()
        .lower()
    )


def _working_diff(
    repository: Path,
) -> str:
    result = _run_git(
        (
            "diff",
            "--binary",
            "--no-ext-diff",
            "--",
        ),
        cwd=repository,
    )

    return result.stdout


class MutationWorkspaceManager:
    """
    Create isolated source-level mutant workspaces from locked subjects.

    The baseline checkout under subjects/ is never modified.

    A detached Git worktree is created at the exact locked commit and the
    version-controlled mutation patch is applied to that worktree.
    """

    def __init__(
        self,
        *,
        project_root: Path,
        subject_lock: SubjectLock,
        implementation_manifest: (
            MutationImplementationManifest
        ),
    ) -> None:
        self._project_root = (
            project_root.resolve()
        )

        self._subject_lock = (
            subject_lock
        )

        self._manifest = (
            implementation_manifest
        )

    def prepare(
        self,
        *,
        mutation_id: str,
        replace: bool = False,
    ) -> MutationWorkspaceRecord:
        implementation = (
            self._manifest.require(
                mutation_id
            )
        )

        subject = self._require_subject(
            implementation.system_id
        )

        subject_root = (
            self._project_root
            / "subjects"
            / subject.id
        ).resolve()

        self._verify_subjects()

        self._validate_oracle(
            implementation
        )

        patch = (
            self._project_root
            / implementation.patch
        ).resolve()

        if not patch.is_file():
            raise FileNotFoundError(
                "Mutation patch does not exist: "
                f"{patch}"
            )

        workspace = (
            self._project_root
            / "workspaces"
            / "mutants"
            / subject.id
            / mutation_id
        ).resolve()

        workspace_parent = (
            workspace.parent
        )

        workspace_parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if workspace.exists():
            if not replace:
                raise MutationWorkspaceError(
                    "Mutation workspace already exists: "
                    f"{workspace}"
                )

            self._remove_worktree(
                subject_root=subject_root,
                workspace=workspace,
            )

        self._validate_patch(
            subject_root=subject_root,
            patch=patch,
        )

        _run_git(
            (
                "worktree",
                "add",
                "--detach",
                str(workspace),
                subject.commit,
            ),
            cwd=subject_root,
        )

        try:
            _run_git(
                (
                    "apply",
                    "--check",
                    "--whitespace=nowarn",
                    str(patch),
                ),
                cwd=workspace,
            )

            _run_git(
                (
                    "apply",
                    "--whitespace=nowarn",
                    str(patch),
                ),
                cwd=workspace,
            )

            actual_commit = (
                _current_commit(
                    workspace
                )
            )

            if (
                actual_commit
                != subject.commit
            ):
                raise MutationWorkspaceError(
                    "Mutant workspace HEAD "
                    "does not match locked baseline.\n"
                    f"Expected: {subject.commit}\n"
                    f"Actual:   {actual_commit}"
                )

            diff = (
                _working_diff(
                    workspace
                )
            )

            if not diff.strip():
                raise MutationWorkspaceError(
                    "Mutation patch produced "
                    "an empty working-tree diff."
                )

            _run_git(
                (
                    "diff",
                    "--check",
                ),
                cwd=workspace,
            )

        except Exception:
            self._remove_worktree(
                subject_root=subject_root,
                workspace=workspace,
            )
            raise

        return MutationWorkspaceRecord(
            system_id=subject.id,
            mutation_id=mutation_id,
            baseline_commit=subject.commit,
            oracle=implementation.oracle,
            patch=implementation.patch,
            patch_sha256=(
                _sha256_file(
                    patch
                )
            ),
            applied_diff_sha256=(
                _sha256_bytes(
                    diff.encode(
                        "utf-8"
                    )
                )
            ),
            workspace=str(
                workspace
            ),
        )

    def remove(
        self,
        *,
        mutation_id: str,
    ) -> None:
        implementation = (
            self._manifest.require(
                mutation_id
            )
        )

        subject = self._require_subject(
            implementation.system_id
        )

        subject_root = (
            self._project_root
            / "subjects"
            / subject.id
        ).resolve()

        workspace = (
            self._project_root
            / "workspaces"
            / "mutants"
            / subject.id
            / mutation_id
        ).resolve()

        if not workspace.exists():
            return

        self._remove_worktree(
            subject_root=subject_root,
            workspace=workspace,
        )

    def _verify_subjects(
        self,
    ) -> None:
        verify_subjects(
            lock=self._subject_lock,
            destination_root=(
                self._project_root
                / "subjects"
            ),
        )

    def _require_subject(
        self,
        system_id: str,
    ) -> LockedSubject:
        for subject in (
            self._subject_lock.subjects
        ):
            if subject.id == system_id:
                return subject

        raise MutationWorkspaceError(
            "Mutation implementation references "
            "an unlocked subject: "
            f"{system_id!r}"
        )

    def _validate_oracle(
        self,
        implementation: (
            MutationImplementation
        ),
    ) -> None:
        oracle_path = (
            self._project_root
            / implementation.oracle
        ).resolve()

        oracle = load_mutation_oracle(
            oracle_path
        )

        if (
            oracle.mutation_id
            != implementation.mutation_id
        ):
            raise MutationWorkspaceError(
                "Mutation implementation and oracle "
                "mutation ids do not match."
            )

        if (
            oracle.system_id
            != implementation.system_id
        ):
            raise MutationWorkspaceError(
                "Mutation implementation and oracle "
                "system ids do not match."
            )

    @staticmethod
    def _validate_patch(
        *,
        subject_root: Path,
        patch: Path,
    ) -> None:
        _run_git(
            (
                "apply",
                "--check",
                "--whitespace=nowarn",
                str(patch),
            ),
            cwd=subject_root,
        )

    @staticmethod
    def _remove_worktree(
        *,
        subject_root: Path,
        workspace: Path,
    ) -> None:
        result = _run_git(
            (
                "worktree",
                "remove",
                "--force",
                str(workspace),
            ),
            cwd=subject_root,
            check=False,
        )

        if result.returncode != 0:
            raise MutationWorkspaceError(
                "Unable to remove mutation worktree.\n"
                f"Workspace: {workspace}\n"
                f"{result.stderr.strip()}"
            )

        _run_git(
            (
                "worktree",
                "prune",
            ),
            cwd=subject_root,
        )