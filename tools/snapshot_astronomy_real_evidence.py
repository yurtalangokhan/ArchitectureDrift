from __future__ import annotations

import argparse
from pathlib import Path

from archdrift.experiments.evidence_snapshot import (
    write_observation_snapshot,
)
from archdrift.experiments.non_runtime import (
    NonRuntimeEvidenceRunner,
)
from archdrift.experiments.static_profile import (
    load_non_runtime_evidence_profile,
)
from archdrift.model.mutation import (
    load_mutation_oracle,
)

MUTATIONS = (
    "AS-M01",
    "AS-M02",
    "AS-M03",
    "AS-M04",
    "AS-M05",
    "AS-M06",
)


EXPECTED_NON_RUNTIME = {
    "AS-M01": False,
    "AS-M02": True,
    "AS-M03": True,
    "AS-M04": False,
    "AS-M05": False,
    "AS-M06": False,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Freeze real Astronomy Shop mutant "
            "non-runtime evidence for empirical evaluation."
        ),
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


def main() -> int:
    args = parse_args()

    root = args.project_root.resolve()

    base_profile = (
        load_non_runtime_evidence_profile(
            root
            / "cases"
            / "real-evidence.yaml",
            subject_id="astronomy-shop",
        )
    )

    runner = NonRuntimeEvidenceRunner()

    for mutation_id in MUTATIONS:
        workspace = (
            root
            / "workspaces"
            / "mutants"
            / "astronomy-shop"
            / mutation_id
        )

        if not workspace.is_dir():
            raise FileNotFoundError(
                "Mutant workspace does not exist: "
                f"{workspace}"
            )

        output_root = (
            root
            / "evidence"
            / "real"
            / "experiments"
            / "astronomy-shop"
            / mutation_id
            / "non-runtime"
        )

        snapshot_file = (
            output_root
            / "observations.json"
        )

        if (
            snapshot_file.is_file()
            and not args.force
        ):
            print(
                "[SKIP] "
                f"{mutation_id}: "
                "snapshot already exists"
            )
            continue

        relative_workspace = (
            workspace
            .relative_to(root)
            .as_posix()
        )

        profile = (
            base_profile.model_copy(
                update={
                    "subject_root": (
                        relative_workspace
                    )
                }
            )
        )

        print()
        print(
            "[RUN] "
            f"{mutation_id} "
            "non-runtime acquisition"
        )

        result = runner.run(
            project_root=root,
            profile=profile,
            rule_pack_root=(
                root
                / "rules"
                / "semgrep"
                / "packs"
            ),
            output_root=output_root,
        )

        observations = (
            *result.deployment_observations,
            *result.source_static_observations,
        )

        write_observation_snapshot(
            path=snapshot_file,
            system_id="astronomy-shop",
            variant=mutation_id,
            observations=observations,
        )

        oracle = load_mutation_oracle(
            root
            / "mutations"
            / "astronomy-shop"
            / f"{mutation_id}.yaml"
        )

        expected_relations = (
            oracle
            .expected_delta
            .added_relation_identities
        )

        observed_relations = (
            result
            .views
            .combined
            .reconstruction
            .graph
            .relation_identities
        )

        detected = bool(
            expected_relations
            & observed_relations
        )

        expected = (
            EXPECTED_NON_RUNTIME[
                mutation_id
            ]
        )

        print(
            "[RESULT] "
            f"{mutation_id}: "
            f"non_runtime_detected="
            f"{detected}; "
            f"expected={expected}; "
            f"deployment_relations="
            f"{len(result.views.deployment.reconstruction.graph.relation_identities)}; "
            f"static_relations="
            f"{len(result.views.source_static.reconstruction.graph.relation_identities)}; "
            f"combined_relations="
            f"{len(result.views.combined.reconstruction.graph.relation_identities)}"
        )

        if detected is not expected:
            raise RuntimeError(
                "Astronomy non-runtime "
                "acceptance criterion failed: "
                f"{mutation_id}; "
                f"expected={expected}; "
                f"observed={detected}"
            )

        print(
            "[OK] "
            f"{mutation_id} "
            "non-runtime evidence frozen"
        )

    print()
    print(
        "[OK] Astronomy real non-runtime "
        "evidence acquisition completed."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )