from __future__ import annotations

import json
from pathlib import Path

import yaml

from archdrift.adapters.compose_bindings import (
    ComposeEndpointBindingAdapter,
)
from archdrift.adapters.semgrep import (
    SemgrepResultAdapter,
)
from archdrift.analysis.baseline import (
    analyze_baseline_reconstruction,
)
from archdrift.analysis.scope import (
    EvidenceScope,
)
from archdrift.analysis.static_observation import (
    static_interactions_to_observations,
)
from archdrift.analysis.static_resolution import (
    StaticTargetResolver,
)
from archdrift.model import (
    ArchitectureGraph,
    NodeType,
    SourcePathRule,
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


def load_baseline(
    path: Path,
) -> ArchitectureGraph:
    document = yaml.safe_load(
        path.read_text(
            encoding="utf-8",
        )
    )

    return ArchitectureGraph.model_validate(document)


def percentage(
    value: float | None,
) -> str:
    if value is None:
        return "N/A"

    return f"{value * 100:.2f}%"


def relation_document(
    relation: tuple,
) -> list[str]:
    source, relation_type, target = relation

    return [
        source,
        relation_type.value,
        target,
    ]


def main() -> int:
    root = Path.cwd().resolve()

    semgrep_file = (
        root
        / "evidence"
        / "real"
        / "non-runtime"
        / SYSTEM_ID
        / "source-static"
        / "semgrep.json"
    )

    compose_file = (
        root / "evidence" / "real" / "non-runtime" / SYSTEM_ID / "compose.resolved.json"
    )

    baseline_file = root / "graphs" / "baseline" / SYSTEM_ID / "baseline.yaml"

    findings = SemgrepResultAdapter().collect(semgrep_file)

    bindings = ComposeEndpointBindingAdapter().collect(
        result_file=compose_file,
        node_types=(ASTRONOMY_NODE_TYPES),
    )

    resolution = StaticTargetResolver().resolve(
        findings=findings,
        source_rules=(
            SourcePathRule(
                path_prefix="src/frontend",
                service_id="frontend",
            ),
            SourcePathRule(
                path_prefix="src/checkout",
                service_id="checkout",
            ),
            SourcePathRule(
                path_prefix="src/recommendation",
                service_id="recommendation",
            ),
            SourcePathRule(
                path_prefix="src/shipping",
                service_id="shipping",
            ),
        ),
        bindings=bindings,
    )

    observations = static_interactions_to_observations(resolution.resolved)

    baseline = load_baseline(baseline_file)

    analysis = analyze_baseline_reconstruction(
        baseline=baseline,
        observations=observations,
        scope=EvidenceScope(node_ids=frozenset(ASTRONOMY_NODE_TYPES)),
        revision=("real-source-static"),
    )

    graph = analysis.reconstruction.graph

    coverage = analysis.coverage

    output_file = root / "results" / "real-baseline" / SYSTEM_ID / "source-static.json"

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    document = {
        "schema_version": "1.0",
        "system_id": SYSTEM_ID,
        "evidence_source": ("SOURCE_STATIC"),
        "findings": len(findings),
        "resolved_findings": (resolution.resolved_count),
        "unresolved_findings": (resolution.unresolved_count),
        "reconstruction": {
            "node_count": len(graph.node_ids),
            "relation_count": len(graph.relation_identities),
            "nodes": sorted(graph.node_ids),
            "relations": [
                relation_document(relation)
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
            "baseline_node_count": (coverage.baseline_node_count),
            "observed_baseline_node_count": (coverage.observed_baseline_node_count),
            "node_coverage": (coverage.node_coverage),
            "baseline_relation_count": (coverage.baseline_relation_count),
            "observed_baseline_relation_count": (
                coverage.observed_baseline_relation_count
            ),
            "relation_coverage": (coverage.relation_coverage),
            "unexpected_nodes": sorted(coverage.unexpected_node_ids),
            "not_observed_nodes": sorted(coverage.not_observed_node_ids),
            "unexpected_relations": [
                relation_document(relation)
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
                relation_document(relation)
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

    output_file.write_text(
        json.dumps(
            document,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print("Astronomy Shop source-static baseline analysis")

    print(f"Findings:   {len(findings)}")

    print(f"Resolved:   {resolution.resolved_count}")

    print(f"Unresolved: {resolution.unresolved_count}")

    print()

    print(f"Canonical nodes:     {len(graph.node_ids)}")

    print(f"Canonical relations: {len(graph.relation_identities)}")

    print()

    print("Baseline coverage")

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

    print(f"Unexpected relations: " f"{len(coverage.unexpected_relation_identities)}")

    print(
        f"Not-observed relations: " f"{len(coverage.not_observed_relation_identities)}"
    )

    print()

    print(f"Result: {output_file}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
