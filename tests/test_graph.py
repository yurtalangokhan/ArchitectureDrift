from pathlib import Path

import networkx as nx
import pytest
from pydantic import ValidationError

from archdrift.model.evidence import EvidenceRecord, EvidenceType
from archdrift.model.graph import (
    ArchitectureEdge,
    ArchitectureGraph,
    ArchitectureNode,
    GraphMetadata,
    GraphView,
    NodeType,
    RelationType,
)


def build_graph() -> ArchitectureGraph:
    return ArchitectureGraph(
        metadata=GraphMetadata(
            system_id="test-system",
            variant="baseline",
            revision="abc123",
            view=GraphView.RUNTIME,
        ),
        nodes=[
            ArchitectureNode(
                id="checkout",
                type=NodeType.SERVICE,
            ),
            ArchitectureNode(
                id="payment",
                type=NodeType.SERVICE,
            ),
        ],
        edges=[],
    )


def test_graph_can_be_created() -> None:
    graph = build_graph()

    assert graph.metadata.system_id == "test-system"
    assert len(graph.nodes) == 2
    assert graph.edges == []


def test_add_edge() -> None:
    graph = build_graph()

    graph.add_edge(
        ArchitectureEdge(
            source="checkout",
            target="payment",
            relation=RelationType.CALLS,
            protocol="grpc",
        )
    )

    assert len(graph.edges) == 1

    assert graph.has_edge(
        source="checkout",
        target="payment",
        relation=RelationType.CALLS,
        protocol="grpc",
    )


def test_protocol_is_normalized() -> None:
    edge = ArchitectureEdge(
        source="checkout",
        target="payment",
        relation=RelationType.CALLS,
        protocol=" GRPC ",
    )

    assert edge.protocol == "grpc"


def test_different_protocols_are_distinct_edges() -> None:
    graph = build_graph()

    graph.add_edge(
        ArchitectureEdge(
            source="checkout",
            target="payment",
            relation=RelationType.CALLS,
            protocol="http",
        )
    )

    graph.add_edge(
        ArchitectureEdge(
            source="checkout",
            target="payment",
            relation=RelationType.CALLS,
            protocol="grpc",
        )
    )

    assert len(graph.edges) == 2


def test_duplicate_edges_merge_evidence() -> None:
    graph = build_graph()

    deployment_evidence = EvidenceRecord(
        type=EvidenceType.DEPLOYMENT_CONFIG,
        artifact="compose.yaml",
        locator="PAYMENT_ADDR",
    )

    runtime_evidence = EvidenceRecord(
        type=EvidenceType.RUNTIME_TRACE,
        artifact="trace.json",
        locator="trace-001",
    )

    graph.add_edge(
        ArchitectureEdge(
            source="checkout",
            target="payment",
            relation=RelationType.CALLS,
            protocol="grpc",
            evidence=[deployment_evidence],
        )
    )

    graph.add_edge(
        ArchitectureEdge(
            source="checkout",
            target="payment",
            relation=RelationType.CALLS,
            protocol="grpc",
            evidence=[runtime_evidence],
        )
    )

    assert len(graph.edges) == 1
    assert len(graph.edges[0].evidence) == 2


def test_duplicate_evidence_is_removed() -> None:
    graph = build_graph()

    evidence = EvidenceRecord(
        type=EvidenceType.RUNTIME_TRACE,
        artifact="trace.json",
        locator="trace-001",
    )

    graph.add_edge(
        ArchitectureEdge(
            source="checkout",
            target="payment",
            relation=RelationType.CALLS,
            protocol="grpc",
            evidence=[evidence],
        )
    )

    graph.add_edge(
        ArchitectureEdge(
            source="checkout",
            target="payment",
            relation=RelationType.CALLS,
            protocol="grpc",
            evidence=[evidence],
        )
    )

    assert len(graph.edges) == 1
    assert len(graph.edges[0].evidence) == 1


def test_graph_rejects_edge_with_unknown_source() -> None:
    with pytest.raises(ValidationError):
        ArchitectureGraph(
            metadata=GraphMetadata(
                system_id="test-system",
            ),
            nodes=[
                ArchitectureNode(
                    id="payment",
                    type=NodeType.SERVICE,
                ),
            ],
            edges=[
                ArchitectureEdge(
                    source="unknown",
                    target="payment",
                    relation=RelationType.CALLS,
                )
            ],
        )


def test_graph_rejects_duplicate_node_ids() -> None:
    with pytest.raises(ValidationError):
        ArchitectureGraph(
            metadata=GraphMetadata(
                system_id="test-system",
            ),
            nodes=[
                ArchitectureNode(
                    id="checkout",
                    type=NodeType.SERVICE,
                ),
                ArchitectureNode(
                    id="checkout",
                    type=NodeType.GATEWAY,
                ),
            ],
            edges=[],
        )


def test_remove_edge() -> None:
    graph = build_graph()

    graph.add_edge(
        ArchitectureEdge(
            source="checkout",
            target="payment",
            relation=RelationType.CALLS,
            protocol="grpc",
        )
    )

    removed = graph.remove_edges(
        source="checkout",
        target="payment",
        relation=RelationType.CALLS,
        protocol="grpc",
    )

    assert removed == 1
    assert graph.edges == []


def test_to_networkx_returns_multidigraph() -> None:
    graph = build_graph()

    graph.add_edge(
        ArchitectureEdge(
            source="checkout",
            target="payment",
            relation=RelationType.CALLS,
            protocol="grpc",
        )
    )

    nx_graph = graph.to_networkx()

    assert isinstance(nx_graph, nx.MultiDiGraph)

    assert nx_graph.has_edge(
        "checkout",
        "payment",
        key="CALLS:grpc",
    )


def test_yaml_round_trip(tmp_path: Path) -> None:
    graph = build_graph()

    graph.add_edge(
        ArchitectureEdge(
            source="checkout",
            target="payment",
            relation=RelationType.CALLS,
            protocol="grpc",
        )
    )

    output = tmp_path / "graph.yaml"

    graph.to_yaml(output)

    loaded = ArchitectureGraph.from_yaml(output)

    assert loaded == graph


def test_json_round_trip(tmp_path: Path) -> None:
    graph = build_graph()

    graph.add_edge(
        ArchitectureEdge(
            source="checkout",
            target="payment",
            relation=RelationType.CALLS,
            protocol="grpc",
        )
    )

    output = tmp_path / "graph.json"

    graph.to_json(output)

    loaded = ArchitectureGraph.from_json(output)

    assert loaded == graph