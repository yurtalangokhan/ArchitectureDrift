from __future__ import annotations

from pathlib import Path
from typing import Protocol

from archdrift.model.observation import (
    NormalizedObservation,
)


class NonRuntimeAdapterError(ValueError):
    """Base exception for non-runtime evidence adapters."""


class AdapterPathError(NonRuntimeAdapterError):
    """Raised when an adapter accesses an invalid repository path."""


class NonRuntimeEvidenceAdapter(Protocol):
    """Common interface implemented by non-runtime evidence adapters."""

    def collect(
        self,
    ) -> tuple[NormalizedObservation, ...]:
        ...


def resolve_repository_path(
    repository_root: Path,
    relative_path: str | Path,
) -> Path:
    """
    Resolve a path while guaranteeing it remains inside repository_root.
    """

    root = repository_root.resolve()

    candidate = (
        root
        / Path(relative_path)
    ).resolve()

    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise AdapterPathError(
            f"Path escapes repository root: {relative_path}"
        ) from exc

    return candidate


def repository_artifact_id(
    repository_root: Path,
    path: Path,
) -> str:
    """
    Return deterministic repository-relative artifact identity.

    Absolute machine-specific paths must never enter evidence fingerprints.
    """

    root = repository_root.resolve()
    resolved = path.resolve()

    try:
        relative = resolved.relative_to(
            root
        )
    except ValueError as exc:
        raise AdapterPathError(
            f"Artifact is outside repository root: {path}"
        ) from exc

    return relative.as_posix()