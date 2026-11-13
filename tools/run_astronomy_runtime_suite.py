from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from archdrift.experiments.astronomy_runtime_profile import (
    AstronomyRuntimeProfile,
    astronomy_runtime_profiles,
)
from archdrift.experiments.otlp_capture import (
    merge_otlp_json_lines,
    relation_present,
)
from archdrift.experiments.runtime_execution import (
    RuntimeVariant,
)
from archdrift.model.graph import (
    NodeType,
)

SYSTEM_ID = "astronomy-shop"


@dataclass(
    frozen=True,
    slots=True,
)
class RuntimeArtifactPaths:
    raw_trace: Path
    normalized_trace: Path
    execution_record: Path


@dataclass(
    frozen=True,
    slots=True,
)
class RuntimeArtifactStatus:
    complete: bool
    reason: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Resume the Astronomy Shop runtime experiment suite "
            "without rerunning completed executions."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Inspect runtime artifacts and report which executions "
            "would run without starting Docker."
        ),
    )

    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
    )

    return parser.parse_args()


def artifact_paths(
    *,
    project_root: Path,
    mutation_id: str,
    variant: RuntimeVariant,
) -> RuntimeArtifactPaths:
    output_directory = (
        project_root
        / "results"
        / "runtime"
        / "raw"
        / SYSTEM_ID
        / mutation_id
        / variant.value
    )

    return RuntimeArtifactPaths(
        raw_trace=(
            output_directory
            / "traces.otlp.jsonl"
        ),
        normalized_trace=(
            output_directory
            / "traces.otlp.json"
        ),
        execution_record=(
            project_root
            / "results"
            / "runtime"
            / "records"
            / SYSTEM_ID
            / mutation_id
            / f"{variant.value}.json"
        ),
    )


def load_node_types(
    project_root: Path,
) -> dict[str, NodeType]:
    configuration_path = (
        project_root
        / "cases"
        / "real-evidence.yaml"
    )

    configuration = yaml.safe_load(
        configuration_path.read_text(
            encoding="utf-8",
        )
    )

    raw_types = (
        configuration[
            "subjects"
        ][
            SYSTEM_ID
        ][
            "scope"
        ][
            "node_types"
        ]
    )

    return {
        name: NodeType(value)
        for name, value in raw_types.items()
    }


def expected_detection(
    *,
    profile: AstronomyRuntimeProfile,
    variant: RuntimeVariant,
) -> bool:
    if variant is RuntimeVariant.BASELINE:
        return False

    return profile.mutant_runtime_expected


def ensure_normalized_trace(
    paths: RuntimeArtifactPaths,
) -> tuple[
    bool,
    str,
]:
    if (
        not paths.raw_trace.is_file()
        or paths.raw_trace.stat().st_size == 0
    ):
        return (
            False,
            "raw OTLP JSONL trace is missing",
        )

    if (
        paths.normalized_trace.is_file()
        and paths.normalized_trace.stat().st_size > 0
    ):
        return (
            True,
            "normalized OTLP trace exists",
        )

    try:
        record_count = merge_otlp_json_lines(
            source=paths.raw_trace,
            destination=paths.normalized_trace,
        )

    except Exception as exc:
        return (
            False,
            "raw trace could not be normalized: "
            f"{type(exc).__name__}: {exc}",
        )

    return (
        True,
        (
            "normalized trace reconstructed from "
            f"{record_count} OTLP JSONL record(s)"
        ),
    )


def inspect_execution(
    *,
    project_root: Path,
    node_types: dict[str, NodeType],
    profile: AstronomyRuntimeProfile,
    variant: RuntimeVariant,
) -> RuntimeArtifactStatus:
    paths = artifact_paths(
        project_root=project_root,
        mutation_id=profile.mutation_id,
        variant=variant,
    )

    normalized, normalization_reason = (
        ensure_normalized_trace(
            paths
        )
    )

    if not normalized:
        return RuntimeArtifactStatus(
            complete=False,
            reason=normalization_reason,
        )

    if not paths.execution_record.is_file():
        return RuntimeArtifactStatus(
            complete=False,
            reason=(
                "runtime execution record is missing"
            ),
        )

    (
        source,
        relation,
        target,
    ) = profile.expected_relation

    try:
        detected = relation_present(
            trace_file=paths.normalized_trace,
            node_types=node_types,
            source=source,
            relation=relation,
            target=target,
        )

    except Exception as exc:
        return RuntimeArtifactStatus(
            complete=False,
            reason=(
                "normalized trace could not be evaluated: "
                f"{type(exc).__name__}: {exc}"
            ),
        )

    expected = expected_detection(
        profile=profile,
        variant=variant,
    )

    if detected != expected:
        return RuntimeArtifactStatus(
            complete=False,
            reason=(
                "runtime acceptance criterion mismatch: "
                f"{source} "
                f"{relation.value} "
                f"{target}; "
                f"expected={expected}, "
                f"observed={detected}"
            ),
        )

    return RuntimeArtifactStatus(
        complete=True,
        reason=(
            "trace and execution record are valid; "
            "runtime acceptance criterion passed"
        ),
    )


def run_execution(
    *,
    project_root: Path,
    profile: AstronomyRuntimeProfile,
    variant: RuntimeVariant,
) -> None:
    command = [
        sys.executable,
        "tools/run_astronomy_runtime.py",
        "--mutation",
        profile.mutation_id,
        "--variant",
        variant.value,
        "--force-output",
    ]

    if variant is RuntimeVariant.MUTANT:
        command.append(
            "--replace-mutant"
        )

    print()
    print("=" * 80)
    print(
        "[RUN] "
        f"{profile.mutation_id} / "
        f"{variant.value}"
    )
    print("=" * 80)

    process = subprocess.run(
        command,
        cwd=project_root,
        check=False,
    )

    if process.returncode != 0:
        raise SystemExit(
            "Runtime suite failed: "
            f"{profile.mutation_id}/"
            f"{variant.value}"
        )


def main() -> int:
    args = parse_args()

    project_root = (
        args.project_root.resolve()
    )

    node_types = load_node_types(
        project_root
    )

    skipped = 0
    executed = 0

    profiles = (
        astronomy_runtime_profiles()
    )

    for profile in profiles:
        for variant in (
            RuntimeVariant.BASELINE,
            RuntimeVariant.MUTANT,
        ):
            status = inspect_execution(
                project_root=project_root,
                node_types=node_types,
                profile=profile,
                variant=variant,
            )

            execution_name = (
                f"{profile.mutation_id}/"
                f"{variant.value}"
            )

            if status.complete:
                skipped += 1

                print(
                    "[SKIP] "
                    f"{execution_name}: "
                    f"{status.reason}"
                )

                continue

            print(
                "[PENDING] "
                f"{execution_name}: "
                f"{status.reason}"
            )

            if args.dry_run:
                continue

            run_execution(
                project_root=project_root,
                profile=profile,
                variant=variant,
            )

            post_status = (
                inspect_execution(
                    project_root=project_root,
                    node_types=node_types,
                    profile=profile,
                    variant=variant,
                )
            )

            if not post_status.complete:
                raise SystemExit(
                    "Execution completed but "
                    "artifact validation failed: "
                    f"{execution_name}: "
                    f"{post_status.reason}"
                )

            executed += 1

            print(
                "[OK] "
                f"{execution_name}: "
                f"{post_status.reason}"
            )

    print()
    print("=" * 80)

    if args.dry_run:
        print(
            "[DRY-RUN] Astronomy runtime "
            "artifact inventory completed."
        )
    else:
        print(
            "[OK] Astronomy runtime "
            "suite completed."
        )

    print(
        f"[SUMMARY] skipped={skipped} "
        f"executed={executed}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())