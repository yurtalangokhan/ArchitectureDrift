from archdrift.model import (
    ArchitectureGraph,
    ArchitectureNode,
    ArchitectureRelation,
    GraphMetadata,
    GraphRole,
    NodeType,
    ReconstructionMode,
    RelationType,
)
from archdrift.analysis.coverage import (
    BaselineCoverageMetrics,
    evaluate_baseline_coverage,
)


def test_baseline_coverage_distinguishes_not_observed_from_unexpected() -> None:
    baseline = ArchitectureGraph(
        metadata=GraphMetadata(
            system_id="system",
            role=GraphRole.BASELINE,
        ),
        nodes=(
            ArchitectureNode(
                id="a",
                type=NodeType.SERVICE,
            ),
            ArchitectureNode(
                id="b",
                type=NodeType.SERVICE,
            ),
            ArchitectureNode(
                id="c",
                type=NodeType.SERVICE,
            ),
        ),
        relations=(
            ArchitectureRelation(
                source="a",
                relation=RelationType.CALLS,
                target="b",
            ),
            ArchitectureRelation(
                source="b",
                relation=RelationType.CALLS,
                target="c",
            ),
        ),
    )

    observed = ArchitectureGraph(
        metadata=GraphMetadata(
            system_id="system",
            role=GraphRole.OBSERVED,
            reconstruction_mode=(
                ReconstructionMode.NON_RUNTIME
            ),
        ),
        nodes=(
            ArchitectureNode(
                id="a",
                type=NodeType.SERVICE,
            ),
            ArchitectureNode(
                id="b",
                type=NodeType.SERVICE,
            ),
            ArchitectureNode(
                id="x",
                type=NodeType.SERVICE,
            ),
        ),
        relations=(
            ArchitectureRelation(
                source="a",
                relation=RelationType.CALLS,
                target="b",
            ),
            ArchitectureRelation(
                source="a",
                relation=RelationType.CALLS,
                target="x",
            ),
        ),
    )

    metrics = evaluate_baseline_coverage(
        baseline=baseline,
        observed=observed,
    )

    assert metrics.node_coverage == 2 / 3
    assert metrics.relation_coverage == 1 / 2

    assert metrics.not_observed_node_ids == frozenset(
        {
            "c",
        }
    )

    assert metrics.unexpected_node_ids == frozenset(
        {
            "x",
        }
    )

    assert metrics.not_observed_relation_identities == frozenset(
        {
            (
                "b",
                RelationType.CALLS,
                "c",
            ),
        }
    )

    assert metrics.unexpected_relation_identities == frozenset(
        {
            (
                "a",
                RelationType.CALLS,
                "x",
            ),
        }
    )