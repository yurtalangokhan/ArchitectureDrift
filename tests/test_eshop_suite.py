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
        "ES-M01",
        False,
        True,
        True,
    ),
    (
        "ES-M02",
        True,
        False,
        True,
    ),
    (
        "ES-M03",
        True,
        True,
        True,
    ),
    (
        "ES-M04",
        False,
        False,
        False,
    ),
    (
        "ES-M05",
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
            "cases/eshop/"
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
def test_eshop_mutation_detection(
    mutation_id: str,
    expected_non_runtime: bool,
    expected_runtime: bool,
    expected_fused: bool,
) -> None:
    result = run_mutation(
        mutation_id
    )

    assert result.mutation_id == mutation_id

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


def test_eshop_suite_detection_totals() -> None:
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


def test_eshop_no_false_positive_contract_detection() -> None:
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


def test_es_m04_is_deliberate_blind_spot() -> None:
    result = run_mutation(
        "ES-M04"
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