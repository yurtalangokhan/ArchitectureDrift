import csv
import json
from pathlib import Path

from archdrift.experiments import (
    run_suite,
    write_suite_reports,
)


PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)


def test_suite_reports_are_generated(
    tmp_path: Path,
) -> None:
    result = run_suite(
        project_root=PROJECT_ROOT,
        suite_file="cases/suite.yaml",
    )

    paths = write_suite_reports(
        result=result,
        output_dir=tmp_path,
    )

    assert paths.result_json.is_file()
    assert paths.manifest_json.is_file()
    assert paths.summary_csv.is_file()
    assert paths.report_markdown.is_file()


def test_suite_csv_contains_three_rows_per_case(
    tmp_path: Path,
) -> None:
    result = run_suite(
        project_root=PROJECT_ROOT,
        suite_file="cases/suite.yaml",
    )

    paths = write_suite_reports(
        result=result,
        output_dir=tmp_path,
    )

    with paths.summary_csv.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        rows = list(
            csv.DictReader(
                file
            )
        )

    assert len(rows) == 48


def test_suite_manifest_contains_fingerprints(
    tmp_path: Path,
) -> None:
    result = run_suite(
        project_root=PROJECT_ROOT,
        suite_file="cases/suite.yaml",
    )

    paths = write_suite_reports(
        result=result,
        output_dir=tmp_path,
    )

    document = json.loads(
        paths.manifest_json.read_text(
            encoding="utf-8",
        )
    )

    assert (
        document["suite_fingerprint"]
        == result.suite_fingerprint
    )

    assert len(
        document["cases"]
    ) == 16

    for case in document["cases"]:
        assert len(
            case["input_fingerprint"]
        ) == 64


def test_markdown_contains_overall_summary(
    tmp_path: Path,
) -> None:
    result = run_suite(
        project_root=PROJECT_ROOT,
        suite_file="cases/suite.yaml",
    )

    paths = write_suite_reports(
        result=result,
        output_dir=tmp_path,
    )

    report = (
        paths.report_markdown.read_text(
            encoding="utf-8",
        )
    )

    assert (
        "# ArchitectureDrift Experiment Report"
        in report
    )

    assert "| overall " in report
    assert "NON_RUNTIME" in report
    assert "RUNTIME" in report
    assert "FUSED" in report