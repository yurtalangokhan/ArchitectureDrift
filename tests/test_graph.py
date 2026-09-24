import networkx as nx
import pytest
from pydantic import ValidationError

from archdrift.model import (
    ArchitectureGraph,
    ArchitectureNode,
    ArchitectureRelation,
    DuplicateNodeError,
    DuplicateRelationError,
    GraphMetadata,
    GraphRole,
    NodeType,
    ReconstructionMode,
    RelationType,
    UnknownNodeError,
    UnknownRelationError,
)


def build_graph() -> ArchitectureGraph:
    return ArchitectureGraph(
        metadata=GraphMetadata(
            system_id="test-system",
            role=GraphRole.BASELINE,
            revision="abc123",
        ),
        nodes=(
            ArchitectureNode(
                id="checkout",
                type=NodeType.SERVICE,
            ),
            ArchitectureNode(
                id="payment",
                type=NodeType.SERVICE,
            ),
        ),
    )


def test_canonical_node_vocabulary() -> None:
    assert set(NodeType) == {
        NodeType.SERVICE,
        NodeType.DATASTORE,
        NodeType.BROKER,
        NodeType.GATEWAY,
        NodeType.REGISTRY,
        NodeType.EXTERNAL,
    }


def test_canonical_relation_vocabulary() -> None:
    assert set(RelationType) == {
        RelationType.CALLS,
        RelationType.READS_FROM,
        RelationType.WRITES_TO,
        RelationType.PUBLISHES_TO,
        RelationType.SUBSCRIBES_TO,
        RelationType.ROUTES_TO,
        RelationType.DISCOVERS_VIA,
        RelationType.EXPOSES_TO,
    }


def test_graph_can_be_created() -> None:
    graph = build_graph()

    assert graph.metadata.system_id == "test-system"
    assert graph.metadata.role is GraphRole.BASELINE
    assert len(graph.nodes) == 2
    assert graph.relations == ()


def test_relation_identity_is_canonical_triplet() -> None:
    relation = ArchitectureRelation(
        source="checkout",
        relation=RelationType.CALLS,
        target="payment",
    )

    assert relation.identity == (
        "checkout",
        RelationType.CALLS,
        "payment",
    )


def test_nodes_are_sorted_deterministically() -> None:
    graph = ArchitectureGraph(
        metadata=GraphMetadata(
            system_id="test-system",
            role=GraphRole.BASELINE,
        ),
        nodes=(
            ArchitectureNode(
                id="payment",
                type=NodeType.SERVICE,
            ),
            ArchitectureNode(
                id="checkout",
                type=NodeType.SERVICE,
            ),
        ),
    )

    assert [
        node.id
        for node in graph.nodes
    ] == [
        "checkout",
        "payment",
    ]


def test_graph_rejects_duplicate_node_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="duplicate node identifiers",
    ):
        ArchitectureGraph(
            metadata=GraphMetadata(
                system_id="test-system",
                role=GraphRole.BASELINE,
            ),
            nodes=(
                ArchitectureNode(
                    id="checkout",
                    type=NodeType.SERVICE,
                ),
                ArchitectureNode(
                    id="checkout",
                    type=NodeType.GATEWAY,
                ),
            ),
        )


def test_graph_rejects_unknown_relation_source() -> None:
    with pytest.raises(
        ValidationError,
        match="unknown source",
    ):
        ArchitectureGraph(
            metadata=GraphMetadata(
                system_id="test-system",
                role=GraphRole.BASELINE,
            ),
            nodes=(
                ArchitectureNode(
                    id="payment",
                    type=NodeType.SERVICE,
                ),
            ),
            relations=(
                ArchitectureRelation(
                    source="unknown",
                    relation=RelationType.CALLS,
                    target="payment",
                ),
            ),
        )


def test_graph_rejects_unknown_relation_target() -> None:
    with pytest.raises(
        ValidationError,
        match="unknown target",
    ):
        ArchitectureGraph(
            metadata=GraphMetadata(
                system_id="test-system",
                role=GraphRole.BASELINE,
            ),
            nodes=(
                ArchitectureNode(
                    id="checkout",
                    type=NodeType.SERVICE,
                ),
            ),
            relations=(
                ArchitectureRelation(
                    source="checkout",
                    relation=RelationType.CALLS,
                    target="unknown",
                ),
            ),
        )


def test_with_relation_returns_new_graph() -> None:
    baseline = build_graph()

    mutant = baseline.with_relation(
        ArchitectureRelation(
            source="checkout",
            relation=RelationType.CALLS,
            target="payment",
        )
    )

    assert baseline.relations == ()

    assert mutant.has_relation(
        source="checkout",
        relation=RelationType.CALLS,
        target="payment",
    )


def test_duplicate_relation_is_rejected() -> None:
    graph = build_graph().with_relation(
        ArchitectureRelation(
            source="checkout",
            relation=RelationType.CALLS,
            target="payment",
        )
    )

    with pytest.raises(DuplicateRelationError):
        graph.with_relation(
            ArchitectureRelation(
                source="checkout",
                relation=RelationType.CALLS,
                target="payment",
            )
        )


def test_relation_can_be_removed_without_mutating_original() -> None:
    original = build_graph().with_relation(
        ArchitectureRelation(
            source="checkout",
            relation=RelationType.CALLS,
            target="payment",
        )
    )

    updated = original.without_relation(
        source="checkout",
        relation=RelationType.CALLS,
        target="payment",
    )

    assert len(original.relations) == 1
    assert updated.relations == ()


def test_unknown_relation_removal_is_rejected() -> None:
    graph = build_graph()

    with pytest.raises(UnknownRelationError):
        graph.without_relation(
            source="checkout",
            relation=RelationType.CALLS,
            target="payment",
        )


def test_node_can_be_added_without_mutating_original() -> None:
    graph = build_graph()

    updated = graph.with_node(
        ArchitectureNode(
            id="recommendation",
            type=NodeType.SERVICE,
        )
    )

    assert graph.get_node("recommendation") is None
    assert updated.get_node("recommendation") is not None


def test_duplicate_node_addition_is_rejected() -> None:
    graph = build_graph()

    with pytest.raises(DuplicateNodeError):
        graph.with_node(
            ArchitectureNode(
                id="checkout",
                type=NodeType.SERVICE,
            )
        )


def test_unknown_node_requirement_is_rejected() -> None:
    graph = build_graph()

    with pytest.raises(UnknownNodeError):
        graph.require_node("recommendation")


def test_removing_node_removes_incident_relations() -> None:
    graph = build_graph().with_relation(
        ArchitectureRelation(
            source="checkout",
            relation=RelationType.CALLS,
            target="payment",
        )
    )

    updated = graph.without_node("payment")

    assert updated.get_node("payment") is None
    assert updated.relations == ()


def test_multiple_relation_types_between_nodes_are_supported() -> None:
    graph = build_graph()

    graph = graph.with_relation(
        ArchitectureRelation(
            source="checkout",
            relation=RelationType.CALLS,
            target="payment",
        )
    )

    graph = graph.with_relation(
        ArchitectureRelation(
            source="checkout",
            relation=RelationType.EXPOSES_TO,
            target="payment",
        )
    )

    assert len(graph.relations) == 2


def test_networkx_projection_is_multidigraph() -> None:
    graph = build_graph().with_relation(
        ArchitectureRelation(
            source="checkout",
            relation=RelationType.CALLS,
            target="payment",
        )
    )

    nx_graph = graph.to_networkx()

    assert isinstance(
        nx_graph,
        nx.MultiDiGraph,
    )

    assert nx_graph.has_edge(
        "checkout",
        "payment",
        key="CALLS",
    )


def test_find_relations_filters_by_source() -> None:
    graph = build_graph().with_relation(
        ArchitectureRelation(
            source="checkout",
            relation=RelationType.CALLS,
            target="payment",
        )
    )

    result = graph.find_relations(
        source="checkout"
    )

    assert len(result) == 1

    assert result[0].identity == (
        "checkout",
        RelationType.CALLS,
        "payment",
    )

def test_mutant_graph_requires_variant() -> None:
    with pytest.raises(
        ValidationError,
        match="requires a variant",
    ):
        GraphMetadata(
            system_id="astronomy-shop",
            role=GraphRole.MUTANT,
        )


def test_mutant_graph_accepts_mutation_variant() -> None:
    metadata = GraphMetadata(
        system_id="astronomy-shop",
        role=GraphRole.MUTANT,
        variant="AS-M01",
    )

    assert metadata.variant == "AS-M01"


def test_baseline_rejects_variant() -> None:
    with pytest.raises(
        ValidationError,
        match="must not define a variant",
    ):
        GraphMetadata(
            system_id="astronomy-shop",
            role=GraphRole.BASELINE,
            variant="AS-M01",
        )


def test_baseline_rejects_reconstruction_mode() -> None:
    with pytest.raises(
        ValidationError,
        match="must not define a reconstruction_mode",
    ):
        GraphMetadata(
            system_id="astronomy-shop",
            role=GraphRole.BASELINE,
            reconstruction_mode=ReconstructionMode.RUNTIME,
        )


def test_observed_graph_requires_reconstruction_mode() -> None:
    with pytest.raises(
        ValidationError,
        match="requires a reconstruction_mode",
    ):
        GraphMetadata(
            system_id="astronomy-shop",
            role=GraphRole.OBSERVED,
        )


def test_observed_non_runtime_graph_metadata() -> None:
    metadata = GraphMetadata(
        system_id="astronomy-shop",
        role=GraphRole.OBSERVED,
        reconstruction_mode=ReconstructionMode.NON_RUNTIME,
    )

    assert (
        metadata.reconstruction_mode
        is ReconstructionMode.NON_RUNTIME
    )


def test_observed_runtime_graph_metadata() -> None:
    metadata = GraphMetadata(
        system_id="astronomy-shop",
        role=GraphRole.OBSERVED,
        reconstruction_mode=ReconstructionMode.RUNTIME,
    )

    assert (
        metadata.reconstruction_mode
        is ReconstructionMode.RUNTIME
    )


def test_observed_fused_graph_metadata() -> None:
    metadata = GraphMetadata(
        system_id="astronomy-shop",
        role=GraphRole.OBSERVED,
        reconstruction_mode=ReconstructionMode.FUSED,
    )

    assert (
        metadata.reconstruction_mode
        is ReconstructionMode.FUSED
    )


def test_observed_mutant_graph_can_reference_variant() -> None:
    metadata = GraphMetadata(
        system_id="astronomy-shop",
        role=GraphRole.OBSERVED,
        variant="AS-M01",
        reconstruction_mode=ReconstructionMode.FUSED,
    )

    assert metadata.variant == "AS-M01"


def test_node_ids_are_exposed_as_frozen_set() -> None:
    graph = build_graph()

    assert graph.node_ids == frozenset(
        {
            "checkout",
            "payment",
        }
    )


def test_relation_identities_are_exposed_as_frozen_set() -> None:
    graph = build_graph().with_relation(
        ArchitectureRelation(
            source="checkout",
            relation=RelationType.CALLS,
            target="payment",
        )
    )

    assert graph.relation_identities == frozenset(
        {
            (
                "checkout",
                RelationType.CALLS,
                "payment",
            )
        }
    )


def test_graph_json_round_trip_preserves_model() -> None:
    graph = build_graph().with_relation(
        ArchitectureRelation(
            source="checkout",
            relation=RelationType.CALLS,
            target="payment",
        )
    )

    serialized = graph.model_dump_json()

    restored = ArchitectureGraph.model_validate_json(
        serialized
    )

    assert restored == graph


def test_networkx_mutation_does_not_change_canonical_graph() -> None:
    graph = build_graph()

    projected = graph.to_networkx()

    projected.add_node(
        "rogue-service",
        type="SERVICE",
    )

    assert "rogue-service" in projected
    assert "rogue-service" not in graph.node_ids