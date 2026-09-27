from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)

_COMMIT_PATTERN = re.compile(
    r"^[0-9a-fA-F]{40}$"
)

_SUBJECT_ID_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9-]*$"
)


class SubjectAcquisitionError(RuntimeError):
    """Base exception for subject repository acquisition."""


class SubjectConfigurationError(
    SubjectAcquisitionError
):
    """Raised when subject configuration is invalid."""


class SubjectRepositoryError(
    SubjectAcquisitionError
):
    """Raised when a subject Git repository violates an invariant."""


class SubjectSpec(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    id: str
    repository: str
    ref: str = "HEAD"

    @field_validator("id")
    @classmethod
    def validate_id(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not _SUBJECT_ID_PATTERN.fullmatch(
            normalized
        ):
            raise ValueError(
                "Subject id must contain only lowercase "
                "letters, digits, and hyphens."
            )

        return normalized

    @field_validator(
        "repository",
        "ref",
    )
    @classmethod
    def validate_non_empty(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Subject repository/ref must not be empty."
            )

        return normalized


class SubjectManifest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    schema_version: Literal["1.0"] = "1.0"

    subjects: tuple[
        SubjectSpec,
        ...,
    ]

    @model_validator(mode="after")
    def validate_subjects(
        self,
    ) -> SubjectManifest:
        if not self.subjects:
            raise ValueError(
                "Subject manifest must contain at least one subject."
            )

        ids = tuple(
            subject.id
            for subject in self.subjects
        )

        if len(ids) != len(
            set(ids)
        ):
            raise ValueError(
                "Subject manifest contains duplicate subject ids."
            )

        return self


class LockedSubject(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    id: str
    repository: str
    requested_ref: str
    commit: str

    @field_validator("commit")
    @classmethod
    def validate_commit(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip().lower()

        if not _COMMIT_PATTERN.fullmatch(
            normalized
        ):
            raise ValueError(
                "Locked subject commit must be a full "
                "40-character Git SHA."
            )

        return normalized


class SubjectLock(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    schema_version: Literal["1.0"] = "1.0"

    subjects: tuple[
        LockedSubject,
        ...,
    ]

    @model_validator(mode="after")
    def validate_subjects(
        self,
    ) -> SubjectLock:
        if not self.subjects:
            raise ValueError(
                "Subject lock must contain at least one subject."
            )

        ids = tuple(
            subject.id
            for subject in self.subjects
        )

        if len(ids) != len(
            set(ids)
        ):
            raise ValueError(
                "Subject lock contains duplicate subject ids."
            )

        return self


class SubjectCheckout(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    id: str
    repository: str
    commit: str
    path: str
    clean: bool


def _run_git(
    arguments: Sequence[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = [
        "git",
        *arguments,
    ]

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
        raise SubjectRepositoryError(
            "Git executable was not found. "
            "Install Git and ensure it is available on PATH."
        ) from exc

    if (
        check
        and result.returncode != 0
    ):
        stderr = (
            result.stderr.strip()
            or result.stdout.strip()
            or "Unknown Git error."
        )

        raise SubjectRepositoryError(
            f"Git command failed: {' '.join(command)}\n"
            f"{stderr}"
        )

    return result


def _load_yaml_mapping(
    path: Path,
) -> Mapping[str, object]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Configuration file not found: {path}"
        )

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            document = yaml.safe_load(
                file
            )

    except yaml.YAMLError as exc:
        raise SubjectConfigurationError(
            f"Invalid YAML: {path}"
        ) from exc

    if not isinstance(
        document,
        Mapping,
    ):
        raise SubjectConfigurationError(
            f"YAML root must be a mapping: {path}"
        )

    return document


def load_subject_manifest(
    path: str | Path,
) -> SubjectManifest:
    manifest_path = Path(
        path
    )

    return SubjectManifest.model_validate(
        _load_yaml_mapping(
            manifest_path
        )
    )


def load_subject_lock(
    path: str | Path,
) -> SubjectLock:
    lock_path = Path(
        path
    )

    return SubjectLock.model_validate(
        _load_yaml_mapping(
            lock_path
        )
    )


def _resolve_remote_ref(
    subject: SubjectSpec,
) -> str:
    requested_ref = (
        subject.ref.strip()
    )

    if _COMMIT_PATTERN.fullmatch(
        requested_ref
    ):
        return requested_ref.lower()

    candidates: tuple[str, ...]
    if requested_ref == "HEAD":
        candidates = (
            "HEAD",
        )

    elif requested_ref.startswith(
        "refs/"
    ):
        candidates = (
            requested_ref,
        )

    else:
        candidates = (
            f"refs/heads/{requested_ref}",
            f"refs/tags/{requested_ref}^{{}}",
            f"refs/tags/{requested_ref}",
        )

    for candidate in candidates:
        result = _run_git(
            (
                "ls-remote",
                subject.repository,
                candidate,
            )
        )

        lines = tuple(
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip()
        )

        if not lines:
            continue

        commits = {
            line.split(
                None,
                1,
            )[0].lower()
            for line in lines
        }

        valid_commits = {
            commit
            for commit in commits
            if _COMMIT_PATTERN.fullmatch(
                commit
            )
        }

        if len(valid_commits) != 1:
            raise SubjectRepositoryError(
                "Remote ref did not resolve to exactly one commit: "
                f"{subject.repository} {candidate}"
            )

        return next(
            iter(
                valid_commits
            )
        )

    raise SubjectRepositoryError(
        "Unable to resolve remote ref "
        f"{subject.ref!r} for subject "
        f"{subject.id!r}."
    )


def resolve_subject_lock(
    manifest: SubjectManifest,
) -> SubjectLock:
    locked_subjects = tuple(
        LockedSubject(
            id=subject.id,
            repository=subject.repository,
            requested_ref=subject.ref,
            commit=_resolve_remote_ref(
                subject
            ),
        )
        for subject in manifest.subjects
    )

    return SubjectLock(
        subjects=locked_subjects
    )


def write_subject_lock(
    lock: SubjectLock,
    path: str | Path,
) -> None:
    destination = Path(
        path
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    document = lock.model_dump(
        mode="json"
    )

    serialized = yaml.safe_dump(
        document,
        sort_keys=False,
        allow_unicode=True,
    )

    temporary = destination.with_name(
        f"{destination.name}.tmp"
    )

    temporary.write_text(
        serialized,
        encoding="utf-8",
    )

    temporary.replace(
        destination
    )


def create_subject_lock(
    *,
    manifest_path: str | Path,
    lock_path: str | Path,
) -> SubjectLock:
    manifest = load_subject_manifest(
        manifest_path
    )

    lock = resolve_subject_lock(
        manifest
    )

    write_subject_lock(
        lock,
        lock_path,
    )

    return lock


def _repository_is_clean(
    repository: Path,
) -> bool:
    result = _run_git(
        (
            "status",
            "--porcelain",
            "--untracked-files=all",
        ),
        cwd=repository,
    )

    return not result.stdout.strip()


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

    commit = (
        result.stdout.strip().lower()
    )

    if not _COMMIT_PATTERN.fullmatch(
        commit
    ):
        raise SubjectRepositoryError(
            f"Invalid HEAD commit in {repository}: {commit!r}"
        )

    return commit


def _origin_url(
    repository: Path,
) -> str:
    result = _run_git(
        (
            "remote",
            "get-url",
            "origin",
        ),
        cwd=repository,
    )

    return result.stdout.strip()


def _commit_exists(
    repository: Path,
    commit: str,
) -> bool:
    result = _run_git(
        (
            "cat-file",
            "-e",
            f"{commit}^{{commit}}",
        ),
        cwd=repository,
        check=False,
    )

    return result.returncode == 0


def _ensure_locked_commit_available(
    repository: Path,
    subject: LockedSubject,
) -> None:
    if _commit_exists(
        repository,
        subject.commit,
    ):
        return

    _run_git(
        (
            "fetch",
            "--depth",
            "1",
            "origin",
            subject.commit,
        ),
        cwd=repository,
    )

    if not _commit_exists(
        repository,
        subject.commit,
    ):
        raise SubjectRepositoryError(
            "Locked commit could not be fetched: "
            f"{subject.id} {subject.commit}"
        )


def _validate_existing_repository(
    repository: Path,
    subject: LockedSubject,
) -> None:
    git_directory = (
        repository
        / ".git"
    )

    if not git_directory.exists():
        raise SubjectRepositoryError(
            "Subject destination already exists but is not "
            f"a Git repository: {repository}"
        )

    origin = _origin_url(
        repository
    )

    if origin != subject.repository:
        raise SubjectRepositoryError(
            "Subject repository origin does not match lock file.\n"
            f"Subject: {subject.id}\n"
            f"Expected: {subject.repository}\n"
            f"Actual:   {origin}"
        )

    if not _repository_is_clean(
        repository
    ):
        raise SubjectRepositoryError(
            "Subject repository contains local modifications. "
            "ArchitectureDrift will not destroy or overwrite "
            f"local work: {repository}"
        )


def _clone_repository(
    destination: Path,
    subject: LockedSubject,
) -> None:
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    _run_git(
        (
            "clone",
            "--filter=blob:none",
            "--no-checkout",
            subject.repository,
            str(
                destination
            ),
        )
    )


def _checkout_locked_subject(
    *,
    destination: Path,
    subject: LockedSubject,
) -> SubjectCheckout:
    if destination.exists():
        _validate_existing_repository(
            destination,
            subject,
        )

    else:
        _clone_repository(
            destination,
            subject,
        )

    _ensure_locked_commit_available(
        destination,
        subject,
    )

    _run_git(
        (
            "checkout",
            "--detach",
            subject.commit,
        ),
        cwd=destination,
    )

    actual_commit = _current_commit(
        destination
    )

    if actual_commit != subject.commit:
        raise SubjectRepositoryError(
            "Subject checkout does not match lock file.\n"
            f"Subject: {subject.id}\n"
            f"Expected: {subject.commit}\n"
            f"Actual:   {actual_commit}"
        )

    clean = _repository_is_clean(
        destination
    )

    if not clean:
        raise SubjectRepositoryError(
            "Subject repository is dirty immediately after checkout: "
            f"{destination}"
        )

    return SubjectCheckout(
        id=subject.id,
        repository=subject.repository,
        commit=actual_commit,
        path=str(
            destination.resolve()
        ),
        clean=True,
    )


def acquire_subjects(
    *,
    lock: SubjectLock,
    destination_root: str | Path,
) -> tuple[
    SubjectCheckout,
    ...,
]:
    root = Path(
        destination_root
    )

    root.mkdir(
        parents=True,
        exist_ok=True,
    )

    return tuple(
        _checkout_locked_subject(
            destination=(
                root
                / subject.id
            ),
            subject=subject,
        )
        for subject in lock.subjects
    )


def acquire_subjects_from_lock(
    *,
    lock_path: str | Path,
    destination_root: str | Path,
) -> tuple[
    SubjectCheckout,
    ...,
]:
    lock = load_subject_lock(
        lock_path
    )

    return acquire_subjects(
        lock=lock,
        destination_root=destination_root,
    )


def verify_subjects(
    *,
    lock: SubjectLock,
    destination_root: str | Path,
) -> tuple[
    SubjectCheckout,
    ...,
]:
    root = Path(
        destination_root
    )

    states: list[
        SubjectCheckout
    ] = []

    for subject in lock.subjects:
        repository = (
            root
            / subject.id
        )

        if not repository.is_dir():
            raise SubjectRepositoryError(
                f"Subject repository is missing: {repository}"
            )

        _validate_existing_repository(
            repository,
            subject,
        )

        commit = _current_commit(
            repository
        )

        if commit != subject.commit:
            raise SubjectRepositoryError(
                "Subject repository is at the wrong revision.\n"
                f"Subject: {subject.id}\n"
                f"Expected: {subject.commit}\n"
                f"Actual:   {commit}"
            )

        states.append(
            SubjectCheckout(
                id=subject.id,
                repository=subject.repository,
                commit=commit,
                path=str(
                    repository.resolve()
                ),
                clean=True,
            )
        )

    return tuple(
        states
    )