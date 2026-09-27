from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from archdrift.adapters.compose import (
    ComposeAdapter,
)
from archdrift.analysis.baseline import (
    BaselineReconstructionAnalysis,
    analyze_baseline_reconstruction,
)
from archdrift.analysis.scope import (
    EvidenceScope,
)
from archdrift.model.graph import (
    ArchitectureGraph,
    NodeType,
)


SYSTEM_ID = "astronomy-shop"

ASTRONOMY_NODE_TYPES = {
    "ad": NodeType.SERVICE,
    "cart": NodeType.SERVICE,
    "checkout": NodeType.SERVICE,
    "currency": NodeType.SERVICE,
    "email": NodeType.SERVICE,
    "frontend": NodeType.SERVICE,
    "kafka": NodeType.BROKER,
    "payment": NodeType.SERVICE,
    "product-catalog": NodeType.SERVICE,
    "quote": NodeType.SERVICE,
    "recommendation": NodeType.SERVICE,
    "shipping": NodeType.SERVICE,
}


def load_architecture_graph(
    path: Path,
) -> ArchitectureGraph:
    if not path.is_file():
        raise FileNotFoundError(
            f"Architecture graph does not exist: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        document = yaml.safe_load(
            file
        )

    if not isinstance(
        document,
        dict,
    ):
        raise ValueError(
            f"Architecture graph root must be a mapping: {path}"
        )

    return ArchitectureGraph.model_validate(
        document
    )


def relation_to_json(
    relation: tuple[
        str,
        object,
        str,
    ],
) -> list[str]:
    source, relation_type, target = relation

    value = getattr(
        relation_type,
        "value",
        str(relation_type),
    )

    return [
        source,
        value,
        target,
    ]


def analysis_document(
    analysis: BaselineReconstructionAnalysis,
) -> dict[str, Any]:
    coverage = analysis.coverage
    graph = analysis.reconstruction.graph

    return {
        "schema_version": "1.0",
        "system_id": SYSTEM_ID,
        "evidence_mode": "NON_RUNTIME",
        "scope": {
            "included_observations": (
                analysis.scoped.included_count
            ),
            "excluded_observations": (
                analysis.scoped.excluded_count
            ),
        },
        "reconstruction": {
            "node_count": len(
                graph.node_ids
            ),
            "relation_count": len(
                graph.relation_identities
            ),
            "nodes": sorted(
                graph.node_ids
            ),
            "relations": [
                relation_to_json(
                    relation
                )
                for relation in sorted(
                    graph.relation_identities,
                    key=lambda item: (
                        item[0],
                        item[1].value,
                        item[2],
                    ),
                )
            ],
        },
        "coverage": {
            "baseline_node_count": (
                coverage.baseline_node_count
            ),
            "observed_baseline_node_count": (
                coverage.observed_baseline_node_count
            ),
            "node_coverage": (
                coverage.node_coverage
            ),
            "baseline_relation_count": (
                coverage.baseline_relation_count
            ),
            "observed_baseline_relation_count": (
                coverage.observed_baseline_relation_count
            ),
            "relation_coverage": (
                coverage.relation_coverage
            ),
            "unexpected_nodes": sorted(
                coverage.unexpected_node_ids
            ),
            "not_observed_nodes": sorted(
                coverage.not_observed_node_ids
            ),
            "unexpected_relations": [
                relation_to_json(
                    relation
                )
                for relation in sorted(
                    coverage.unexpected_relation_identities,
                    key=lambda item: (
                        item[0],
                        item[1].value,
                        item[2],
                    ),
                )
            ],
            "not_observed_relations": [
                relation_to_json(
                    relation
                )
                for relation in sorted(
                    coverage.not_observed_relation_identities,
                    key=lambda item: (
                        item[0],
                        item[1].value,
                        item[2],
                    ),
                )
            ],
        },
    }


def percentage(
    value: float | None,
) -> str:
    if value is None:
        return "N/A"

    return f"{value * 100:.2f}%"


def main() -> int:
    project_root = (
        Path.cwd().resolve()
    )

    evidence_path = (
        project_root
        / "evidence"
        / "real"
        / "non-runtime"
        / SYSTEM_ID
        / "compose.resolved.json"
    )

    baseline_path = (
        project_root
        / "graphs"
        / "baseline"
        / SYSTEM_ID
        / "baseline.yaml"
    )

    if not evidence_path.is_file():
        raise FileNotFoundError(
            "Resolved Astronomy Shop evidence was not found. "
            "Run tools/render_real_compose.py first: "
            f"{evidence_path}"
        )

    baseline = load_architecture_graph(
        baseline_path
    )

    if (
        baseline.metadata.system_id
        != SYSTEM_ID
    ):
        raise ValueError(
            "Astronomy Shop baseline has an unexpected system_id: "
            f"{baseline.metadata.system_id!r}"
        )

    adapter = ComposeAdapter(
        project_root,
        evidence_path.relative_to(
            project_root
        ),
        node_types=(
            ASTRONOMY_NODE_TYPES
        ),
    )

    observations = adapter.collect()

    analysis = analyze_baseline_reconstruction(
        baseline=baseline,
        observations=observations,
        scope=EvidenceScope(
            node_ids=frozenset(
                ASTRONOMY_NODE_TYPES
            )
        ),
        revision="real-non-runtime",
    )

    output_path = (
        project_root
        / "results"
        / "real-baseline"
        / SYSTEM_ID
        / "non-runtime.json"
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    document = analysis_document(
        analysis
    )

    output_path.write_text(
        json.dumps(
            document,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    coverage = analysis.coverage

    print(
        "Astronomy Shop real non-runtime baseline analysis"
    )

    print(
        f"Scoped observations: "
        f"{analysis.scoped.included_count}"
    )

    print(
        f"Excluded observations: "
        f"{analysis.scoped.excluded_count}"
    )

    print(
        f"Canonical nodes: "
        f"{len(analysis.reconstruction.graph.node_ids)}"
    )

    print(
        f"Canonical relations: "
        f"{len(analysis.reconstruction.graph.relation_identities)}"
    )

    print()

    print(
        "Baseline coverage"
    )

    print(
        "  Nodes:     "
        f"{coverage.observed_baseline_node_count}/"
        f"{coverage.baseline_node_count} "
        f"({percentage(coverage.node_coverage)})"
    )

    print(
        "  Relations: "
        f"{coverage.observed_baseline_relation_count}/"
        f"{coverage.baseline_relation_count} "
        f"({percentage(coverage.relation_coverage)})"
    )

    print()

    print(
        f"Unexpected nodes: "
        f"{len(coverage.unexpected_node_ids)}"
    )

    print(
        f"Not-observed nodes: "
        f"{len(coverage.not_observed_node_ids)}"
    )

    print(
        f"Unexpected relations: "
        f"{len(coverage.unexpected_relation_identities)}"
    )

    for relation in sorted(
        coverage.unexpected_relation_identities,
        key=lambda item: (
            item[0],
            item[1].value,
            item[2],
        ),
    ):
        print(
            "  + "
            f"{relation[0]} "
            f"--{relation[1].value}--> "
            f"{relation[2]}"
        )

    print(
        f"Not-observed relations: "
        f"{len(coverage.not_observed_relation_identities)}"
    )

    for relation in sorted(
        coverage.not_observed_relation_identities,
        key=lambda item: (
            item[0],
            item[1].value,
            item[2],
        ),
    ):
        print(
            "  ? "
            f"{relation[0]} "
            f"--{relation[1].value}--> "
            f"{relation[2]}"
        )

    print()

    print(
        f"Result: {output_path}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )