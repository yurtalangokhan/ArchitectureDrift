from pathlib import Path

import pytest

from archdrift.experiments.static_profile import (
    load_non_runtime_evidence_profile,
    load_static_evidence_profile,
)

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)


@pytest.mark.parametrize(
    (
        "subject_id",
        "expected_root",
        "expected_source_roots",
    ),
    (
        (
            "astronomy-shop",
            "subjects/astronomy-shop",
            3,
        ),
        (
            "eshop",
            "subjects/eshop",
            2,
        ),
        (
            "teastore",
            "subjects/teastore",
            0,
        ),
    ),
)
def test_static_evidence_profiles_load(
    subject_id: str,
    expected_root: str,
    expected_source_roots: int,
) -> None:
    profile = (
        load_static_evidence_profile(
            PROJECT_ROOT
            / "cases"
            / "real-evidence.yaml",
            subject_id=subject_id,
        )
    )

    assert (
        profile.subject_root
        == expected_root
    )

    assert (
        len(profile.source_roots)
        == expected_source_roots
    )

    assert profile.node_types

@pytest.mark.parametrize(
    (
        "subject_id",
        "deployment_kind",
    ),
    (
        (
            "astronomy-shop",
            "compose",
        ),
        (
            "eshop",
            "aspire",
        ),
        (
            "teastore",
            "compose",
        ),
    ),
)
def test_non_runtime_profiles_define_one_deployment_source(
    subject_id: str,
    deployment_kind: str,
) -> None:
    profile = (
        load_non_runtime_evidence_profile(
            PROJECT_ROOT
            / "cases"
            / "real-evidence.yaml",
            subject_id=subject_id,
        )
    )

    if deployment_kind == "compose":
        assert profile.compose is not None

        assert profile.aspire is None

    else:
        assert profile.aspire is not None

        assert profile.compose is None