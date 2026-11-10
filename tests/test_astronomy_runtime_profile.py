from archdrift.experiments.astronomy_runtime_profile import (
    AstronomyComposeMode,
    astronomy_runtime_profiles,
    require_astronomy_runtime_profile,
)
from archdrift.model.graph import (
    RelationType,
)


def test_astronomy_runtime_profile_inventory(
) -> None:
    profiles = (
        astronomy_runtime_profiles()
    )

    assert tuple(
        profile.mutation_id
        for profile in profiles
    ) == (
        "AS-M01",
        "AS-M02",
        "AS-M03",
        "AS-M04",
        "AS-M05",
        "AS-M06",
    )


def test_astronomy_core_runtime_profiles(
) -> None:
    for mutation_id in (
        "AS-M01",
        "AS-M02",
        "AS-M03",
        "AS-M04",
    ):
        profile = (
            require_astronomy_runtime_profile(
                mutation_id
            )
        )

        assert (
            profile.compose_mode
            is AstronomyComposeMode.CORE
        )


def test_astronomy_kafka_runtime_profiles_use_full_compose(
) -> None:
    for mutation_id in (
        "AS-M05",
        "AS-M06",
    ):
        profile = (
            require_astronomy_runtime_profile(
                mutation_id
            )
        )

        assert (
            profile.compose_mode
            is AstronomyComposeMode.FULL
        )


def test_as_m02_is_runtime_negative_control(
) -> None:
    profile = (
        require_astronomy_runtime_profile(
            "AS-M02"
        )
    )

    assert profile.expected_relation == (
        "payment",
        RelationType.CALLS,
        "shipping",
    )

    assert (
        profile.mutant_runtime_expected
        is False
    )


def test_as_m04_is_runtime_negative_control(
) -> None:
    profile = (
        require_astronomy_runtime_profile(
            "AS-M04"
        )
    )

    assert profile.expected_relation == (
        "cart",
        RelationType.CALLS,
        "recommendation",
    )

    assert (
        profile.mutant_runtime_expected
        is False
    )