from __future__ import annotations

import argparse
import json
from pathlib import Path

from archdrift.experiments.non_runtime import (
    NonRuntimeEvidenceRunner,
)
from archdrift.experiments.static_profile import (
    load_non_runtime_evidence_profile,
)


def _graph_summary(
    view,
) -> dict[str, object]:
    graph = (
        view
        .reconstruction
        .graph
    )

    return {
        "included_observations": (
            view.scoped.included_count
        ),
        "excluded_observations": (
            view.scoped.excluded_count
        ),
        "nodes": len(
            graph.node_ids
        ),
        "relations": len(
            graph.relation_identities
        ),
        "graph": (
            graph.model_dump(
                mode="json",
            )
        ),
        "relation_support": [
            support.model_dump(
                mode="json",
            )
            for support in (
                view
                .reconstruction
                .relation_support
            )
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--subject",
        required=True,
        choices=(
            "astronomy-shop",
            "eshop",
            "teastore",
        ),
    )

    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
    )

    args = parser.parse_args()

    root = (
        args.project_root
        .resolve()
    )

    profile = (
        load_non_runtime_evidence_profile(
            root
            / "cases"
            / "real-evidence.yaml",
            subject_id=args.subject,
        )
    )

    result = (
        NonRuntimeEvidenceRunner()
        .run(
            project_root=root,
            profile=profile,
            rule_pack_root=(
                root
                / "rules"
                / "semgrep"
                / "packs"
            ),
        )
    )

    deployment = (
        result.views.deployment
    )

    source_static = (
        result.views.source_static
    )

    combined = (
        result.views.combined
    )

    output_file = (
        root
        / "results"
        / "real-baseline"
        / args.subject
        / "non-runtime.json"
    )

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    document = {
        "schema_version": "1.0",
        "subject_id": (
            result.subject_id
        ),
        "source_static": {
            "findings": len(
                result.source_static_findings
            ),
            "resolved": (
                result
                .static_resolution
                .resolved_count
            ),
            "unresolved": (
                result
                .static_resolution
                .unresolved_count
            ),
        },
        "views": {
            "deployment": (
                _graph_summary(
                    deployment
                )
            ),
            "source_static": (
                _graph_summary(
                    source_static
                )
            ),
            "combined": (
                _graph_summary(
                    combined
                )
            ),
        },
    }

    output_file.write_text(
        json.dumps(
            document,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        f"Subject: {result.subject_id}"
    )

    print(
        "Static findings: "
        f"{len(result.source_static_findings)}"
    )

    print(
        "Static resolved: "
        f"{result.static_resolution.resolved_count}"
    )

    print(
        "Static unresolved: "
        f"{result.static_resolution.unresolved_count}"
    )

    print()

    print(
        "Deployment graph: "
        f"{len(deployment.reconstruction.graph.node_ids)} nodes, "
        f"{len(deployment.reconstruction.graph.relation_identities)} relations"
    )

    print(
        "Source-static graph: "
        f"{len(source_static.reconstruction.graph.node_ids)} nodes, "
        f"{len(source_static.reconstruction.graph.relation_identities)} relations"
    )

    print(
        "Combined graph: "
        f"{len(combined.reconstruction.graph.node_ids)} nodes, "
        f"{len(combined.reconstruction.graph.relation_identities)} relations"
    )

    print()

    print(
        f"Result: {output_file}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )