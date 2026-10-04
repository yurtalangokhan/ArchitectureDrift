from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from archdrift.model.static_profile import (
    NonRuntimeEvidenceProfile,
    StaticEvidenceProfile,
)


class StaticProfileError(
    ValueError
):
    pass


def _mapping(
    value: Any,
    *,
    name: str,
) -> dict[str, Any]:
    if not isinstance(
        value,
        dict,
    ):
        raise StaticProfileError(
            f"{name} must be a mapping."
        )

    return value


def load_static_evidence_profile(
    path: Path,
    *,
    subject_id: str,
) -> StaticEvidenceProfile:
    resolved = path.resolve()

    if not resolved.is_file():
        raise FileNotFoundError(
            "Real-evidence configuration "
            f"not found: {resolved}"
        )

    document = yaml.safe_load(
        resolved.read_text(
            encoding="utf-8",
        )
    )

    root = _mapping(
        document,
        name="real-evidence root",
    )

    subjects = _mapping(
        root.get("subjects"),
        name="subjects",
    )

    raw_subject = subjects.get(
        subject_id
    )

    if raw_subject is None:
        raise StaticProfileError(
            "Unknown real-evidence subject: "
            f"{subject_id!r}"
        )

    subject = _mapping(
        raw_subject,
        name=f"subject {subject_id!r}",
    )

    non_runtime = _mapping(
        subject.get("non_runtime"),
        name=(
            f"subject {subject_id!r} "
            "non_runtime"
        ),
    )

    source_static_raw = (
        non_runtime.get(
            "source_static",
            {},
        )
    )

    source_static = _mapping(
        source_static_raw,
        name=(
            f"subject {subject_id!r} "
            "source_static"
        ),
    )

    scope = _mapping(
        subject.get("scope"),
        name=(
            f"subject {subject_id!r} "
            "scope"
        ),
    )

    node_types = _mapping(
        scope.get("node_types"),
        name=(
            f"subject {subject_id!r} "
            "scope.node_types"
        ),
    )

    profile_document = {
        "schema_version": (
            root.get(
                "schema_version"
            )
        ),
        "subject_id": subject_id,
        "subject_root": (
            subject.get(
                "subject_root"
            )
        ),
        "node_types": node_types,
        "source_roots": (
            source_static.get(
                "source_roots",
                [],
            )
        ),
    }

    return (
        StaticEvidenceProfile
        .model_validate(
            profile_document
        )
    )

def load_non_runtime_evidence_profile(
    path: Path,
    *,
    subject_id: str,
) -> NonRuntimeEvidenceProfile:
    resolved = path.resolve()

    if not resolved.is_file():
        raise FileNotFoundError(
            "Real-evidence configuration "
            f"not found: {resolved}"
        )

    document = yaml.safe_load(
        resolved.read_text(
            encoding="utf-8",
        )
    )

    root = _mapping(
        document,
        name="real-evidence root",
    )

    subjects = _mapping(
        root.get("subjects"),
        name="subjects",
    )

    raw_subject = subjects.get(
        subject_id
    )

    if raw_subject is None:
        raise StaticProfileError(
            "Unknown real-evidence subject: "
            f"{subject_id!r}"
        )

    subject = _mapping(
        raw_subject,
        name=f"subject {subject_id!r}",
    )

    non_runtime = _mapping(
        subject.get(
            "non_runtime"
        ),
        name=(
            f"subject {subject_id!r} "
            "non_runtime"
        ),
    )

    scope = _mapping(
        subject.get("scope"),
        name=(
            f"subject {subject_id!r} "
            "scope"
        ),
    )

    node_types = _mapping(
        scope.get(
            "node_types"
        ),
        name=(
            f"subject {subject_id!r} "
            "scope.node_types"
        ),
    )

    source_static = _mapping(
        non_runtime.get(
            "source_static",
            {},
        ),
        name=(
            f"subject {subject_id!r} "
            "source_static"
        ),
    )

    profile_document = {
        "schema_version": (
            root.get(
                "schema_version"
            )
        ),
        "subject_id": subject_id,
        "subject_root": (
            subject.get(
                "subject_root"
            )
        ),
        "node_types": node_types,
        "source_roots": (
            source_static.get(
                "source_roots",
                [],
            )
        ),
        "compose": (
            non_runtime.get(
                "compose"
            )
        ),
        "aspire": (
            non_runtime.get(
                "aspire"
            )
        ),
    }

    return (
        NonRuntimeEvidenceProfile
        .model_validate(
            profile_document
        )
    )