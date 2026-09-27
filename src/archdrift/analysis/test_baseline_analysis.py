from __future__ import annotations

from archdrift.analysis.baseline import (
    analyze_baseline_reconstruction,
)
from archdrift.analysis.scope import (
    EvidenceScope,
)
from archdrift.model import (
    ArchitectureGraph,
    ArchitectureNode,
    ArchitectureRelation,
    EvidenceRecord,
    EvidenceType,
    GraphMetadata,
    GraphRole,
    InteractionType,
    NodeType,
    NormalizedEndpoint,
    NormalizedNodeObservation,
    NormalizedRelationObservation,
    RelationType,
)


def evidence() -> tuple[
    EvidenceRecord,
    ...,
]:
    return (
        EvidenceRecord(
            type=EvidenceType.DEPLOYMENT_CONFIG,
            artifact="compose.resolved.json",
            locator="test",
        ),
    )


def test_real_baseline_analysis_reconstructs_scoped_graph() -> None:
    baseline = ArchitectureGraph(
        metadata=GraphMetadata(
            system_id="system",
            role=GraphRole.BASELINE,
            revision="baseline-01",
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
        ),
        relations=(
            ArchitectureRelation(
                source="a",
                relation=RelationType.CALLS,
                target="b",
            ),
        ),
    )

    observations = (
        NormalizedNodeObservation(
            endpoint=NormalizedEndpoint(
                id="a",
                type=NodeType.SERVICE,
            ),
            evidence=evidence(),
        ),
        NormalizedNodeObservation(
            endpoint=NormalizedEndpoint(
                id="b",
                type=NodeType.SERVICE,
            ),
            evidence=evidence(),
        ),
        NormalizedNodeObservation(
            endpoint=NormalizedEndpoint(
                id="outside",
                type=NodeType.SERVICE,
            ),
            evidence=evidence(),
        ),
        NormalizedRelationObservation(
            source=NormalizedEndpoint(
                id="a",
                type=NodeType.SERVICE,
            ),
            target=NormalizedEndpoint(
                id="b",
                type=NodeType.SERVICE,
            ),
            interaction=InteractionType.SERVICE_CALL,
            protocol="http",
            evidence=evidence(),
        ),
        NormalizedRelationObservation(
            source=NormalizedEndpoint(
                id="a",
                type=NodeType.SERVICE,
            ),
            target=NormalizedEndpoint(
                id="outside",
                type=NodeType.SERVICE,
            ),
            interaction=InteractionType.SERVICE_CALL,
            protocol="http",
            evidence=evidence(),
        ),
    )

    result = analyze_baseline_reconstruction(
        baseline=baseline,
        observations=observations,
        scope=EvidenceScope(
            node_ids=frozenset(
                {
                    "a",
                    "b",
                }
            )
        ),
        revision="real-evidence-01",
    )

    assert result.scoped.included_count == 3
    assert result.scoped.excluded_count == 2

    assert result.reconstruction.graph.node_ids == frozenset(
        {
            "a",
            "b",
        }
    )

    assert (
        result.reconstruction.graph.relation_identities
        == frozenset(
            {
                (
                    "a",
                    RelationType.CALLS,
                    "b",
                )
            }
        )
    )

    assert result.coverage.node_coverage == 1.0
    assert result.coverage.relation_coverage == 1.0

    assert (
        result.coverage.unexpected_node_ids
        == frozenset()
    )

    assert (
        result.coverage.not_observed_node_ids
        == frozenset()
    )

    assert (
        result.coverage.unexpected_relation_identities
        == frozenset()
    )

    assert (
        result.coverage.not_observed_relation_identities
        == frozenset()
    )