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