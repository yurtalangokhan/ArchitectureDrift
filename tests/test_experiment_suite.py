from pathlib import Path

import pytest

from archdrift.experiments import (
    run_suite,
)


PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)


@pytest.fixture(scope="module")
def suite_result():
    return run_suite(
        project_root=PROJECT_ROOT,
        suite_file="cases/suite.yaml",
    )


def test_suite_contains_all_mutations(
    suite_result,
) -> None:
    assert len(
        suite_result.cases
    ) == 16

    assert {
        case.system_id
        for case in suite_result.cases
    } == {
        "astronomy-shop",
        "eshop",
        "teastore",
    }


def test_suite_system_case_counts(
    suite_result,
) -> None:
    counts = {
        aggregate.scope_id: (
            aggregate.case_count
        )
        for aggregate in (
            suite_result.systems
        )
    }

    assert counts == {
        "astronomy-shop": 6,
        "eshop": 5,
        "teastore": 5,
    }


def test_suite_expected_detection_counts(
    suite_result,
) -> None:
    overall = (
        suite_result.overall
    )

    assert (
        overall.non_runtime
        .fully_detected_case_count
        == 6
    )

    assert (
        overall.runtime
        .fully_detected_case_count
        == 10
    )

    assert (
        overall.fused
        .fully_detected_case_count
        == 13
    )


def test_fused_recall_exceeds_individual_channels(
    suite_result,
) -> None:
    overall = (
        suite_result.overall
    )

    non_runtime_recall = (
        overall
        .non_runtime
        .contract_violations
        .recall
    )

    runtime_recall = (
        overall
        .runtime
        .contract_violations
        .recall
    )

    fused_recall = (
        overall
        .fused
        .contract_violations
        .recall
    )

    assert non_runtime_recall == pytest.approx(
        6 / 16
    )

    assert runtime_recall == pytest.approx(
        10 / 16
    )

    assert fused_recall == pytest.approx(
        13 / 16
    )

    assert fused_recall > runtime_recall
    assert fused_recall > non_runtime_recall


def test_suite_has_no_contract_false_positives(
    suite_result,
) -> None:
    overall = (
        suite_result.overall
    )

    assert (
        overall
        .non_runtime
        .contract_violations
        .false_positive
        == 0
    )

    assert (
        overall
        .runtime
        .contract_violations
        .false_positive
        == 0
    )

    assert (
        overall
        .fused
        .contract_violations
        .false_positive
        == 0
    )


def test_suite_fingerprint_is_present(
    suite_result,
) -> None:
    assert len(
        suite_result.suite_fingerprint
    ) == 64

    assert len(
        suite_result.implementation_fingerprint
    ) == 64