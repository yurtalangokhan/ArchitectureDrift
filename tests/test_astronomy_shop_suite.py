from pathlib import Path

import pytest

from archdrift.experiments import (
    ExperimentResult,
    run_case,
)

PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)


EXPECTED_DETECTION = (
    (
        "AS-M01",
        False,
        True,
        True,
    ),
    (
        "AS-M02",
        True,
        False,
        True,
    ),
    (
        "AS-M03",
        True,
        True,
        True,
    ),
    (
        "AS-M04",
        False,
        False,
        False,
    ),
    (
        "AS-M05",
        False,
        True,
        True,
    ),
    (
        "AS-M06",
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
            "cases/astronomy-shop/"
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
def test_astronomy_shop_mutation_detection(
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

    non_runtime = (
        result.metrics
        .non_runtime
        .contract_violations
    )

    runtime = (
        result.metrics
        .runtime
        .contract_violations
    )

    fused = (
        result.metrics
        .fused
        .contract_violations
    )

    assert (
        non_runtime.false_positive
        == 0
    )

    assert (
        runtime.false_positive
        == 0
    )

    assert (
        fused.false_positive
        == 0
    )


def test_astronomy_shop_suite_detection_totals() -> None:
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
    assert runtime_tp == 4
    assert fused_tp == 5


def test_as_m04_is_deliberate_blind_spot() -> None:
    result = run_mutation(
        "AS-M04"
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