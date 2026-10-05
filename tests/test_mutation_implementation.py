from pathlib import Path

from archdrift.model import (
    load_mutation_implementation_manifest,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)


def test_real_mutation_implementation_manifest_contains_all_cases() -> None:
    manifest = (
        load_mutation_implementation_manifest(
            PROJECT_ROOT
            / "mutations"
            / "implementation-manifest.yaml"
        )
    )

    assert len(
        manifest.implementations
    ) == 16

    assert {
        implementation.mutation_id
        for implementation
        in manifest.implementations
    } == {
        "AS-M01",
        "AS-M02",
        "AS-M03",
        "AS-M04",
        "AS-M05",
        "AS-M06",
        "ES-M01",
        "ES-M02",
        "ES-M03",
        "ES-M04",
        "ES-M05",
        "TS-M01",
        "TS-M02",
        "TS-M03",
        "TS-M04",
        "TS-M05",
    }