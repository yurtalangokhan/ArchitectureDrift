from pathlib import Path

import pytest

from archdrift.experiments import (
    ExperimentResult,
    run_case,
)
from archdrift.model import (
    RelationType,
)

PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)


EXPECTED_DETECTION = (
    (
        "TS-M01",
        False,
        True,
        True,
    ),
    (
        "TS-M02",
        True,
        False,
        True,
    ),
    (
        "TS-M03",
        True,
        True,
        True,
    ),
    (
        "TS-M04",
        False,
        False,
        False,
    ),
    (
        "TS-M05",
        False,
        True,
        True,
    ),
)


def run_mutation(
    mutation_id: str,
) -> ExperimentResult:
    return run_case(
        project_root=PROJECT_ROOT,
        case_file=(
            "cases/teastore/"
            f"{mutation_id}.yaml"
        ),
    )


@pytest.mark.parametrize(
    (
        "mutation_id",
        "expected_non_runtime",
        "expected_runtime",
        "expected_fused",
    ),
    EXPECTED_DETECTION,
)
def test_teastore_mutation_detection(
    mutation_id: str,
    expected_non_runtime: bool,
    expected_runtime: bool,
    expected_fused: bool,
) -> None:
    result = run_mutation(
        mutation_id
    )

    assert (
        result.mutation_id
        == mutation_id
    )

    assert (
        result.mutation_delta.change_count
        == 1
    )

    assert (
        result
        .non_runtime_detected_expected_violation
        is expected_non_runtime
    )

    assert (
        result
        .runtime_detected_expected_violation
        is expected_runtime
    )

    assert (
        result
        .fused_detected_expected_violation
        is expected_fused
    )


def test_teastore_suite_detection_totals() -> None:
    results = tuple(
        run_mutation(
            mutation_id
        )
        for (
            mutation_id,
            _,
            _,
            _,
        ) in EXPECTED_DETECTION
    )

    non_runtime_tp = sum(
        result.metrics
        .non_runtime
        .contract_violations
        .true_positive
        for result in results
    )

    runtime_tp = sum(
        result.metrics
        .runtime
        .contract_violations
        .true_positive
        for result in results
    )

    fused_tp = sum(
        result.metrics
        .fused
        .contract_violations
        .true_positive
        for result in results
    )

    assert non_runtime_tp == 2
    assert runtime_tp == 3
    assert fused_tp == 4


def test_teastore_has_no_contract_false_positives() -> None:
    for (
        mutation_id,
        _,
        _,
        _,
    ) in EXPECTED_DETECTION:
        result = run_mutation(
            mutation_id
        )

        assert (
            result.metrics
            .non_runtime
            .contract_violations
            .false_positive
            == 0
        )

        assert (
            result.metrics
            .runtime
            .contract_violations
            .false_positive
            == 0
        )

        assert (
            result.metrics
            .fused
            .contract_violations
            .false_positive
            == 0
        )


def test_ts_m04_is_deliberate_blind_spot() -> None:
    result = run_mutation(
        "TS-M04"
    )

    assert (
        result
        .non_runtime_detected_expected_violation
        is False
    )

    assert (
        result
        .runtime_detected_expected_violation
        is False
    )

    assert (
        result
        .fused_detected_expected_violation
        is False
    )


def test_ts_m05_preserves_discovery_and_detects_illegal_call() -> None:
    result = run_mutation(
        "TS-M05"
    )

    discovery = (
        "webui",
        RelationType.DISCOVERS_VIA,
        "registry",
    )

    illegal_call = (
        "webui",
        RelationType.CALLS,
        "registry",
    )

    # Non-runtime evidence reconstructs the legitimate discovery edge.
    assert discovery in (
        result.views
        .non_runtime
        .graph
        .relation_identities
    )

    assert illegal_call not in (
        result.views
        .non_runtime
        .graph
        .relation_identities
    )

    # Runtime evidence observes the mutation.
    assert illegal_call in (
        result.views
        .runtime
        .graph
        .relation_identities
    )

    # Fused graph preserves both semantics.
    assert discovery in (
        result.views
        .fused
        .graph
        .relation_identities
    )

    assert illegal_call in (
        result.views
        .fused
        .graph
        .relation_identities
    )

    assert (
        result
        .fused_conformance
        .violated_contract_ids
        == frozenset(
            {
                "TS-C005",
            }
        )
    )

def test_teastore_baseline_satisfies_all_contracts() -> None:
    result = run_mutation(
        "TS-M01"
    )

    assert (
        result
        .baseline_conformance
        .violated_contract_ids
        == frozenset()
    )

    assert (
        result
        .baseline_conformance
        .not_evaluable_contract_ids
        == frozenset()
    )