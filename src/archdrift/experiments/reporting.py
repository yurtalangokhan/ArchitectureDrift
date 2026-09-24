"""Experiment result reporting."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from archdrift.analysis.conformance import (
    ConformanceReport,
)
from archdrift.analysis.metrics import (
    EvidenceViewMetrics,
)
from archdrift.experiments.suite import (
    EvidenceModeAggregate,
    ExperimentSuiteResult,
    SuiteCaseResult,
)
from archdrift.model.graph import (
    ReconstructionMode,
)


@dataclass(
    frozen=True,
    slots=True,
)
class ReportPaths:
    result_json: Path
    manifest_json: Path
    summary_csv: Path
    report_markdown: Path


def _format_metric(
    value: float | None,
) -> str:
    if value is None:
        return "N/A"

    return f"{value:.3f}"


def _mode_view(
    case: SuiteCaseResult,
    mode: ReconstructionMode,
) -> tuple[
    EvidenceViewMetrics,
    ConformanceReport,
]:
    result = case.result

    if (
        mode
        is ReconstructionMode.NON_RUNTIME
    ):
        return (
            result.metrics.non_runtime,
            result.non_runtime_conformance,
        )

    if (
        mode
        is ReconstructionMode.RUNTIME
    ):
        return (
            result.metrics.runtime,
            result.runtime_conformance,
        )

    if (
        mode
        is ReconstructionMode.FUSED
    ):
        return (
            result.metrics.fused,
            result.fused_conformance,
        )

    raise ValueError(
        f"Unsupported reconstruction mode: {mode!r}"
    )


def _write_result_json(
    result: ExperimentSuiteResult,
    path: Path,
) -> None:
    path.write_text(
        result.model_dump_json(
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_manifest_json(
    result: ExperimentSuiteResult,
    path: Path,
) -> None:
    document = {
        "suite_id": result.suite_id,
        "suite_file": result.suite_file,
        "git_commit": result.git_commit,
        "implementation_fingerprint": (
            result.implementation_fingerprint
        ),
        "suite_fingerprint": (
            result.suite_fingerprint
        ),
        "cases": [
            {
                "case_file": (
                    case.case_file
                ),
                "system_id": (
                    case.system_id
                ),
                "mutation_id": (
                    case.mutation_id
                ),
                "input_fingerprint": (
                    case
                    .input_manifest
                    .fingerprint
                ),
                "artifacts": [
                    artifact.model_dump(
                        mode="json"
                    )
                    for artifact in (
                        case
                        .input_manifest
                        .artifacts
                    )
                ],
            }
            for case in result.cases
        ],
    }

    path.write_text(
        json.dumps(
            document,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_csv(
    result: ExperimentSuiteResult,
    path: Path,
) -> None:
    fieldnames = [
        "system_id",
        "case_id",
        "mutation_id",
        "evidence_mode",
        "structural_tp",
        "structural_fp",
        "structural_fn",
        "structural_precision",
        "structural_recall",
        "structural_f1",
        "contract_tp",
        "contract_fp",
        "contract_fn",
        "contract_tn",
        "not_evaluable_positive",
        "not_evaluable_negative",
        "contract_precision",
        "contract_recall",
        "contract_f1",
        "evaluability_rate",
        "expected_violations",
        "detected_violations",
    ]

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for case in result.cases:
            for mode in (
                ReconstructionMode.NON_RUNTIME,
                ReconstructionMode.RUNTIME,
                ReconstructionMode.FUSED,
            ):
                metrics, report = (
                    _mode_view(
                        case,
                        mode,
                    )
                )

                structural = (
                    metrics.structural.overall
                )

                contract = (
                    metrics.contract_violations
                )

                writer.writerow(
                    {
                        "system_id": (
                            case.system_id
                        ),
                        "case_id": (
                            case.result.case_id
                        ),
                        "mutation_id": (
                            case.mutation_id
                        ),
                        "evidence_mode": (
                            mode.value
                        ),
                        "structural_tp": (
                            structural.true_positive
                        ),
                        "structural_fp": (
                            structural.false_positive
                        ),
                        "structural_fn": (
                            structural.false_negative
                        ),
                        "structural_precision": (
                            _format_metric(
                                structural.precision
                            )
                        ),
                        "structural_recall": (
                            _format_metric(
                                structural.recall
                            )
                        ),
                        "structural_f1": (
                            _format_metric(
                                structural.f1
                            )
                        ),
                        "contract_tp": (
                            contract.true_positive
                        ),
                        "contract_fp": (
                            contract.false_positive
                        ),
                        "contract_fn": (
                            contract.false_negative
                        ),
                        "contract_tn": (
                            contract.true_negative
                        ),
                        "not_evaluable_positive": (
                            contract
                            .not_evaluable_positive
                        ),
                        "not_evaluable_negative": (
                            contract
                            .not_evaluable_negative
                        ),
                        "contract_precision": (
                            _format_metric(
                                contract.precision
                            )
                        ),
                        "contract_recall": (
                            _format_metric(
                                contract.recall
                            )
                        ),
                        "contract_f1": (
                            _format_metric(
                                contract.f1
                            )
                        ),
                        "evaluability_rate": (
                            _format_metric(
                                contract.evaluability_rate
                            )
                        ),
                        "expected_violations": (
                            ";".join(
                                case
                                .result
                                .expected_violated_contracts
                            )
                        ),
                        "detected_violations": (
                            ";".join(
                                sorted(
                                    report
                                    .violated_contract_ids
                                )
                            )
                        ),
                    }
                )


def _aggregate_row(
    *,
    scope: str,
    mode: str,
    aggregate: EvidenceModeAggregate,
) -> str:
    structural = aggregate.structural

    contract = (
        aggregate.contract_violations
    )

    return (
        f"| {scope} "
        f"| {aggregate.case_count} "
        f"| {mode} "
        f"| {aggregate.fully_detected_case_count} "
        f"| {_format_metric(aggregate.full_detection_rate)} "
        f"| {_format_metric(structural.precision)} "
        f"| {_format_metric(structural.recall)} "
        f"| {_format_metric(structural.f1)} "
        f"| {_format_metric(contract.precision)} "
        f"| {_format_metric(contract.recall)} "
        f"| {_format_metric(contract.f1)} "
        f"| {_format_metric(contract.evaluability_rate)} |"
    )


def _write_markdown(
    result: ExperimentSuiteResult,
    path: Path,
) -> None:
    lines = [
        "# ArchitectureDrift Experiment Report",
        "",
        f"Suite: `{result.suite_id}`",
        "",
        f"Suite fingerprint: `{result.suite_fingerprint}`",
        "",
        (
            "Implementation fingerprint: "
            f"`{result.implementation_fingerprint}`"
        ),
        "",
    ]

    if result.git_commit is not None:
        lines.extend(
            [
                f"Git commit: `{result.git_commit}`",
                "",
            ]
        )

    lines.extend(
        [
            "## Aggregated Results",
            "",
            (
                "| Scope | Cases | Evidence | Fully detected | "
                "Detection rate | Structural P | Structural R | "
                "Structural F1 | Contract P | Contract R | "
                "Contract F1 | Evaluability |"
            ),
            (
                "|---|---:|---|---:|---:|---:|---:|---:|"
                "---:|---:|---:|---:|"
            ),
        ]
    )

    scopes = (
        *result.systems,
        result.overall,
    )

    for scope in scopes:
        lines.append(
            _aggregate_row(
                scope=scope.scope_id,
                mode="NON_RUNTIME",
                aggregate=scope.non_runtime,
            )
        )

        lines.append(
            _aggregate_row(
                scope=scope.scope_id,
                mode="RUNTIME",
                aggregate=scope.runtime,
            )
        )

        lines.append(
            _aggregate_row(
                scope=scope.scope_id,
                mode="FUSED",
                aggregate=scope.fused,
            )
        )

    lines.extend(
        [
            "",
            "## Per-Mutation Detection",
            "",
            (
                "| System | Mutation | Non-Runtime | "
                "Runtime | Fused |"
            ),
            "|---|---|---:|---:|---:|",
        ]
    )

    for case in result.cases:
        non_runtime = (
            case
            .result
            .metrics
            .non_runtime
            .contract_violations
        )

        runtime = (
            case
            .result
            .metrics
            .runtime
            .contract_violations
        )

        fused = (
            case
            .result
            .metrics
            .fused
            .contract_violations
        )

        lines.append(
            (
                f"| {case.system_id} "
                f"| {case.mutation_id} "
                f"| {'Yes' if non_runtime.false_negative == 0 else 'No'} "
                f"| {'Yes' if runtime.false_negative == 0 else 'No'} "
                f"| {'Yes' if fused.false_negative == 0 else 'No'} |"
            )
        )

    lines.extend(
        [
            "",
            "## Reproducibility",
            "",
            (
                "The suite manifest explicitly defines the case set. "
                "Each case includes SHA-256 digests of its baseline, "
                "contracts, mutation oracle, and evidence artifacts. "
                "The implementation fingerprint covers the ArchitectureDrift "
                "Python sources and pyproject.toml."
            ),
            "",
        ]
    )

    path.write_text(
        "\n".join(
            lines
        ),
        encoding="utf-8",
    )


def write_suite_reports(
    *,
    result: ExperimentSuiteResult,
    output_dir: str | Path,
) -> ReportPaths:
    destination = Path(
        output_dir
    )

    destination.mkdir(
        parents=True,
        exist_ok=True,
    )

    paths = ReportPaths(
        result_json=(
            destination
            / "suite-result.json"
        ),
        manifest_json=(
            destination
            / "suite-manifest.json"
        ),
        summary_csv=(
            destination
            / "suite-summary.csv"
        ),
        report_markdown=(
            destination
            / "suite-report.md"
        ),
    )

    _write_result_json(
        result,
        paths.result_json,
    )

    _write_manifest_json(
        result,
        paths.manifest_json,
    )

    _write_csv(
        result,
        paths.summary_csv,
    )

    _write_markdown(
        result,
        paths.report_markdown,
    )

    return paths