import pytest
from pydantic import ValidationError

from archdrift.model import (
    ArchitectureNode,
    ArchitectureRelation,
    CanonicalArchitectureGraph,
    CanonicalArchitectureModel,
    DuplicateNodeError,
    DuplicateRelationError,
    NodeType,
    RelationType,
    UnknownNodeError,
    UnknownRelationError,
)

# =============================================================================
# Test Fixtures / Helpers
# =============================================================================


def create_astronomy_graph() -> CanonicalArchitectureGraph:
    """
    Create a minimal Astronomy Shop graph used by WP-01 tests.
    """

    graph = CanonicalArchitectureGraph(
        system_id="astronomy-shop"
    )

    graph.add_node(
        ArchitectureNode(
            id="checkout",
            type=NodeType.SERVICE,
            name="Checkout Service",
        )
    )

    graph.add_node(
        ArchitectureNode(
            id="recommendation",
            type=NodeType.SERVICE,
            name="Recommendation Service",
        )
    )

    return graph


# =============================================================================
# Enum Tests
# =============================================================================


def test_node_types_match_canonical_vocabulary() -> None:
    assert set(NodeType) == {
        NodeType.SERVICE,
        NodeType.DATASTORE,
        NodeType.BROKER,
        NodeType.GATEWAY,
        NodeType.REGISTRY,
        NodeType.EXTERNAL,
    }


def test_relation_types_match_canonical_vocabulary() -> None:
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


# =============================================================================
# ArchitectureNode Tests
# =============================================================================


def test_architecture_node_can_be_created() -> None:
    node = ArchitectureNode(
        id="checkout",
        type=NodeType.SERVICE,
        name="Checkout Service",
    )

    assert node.id == "checkout"
    assert node.type == NodeType.SERVICE
    assert node.name == "Checkout Service"


def test_architecture_node_identifier_is_trimmed() -> None:
    node = ArchitectureNode(
        id="checkout",
        type=NodeType.SERVICE,
    )

    assert node.id == "checkout"


def test_architecture_node_rejects_blank_identifier() -> None:
    with pytest.raises(ValidationError):
        ArchitectureNode(
            id="   ",
            type=NodeType.SERVICE,
        )


def test_architecture_node_rejects_identifier_with_whitespace() -> None:
    with pytest.raises(ValidationError):
        ArchitectureNode(
            id="checkout service",
            type=NodeType.SERVICE,
        )


def test_architecture_node_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ArchitectureNode(
            id="checkout",
            type=NodeType.SERVICE,
            unknown_field="invalid",
        )


# =============================================================================
# ArchitectureRelation Tests
# =============================================================================


def test_relation_can_be_created() -> None:
    relation = ArchitectureRelation(
        source="checkout",
        target="recommendation",
        type=RelationType.CALLS,
    )

    assert relation.source == "checkout"
    assert relation.target == "recommendation"
    assert relation.type == RelationType.CALLS


def test_relation_signature_is_canonical_triplet() -> None:
    relation = ArchitectureRelation(
        source="checkout",
        target="recommendation",
        type=RelationType.CALLS,
    )

    assert relation.signature == (
        "checkout",
        RelationType.CALLS,
        "recommendation",
    )


# =============================================================================
# CanonicalArchitectureModel Tests
# =============================================================================


def test_canonical_model_accepts_valid_graph() -> None:
    model = CanonicalArchitectureModel(
        system_id="astronomy-shop",
        nodes=[
            ArchitectureNode(
                id="checkout",
                type=NodeType.SERVICE,
            ),
            ArchitectureNode(
                id="recommendation",
                type=NodeType.SERVICE,
            ),
        ],
        relations=[
            ArchitectureRelation(
                source="checkout",
                target="recommendation",
                type=RelationType.CALLS,
            )
        ],
    )

    assert model.system_id == "astronomy-shop"
    assert len(model.nodes) == 2
    assert len(model.relations) == 1


def test_canonical_model_rejects_duplicate_nodes() -> None:
    with pytest.raises(
        ValidationError,
        match="duplicate node identifiers",
    ):
        CanonicalArchitectureModel(
            system_id="astronomy-shop",
            nodes=[
                ArchitectureNode(
                    id="checkout",
                    type=NodeType.SERVICE,
                ),
                ArchitectureNode(
                    id="checkout",
                    type=NodeType.SERVICE,
                ),
            ],
        )


def test_canonical_model_rejects_unknown_relation_source() -> None:
    with pytest.raises(
        ValidationError,
        match="unknown source node",
    ):
        CanonicalArchitectureModel(
            system_id="astronomy-shop",
            nodes=[
                ArchitectureNode(
                    id="recommendation",
                    type=NodeType.SERVICE,
                ),
            ],
            relations=[
                ArchitectureRelation(
                    source="checkout",
                    target="recommendation",
                    type=RelationType.CALLS,
                ),
            ],
        )


def test_canonical_model_rejects_unknown_relation_target() -> None:
    with pytest.raises(
        ValidationError,
        match="unknown target node",
    ):
        CanonicalArchitectureModel(
            system_id="astronomy-shop",
            nodes=[
                ArchitectureNode(
                    id="checkout",
                    type=NodeType.SERVICE,
                ),
            ],
            relations=[
                ArchitectureRelation(
                    source="checkout",
                    target="recommendation",
                    type=RelationType.CALLS,
                ),
            ],
        )


def test_canonical_model_rejects_duplicate_relations() -> None:
    checkout = ArchitectureNode(
        id="checkout",
        type=NodeType.SERVICE,
    )

    recommendation = ArchitectureNode(
        id="recommendation",
        type=NodeType.SERVICE,
    )

    relation = ArchitectureRelation(
        source="checkout",
        target="recommendation",
        type=RelationType.CALLS,
    )

    with pytest.raises(
        ValidationError,
        match="duplicate relation",
    ):
        CanonicalArchitectureModel(
            system_id="astronomy-shop",
            nodes=[
                checkout,
                recommendation,
            ],
            relations=[
                relation,
                relation,
            ],
        )


# =============================================================================
# CanonicalArchitectureGraph Node Tests
# =============================================================================


def test_graph_adds_nodes() -> None:
    graph = create_astronomy_graph()

    assert graph.node_count == 2
    assert graph.has_node("checkout")
    assert graph.has_node("recommendation")


def test_graph_can_get_node() -> None:
    graph = create_astronomy_graph()

    node = graph.get_node(
        "checkout"
    )

    assert node.id == "checkout"
    assert node.type == NodeType.SERVICE


def test_graph_rejects_duplicate_node() -> None:
    graph = create_astronomy_graph()

    with pytest.raises(DuplicateNodeError):
        graph.add_node(
            ArchitectureNode(
                id="checkout",
                type=NodeType.SERVICE,
            )
        )


def test_graph_rejects_unknown_node_lookup() -> None:
    graph = create_astronomy_graph()

    with pytest.raises(UnknownNodeError):
        graph.get_node(
            "unknown-service"
        )


def test_graph_can_remove_node() -> None:
    graph = create_astronomy_graph()

    graph.remove_node(
        "recommendation"
    )

    assert graph.node_count == 1
    assert not graph.has_node(
        "recommendation"
    )


# =============================================================================
# CanonicalArchitectureGraph Relation Tests
# =============================================================================


def test_graph_adds_relation() -> None:
    graph = create_astronomy_graph()

    relation = ArchitectureRelation(
        source="checkout",
        target="recommendation",
        type=RelationType.CALLS,
    )

    graph.add_relation(relation)

    assert graph.relation_count == 1

    assert graph.has_relation(
        source="checkout",
        relation_type=RelationType.CALLS,
        target="recommendation",
    )


def test_graph_rejects_relation_with_unknown_source() -> None:
    graph = create_astronomy_graph()

    with pytest.raises(UnknownNodeError):
        graph.add_relation(
            ArchitectureRelation(
                source="unknown-service",
                target="recommendation",
                type=RelationType.CALLS,
            )
        )


def test_graph_rejects_relation_with_unknown_target() -> None:
    graph = create_astronomy_graph()

    with pytest.raises(UnknownNodeError):
        graph.add_relation(
            ArchitectureRelation(
                source="checkout",
                target="unknown-service",
                type=RelationType.CALLS,
            )
        )


def test_graph_rejects_duplicate_relation() -> None:
    graph = create_astronomy_graph()

    relation = ArchitectureRelation(
        source="checkout",
        target="recommendation",
        type=RelationType.CALLS,
    )

    graph.add_relation(relation)

    with pytest.raises(
        DuplicateRelationError
    ):
        graph.add_relation(relation)


def test_graph_supports_multiple_relation_types_between_same_nodes() -> None:
    graph = create_astronomy_graph()

    graph.add_relation(
        ArchitectureRelation(
            source="checkout",
            target="recommendation",
            type=RelationType.CALLS,
        )
    )

    graph.add_relation(
        ArchitectureRelation(
            source="checkout",
            target="recommendation",
            type=RelationType.EXPOSES_TO,
        )
    )

    assert graph.relation_count == 2


def test_graph_can_get_relation() -> None:
    graph = create_astronomy_graph()

    graph.add_relation(
        ArchitectureRelation(
            source="checkout",
            target="recommendation",
            type=RelationType.CALLS,
        )
    )

    relation = graph.get_relation(
        source="checkout",
        relation_type=RelationType.CALLS,
        target="recommendation",
    )

    assert relation.signature == (
        "checkout",
        RelationType.CALLS,
        "recommendation",
    )


def test_graph_can_remove_relation() -> None:
    graph = create_astronomy_graph()

    graph.add_relation(
        ArchitectureRelation(
            source="checkout",
            target="recommendation",
            type=RelationType.CALLS,
        )
    )

    graph.remove_relation(
        source="checkout",
        relation_type=RelationType.CALLS,
        target="recommendation",
    )

    assert graph.relation_count == 0


def test_graph_rejects_unknown_relation_removal() -> None:
    graph = create_astronomy_graph()

    with pytest.raises(
        UnknownRelationError
    ):
        graph.remove_relation(
            source="checkout",
            relation_type=RelationType.CALLS,
            target="recommendation",
        )


# =============================================================================
# Determinism Tests
# =============================================================================


def test_nodes_are_returned_in_deterministic_order() -> None:
    graph = CanonicalArchitectureGraph(
        system_id="test-system"
    )

    graph.add_node(
        ArchitectureNode(
            id="z-service",
            type=NodeType.SERVICE,
        )
    )

    graph.add_node(
        ArchitectureNode(
            id="a-service",
            type=NodeType.SERVICE,
        )
    )

    node_ids = [
        node.id
        for node in graph.nodes()
    ]

    assert node_ids == [
        "a-service",
        "z-service",
    ]


def test_relations_are_returned_in_deterministic_order() -> None:
    graph = CanonicalArchitectureGraph(
        system_id="test-system"
    )

    for node_id in [
        "service-a",
        "service-b",
        "service-c",
    ]:
        graph.add_node(
            ArchitectureNode(
                id=node_id,
                type=NodeType.SERVICE,
            )
        )

    graph.add_relation(
        ArchitectureRelation(
            source="service-b",
            target="service-c",
            type=RelationType.CALLS,
        )
    )

    graph.add_relation(
        ArchitectureRelation(
            source="service-a",
            target="service-b",
            type=RelationType.CALLS,
        )
    )

    signatures = [
        relation.signature
        for relation in graph.relations()
    ]

    assert signatures == [
        (
            "service-a",
            RelationType.CALLS,
            "service-b",
        ),
        (
            "service-b",
            RelationType.CALLS,
            "service-c",
        ),
    ]


# =============================================================================
# Serialization / Reconstruction Tests
# =============================================================================


def test_graph_round_trip_preserves_architecture() -> None:
    graph = create_astronomy_graph()

    graph.add_relation(
        ArchitectureRelation(
            source="checkout",
            target="recommendation",
            type=RelationType.CALLS,
        )
    )

    model = graph.to_model()

    restored = CanonicalArchitectureGraph.from_model(
        model
    )

    assert restored.system_id == graph.system_id
    assert restored.node_count == graph.node_count
    assert restored.relation_count == graph.relation_count

    assert restored.has_relation(
        source="checkout",
        relation_type=RelationType.CALLS,
        target="recommendation",
    )


# =============================================================================
# Baseline / Mutant Isolation Tests
# =============================================================================


def test_graph_copy_is_independent_from_baseline() -> None:
    baseline = create_astronomy_graph()

    mutant = baseline.copy()

    mutant.add_relation(
        ArchitectureRelation(
            source="checkout",
            target="recommendation",
            type=RelationType.CALLS,
        )
    )

    assert baseline.relation_count == 0
    assert mutant.relation_count == 1


def test_networkx_projection_cannot_mutate_canonical_graph() -> None:
    graph = create_astronomy_graph()

    networkx_graph = graph.as_networkx()

    networkx_graph.add_node(
        "rogue-service"
    )

    assert "rogue-service" in networkx_graph

    assert not graph.has_node(
        "rogue-service"
    )