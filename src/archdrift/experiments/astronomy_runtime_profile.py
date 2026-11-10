from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
)

from archdrift.model.graph import (
    RelationIdentity,
    RelationType,
)


class AstronomyRuntimeProfileError(
    ValueError
):
    """Raised for an unsupported Astronomy Shop runtime mutation."""


class AstronomyComposeMode(
    StrEnum
):
    CORE = "core"
    FULL = "full"


class AstronomyWorkload(
    StrEnum
):
    CHECKOUT = "checkout"


class AstronomyRuntimeProfile(
    BaseModel
):
    """
    Immutable execution metadata for one Astronomy Shop mutation.

    This model describes experiment orchestration only. It does not
    participate in evidence inference or mutation detection.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    mutation_id: str

    compose_mode: AstronomyComposeMode

    build_services: tuple[
        str,
        ...,
    ]

    workload: AstronomyWorkload

    expected_relation: RelationIdentity

    mutant_runtime_expected: bool


_PROFILES: dict[
    str,
    AstronomyRuntimeProfile,
] = {
    "AS-M01": AstronomyRuntimeProfile(
        mutation_id="AS-M01",
        compose_mode=(
            AstronomyComposeMode.CORE
        ),
        build_services=(
            "checkout",
        ),
        workload=(
            AstronomyWorkload.CHECKOUT
        ),
        expected_relation=(
            "checkout",
            RelationType.CALLS,
            "recommendation",
        ),
        mutant_runtime_expected=True,
    ),
    "AS-M02": AstronomyRuntimeProfile(
        mutation_id="AS-M02",
        compose_mode=(
            AstronomyComposeMode.CORE
        ),
        build_services=(
            "payment",
        ),
        workload=(
            AstronomyWorkload.CHECKOUT
        ),
        expected_relation=(
            "payment",
            RelationType.CALLS,
            "shipping",
        ),
        mutant_runtime_expected=False,
    ),
    "AS-M03": AstronomyRuntimeProfile(
        mutation_id="AS-M03",
        compose_mode=(
            AstronomyComposeMode.CORE
        ),
        build_services=(
            "frontend",
        ),
        workload=(
            AstronomyWorkload.CHECKOUT
        ),
        expected_relation=(
            "frontend",
            RelationType.CALLS,
            "payment",
        ),
        mutant_runtime_expected=True,
    ),
    "AS-M04": AstronomyRuntimeProfile(
        mutation_id="AS-M04",
        compose_mode=(
            AstronomyComposeMode.CORE
        ),
        build_services=(
            "cart",
        ),
        workload=(
            AstronomyWorkload.CHECKOUT
        ),
        expected_relation=(
            "cart",
            RelationType.CALLS,
            "recommendation",
        ),
        mutant_runtime_expected=False,
    ),
    "AS-M05": AstronomyRuntimeProfile(
        mutation_id="AS-M05",
        compose_mode=(
            AstronomyComposeMode.FULL
        ),
        build_services=(
            "frontend",
        ),
        workload=(
            AstronomyWorkload.CHECKOUT
        ),
        expected_relation=(
            "frontend",
            RelationType.PUBLISHES_TO,
            "kafka",
        ),
        mutant_runtime_expected=True,
    ),
    "AS-M06": AstronomyRuntimeProfile(
        mutation_id="AS-M06",
        compose_mode=(
            AstronomyComposeMode.FULL
        ),
        build_services=(
            "checkout",
        ),
        workload=(
            AstronomyWorkload.CHECKOUT
        ),
        expected_relation=(
            "checkout",
            RelationType.SUBSCRIBES_TO,
            "kafka",
        ),
        mutant_runtime_expected=True,
    ),
}


def astronomy_runtime_profiles(
) -> tuple[
    AstronomyRuntimeProfile,
    ...,
]:
    return tuple(
        _PROFILES[
            mutation_id
        ]
        for mutation_id in sorted(
            _PROFILES
        )
    )


def require_astronomy_runtime_profile(
    mutation_id: str,
) -> AstronomyRuntimeProfile:
    try:
        return _PROFILES[
            mutation_id
        ]

    except KeyError as exc:
        raise AstronomyRuntimeProfileError(
            "Unsupported Astronomy Shop "
            "runtime mutation: "
            f"{mutation_id!r}"
        ) from exc