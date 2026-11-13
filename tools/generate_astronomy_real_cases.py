from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import yaml

SYSTEM_ID = "astronomy-shop"

MUTATIONS = (
    "AS-M01",
    "AS-M02",
    "AS-M03",
    "AS-M04",
    "AS-M05",
    "AS-M06",
)

COMPONENTS = {
    "ad": "SERVICE",
    "cart": "SERVICE",
    "checkout": "SERVICE",
    "currency": "SERVICE",
    "email": "SERVICE",
    "frontend": "SERVICE",
    "kafka": "BROKER",
    "payment": "SERVICE",
    "product-catalog": "SERVICE",
    "quote": "SERVICE",
    "recommendation": "SERVICE",
    "shipping": "SERVICE",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Freeze Astronomy Shop empirical evidence "
            "and generate real experiment cases."
        )
    )

    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
    )

    parser.add_argument(
        "--force",
        action="store_true",
    )

    return parser.parse_args()


def freeze_file(
    *,
    source: Path,
    destination: Path,
    force: bool,
) -> None:
    if not source.is_file():
        raise FileNotFoundError(
            f"Required experiment artifact missing: {source}"
        )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if destination.is_file():
        if (
            destination.read_bytes()
            == source.read_bytes()
        ):
            print(
                "[SKIP] unchanged: "
                f"{destination}"
            )
            return

        if not force:
            raise RuntimeError(
                "Frozen evidence already exists with "
                "different content: "
                f"{destination}. "
                "Use --force only when intentionally "
                "replacing empirical evidence."
            )

    shutil.copyfile(
        source,
        destination,
    )

    print(
        "[OK] frozen: "
        f"{destination}"
    )


def write_yaml(
    path: Path,
    document: object,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        yaml.safe_dump(
            document,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def case_document(
    *,
    mutation_id: str,
) -> dict[str, object]:
    evidence_root = (
        "evidence/real/experiments/"
        f"{SYSTEM_ID}/{mutation_id}"
    )

    return {
        "schema_version": "1.0",
        "case_id": (
            f"{SYSTEM_ID}-real-{mutation_id}"
        ),
        "system_id": SYSTEM_ID,
        "variant": mutation_id,
        "baseline_graph": (
            "graphs/baseline/"
            f"{SYSTEM_ID}/baseline.yaml"
        ),
        "contract_document": (
            f"contracts/{SYSTEM_ID}.yaml"
        ),
        "mutation_oracle": (
            "mutations/"
            f"{SYSTEM_ID}/{mutation_id}.yaml"
        ),
        "components": [
            {
                "id": component_id,
                "type": component_type,
            }
            for (
                component_id,
                component_type,
            ) in COMPONENTS.items()
        ],
        "non_runtime": {
            "observation_files": [
                (
                    f"{evidence_root}/"
                    "non-runtime/"
                    "observations.json"
                )
            ]
        },
        "runtime": {
            "otlp_files": [
                (
                    f"{evidence_root}/"
                    "runtime/"
                    "baseline.otlp.json"
                ),
                (
                    f"{evidence_root}/"
                    "runtime/"
                    "mutant.otlp.json"
                ),
            ]
        },
        "provenance_files": [
            (
                f"{evidence_root}/"
                "runtime/"
                "baseline.execution.json"
            ),
            (
                f"{evidence_root}/"
                "runtime/"
                "mutant.execution.json"
            ),
        ],
    }


def main() -> int:
    args = parse_args()

    root = (
        args.project_root
        .resolve()
    )

    real_case_root = (
        root
        / "cases"
        / "real"
        / SYSTEM_ID
    )

    for mutation_id in MUTATIONS:
        experiment_root = (
            root
            / "evidence"
            / "real"
            / "experiments"
            / SYSTEM_ID
            / mutation_id
        )

        non_runtime_snapshot = (
            experiment_root
            / "non-runtime"
            / "observations.json"
        )

        if not non_runtime_snapshot.is_file():
            raise FileNotFoundError(
                "Non-runtime snapshot missing: "
                f"{non_runtime_snapshot}. "
                "Run snapshot_astronomy_real_evidence.py first."
            )

        for variant in (
            "baseline",
            "mutant",
        ):
            source_trace = (
                root
                / "results"
                / "runtime"
                / "raw"
                / SYSTEM_ID
                / mutation_id
                / variant
                / "traces.otlp.json"
            )

            source_record = (
                root
                / "results"
                / "runtime"
                / "records"
                / SYSTEM_ID
                / mutation_id
                / f"{variant}.json"
            )

            freeze_file(
                source=source_trace,
                destination=(
                    experiment_root
                    / "runtime"
                    / f"{variant}.otlp.json"
                ),
                force=args.force,
            )

            freeze_file(
                source=source_record,
                destination=(
                    experiment_root
                    / "runtime"
                    / f"{variant}.execution.json"
                ),
                force=args.force,
            )

        case_file = (
            real_case_root
            / f"{mutation_id}.yaml"
        )

        write_yaml(
            case_file,
            case_document(
                mutation_id=mutation_id,
            ),
        )

        print(
            "[OK] case: "
            f"{case_file}"
        )

    suite_file = (
        root
        / "cases"
        / "real"
        / "astronomy-suite.yaml"
    )

    write_yaml(
        suite_file,
        {
            "schema_version": "1.0",
            "suite_id": (
                "architecture-drift-"
                "astronomy-real"
            ),
            "metadata": {
                "purpose": (
                    "Empirical Astronomy Shop controlled "
                    "mutation evaluation using acquired "
                    "non-runtime and runtime evidence."
                ),
                "revision": "REAL-AS-01",
            },
            "cases": [
                (
                    "cases/real/"
                    f"{SYSTEM_ID}/{mutation_id}.yaml"
                )
                for mutation_id in MUTATIONS
            ],
        },
    )

    print()
    print(
        "[OK] Astronomy real case generation completed."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )