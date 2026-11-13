from __future__ import annotations

from pathlib import Path

from archdrift.experiments import (
    run_suite,
    write_suite_reports,
)

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

SUITE_FILE = (
    "cases/real/"
    "astronomy-suite.yaml"
)

EXPECTED_DETECTION = {
    "AS-M01": (
        False,
        True,
        True,
    ),
    "AS-M02": (
        True,
        False,
        True,
    ),
    "AS-M03": (
        True,
        True,
        True,
    ),
    "AS-M04": (
        False,
        False,
        False,
    ),
    "AS-M05": (
        False,
        True,
        True,
    ),
    "AS-M06": (
        False,
        True,
        True,
    ),
}


def main() -> int:
    result = run_suite(
        project_root=PROJECT_ROOT,
        suite_file=SUITE_FILE,
    )

    print()
    print(
        "Astronomy Shop real-evidence detection"
    )
    print(
        "=" * 72
    )

    for case in result.cases:
        mutation_id = (
            case.mutation_id
        )

        experiment = (
            case.result
        )

        observed = (
            experiment
            .non_runtime_detected_expected_violation,
            experiment
            .runtime_detected_expected_violation,
            experiment
            .fused_detected_expected_violation,
        )

        expected = (
            EXPECTED_DETECTION[
                mutation_id
            ]
        )

        print(
            f"{mutation_id}: "
            f"NR={observed[0]} "
            f"R={observed[1]} "
            f"F={observed[2]}"
        )

        if observed != expected:
            raise RuntimeError(
                "Empirical detection acceptance "
                "criterion failed for "
                f"{mutation_id}. "
                f"Expected={expected}, "
                f"observed={observed}"
            )

    output_directory = (
        PROJECT_ROOT
        / "results"
        / "real-experiments"
        / "astronomy-shop"
    )

    paths = write_suite_reports(
        result=result,
        output_dir=output_directory,
    )

    print()
    print(
        "[OK] Astronomy empirical suite passed."
    )

    print(
        f"[RESULT] {paths.result_json}"
    )
    print(
        f"[MANIFEST] {paths.manifest_json}"
    )
    print(
        f"[CSV] {paths.summary_csv}"
    )
    print(
        f"[REPORT] {paths.report_markdown}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )