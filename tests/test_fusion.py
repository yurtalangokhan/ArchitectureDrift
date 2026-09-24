from archdrift.analysis import (
    CandidateConflictError,
    CanonicalNodeCandidate,
    CanonicalRelationCandidate,
    build_evidence_graph_views,
    reconstruct_observed_graph,
)
from archdrift.model import (
    ArchitectureNode,
    ArchitectureRelation,
    EvidenceChannel,
    EvidenceRecord,
    EvidenceType,
    NodeType,
    ReconstructionMode,
    RelationType,
)

import pytest


def non_runtime_evidence(
    artifact: str = "compose.yaml",
) -> EvidenceRecord:
    return EvidenceRecord(
        type=EvidenceType.DEPLOYMENT_CONFIG,
        artifact=artifact,
    )


def runtime_evidence(
    artifact: str = "traces.json",
) -> EvidenceRecord:
    return EvidenceRecord(
        type=EvidenceType.RUNTIME_TRACE,
        artifact=artifact,
    )


def non_runtime_relation_candidate() -> CanonicalRelationCandidate:
    return CanonicalRelationCandidate(
        source_node=ArchitectureNode(
            id="checkout",
            type=NodeType.SERVICE,
        ),
        target_node=ArchitectureNode(
            id="recommendation",
            type=NodeType.SERVICE,
        ),
        relation=ArchitectureRelation(
            source="checkout",
            relation=RelationType.CALLS,
            target="recommendation",
        ),
        protocol="http",
        evidence=(
            non_runtime_evidence(),
        ),
    )


def runtime_relation_candidate() -> CanonicalRelationCandidate:
    return CanonicalRelationCandidate(
        source_node=ArchitectureNode(
            id="checkout",
            type=NodeType.SERVICE,
        ),
        target_node=ArchitectureNode(
            id="recommendation",
            type=NodeType.SERVICE,
        ),
        relation=ArchitectureRelation(
            source="checkout",
            relation=RelationType.CALLS,
            target="recommendation",
        ),
        protocol="grpc",
        evidence=(
            runtime_evidence(),
        ),
    )


def test_non_runtime_view_excludes_runtime_candidate() -> None:
    result = reconstruct_observed_graph(
        system_id="astronomy-shop",
        candidates=(
            non_runtime_relation_candidate(),
            runtime_relation_candidate(),
        ),
        mode=ReconstructionMode.NON_RUNTIME,
        variant="AS-M01",
    )

    assert result.graph.relation_identities == frozenset(
        {
            (
                "checkout",
                RelationType.CALLS,
                "recommendation",
            )
        }
    )

    support = result.relation_support[0]

    assert support.channels == (
        EvidenceChannel.NON_RUNTIME,
    )

    assert support.protocols == (
        "http",
    )


def test_runtime_view_excludes_non_runtime_candidate() -> None:
    result = reconstruct_observed_graph(
        system_id="astronomy-shop",
        candidates=(
            non_runtime_relation_candidate(),
            runtime_relation_candidate(),
        ),
        mode=ReconstructionMode.RUNTIME,
        variant="AS-M01",
    )

    assert len(
        result.graph.relations
    ) == 1

    support = result.relation_support[0]

    assert support.channels == (
        EvidenceChannel.RUNTIME,
    )

    assert support.protocols == (
        "grpc",
    )


def test_fused_view_merges_same_canonical_relation() -> None:
    result = reconstruct_observed_graph(
        system_id="astronomy-shop",
        candidates=(
            non_runtime_relation_candidate(),
            runtime_relation_candidate(),
        ),
        mode=ReconstructionMode.FUSED,
        variant="AS-M01",
    )

    assert len(
        result.graph.relations
    ) == 1

    assert result.graph.relation_identities == frozenset(
        {
            (
                "checkout",
                RelationType.CALLS,
                "recommendation",
            )
        }
    )

    support = result.relation_support[0]

    assert support.channels == (
        EvidenceChannel.NON_RUNTIME,
        EvidenceChannel.RUNTIME,
    )

    assert support.protocols == (
        "grpc",
        "http",
    )

    assert len(
        support.evidence
    ) == 2

    assert support.is_cross_channel is True


def test_relation_candidate_implicitly_reconstructs_endpoints() -> None:
    result = reconstruct_observed_graph(
        system_id="astronomy-shop",
        candidates=(
            runtime_relation_candidate(),
        ),
        mode=ReconstructionMode.RUNTIME,
    )

    assert result.graph.node_ids == frozenset(
        {
            "checkout",
            "recommendation",
        }
    )


def test_explicit_node_and_relation_evidence_are_merged() -> None:
    node_candidate = CanonicalNodeCandidate(
        node=ArchitectureNode(
            id="checkout",
            type=NodeType.SERVICE,
        ),
        evidence=(
            non_runtime_evidence(
                "src/checkout/Dockerfile"
            ),
        ),
    )

    result = reconstruct_observed_graph(
        system_id="astronomy-shop",
        candidates=(
            node_candidate,
            non_runtime_relation_candidate(),
        ),
        mode=ReconstructionMode.NON_RUNTIME,
    )

    support = result.get_node_support(
        "checkout"
    )

    assert support is not None

    assert len(
        support.evidence
    ) == 2


def test_conflicting_node_types_are_rejected() -> None:
    service_candidate = CanonicalNodeCandidate(
        node=ArchitectureNode(
            id="shared-component",
            type=NodeType.SERVICE,
        ),
        evidence=(
            non_runtime_evidence(),
        ),
    )

    gateway_candidate = CanonicalNodeCandidate(
        node=ArchitectureNode(
            id="shared-component",
            type=NodeType.GATEWAY,
        ),
        evidence=(
            runtime_evidence(),
        ),
    )

    with pytest.raises(
        CandidateConflictError,
        match="Conflicting canonical node types",
    ):
        reconstruct_observed_graph(
            system_id="test-system",
            candidates=(
                service_candidate,
                gateway_candidate,
            ),
            mode=ReconstructionMode.FUSED,
        )


def test_empty_candidate_set_produces_empty_observed_graph() -> None:
    result = reconstruct_observed_graph(
        system_id="astronomy-shop",
        candidates=(),
        mode=ReconstructionMode.RUNTIME,
        variant="AS-M01",
    )

    assert result.graph.nodes == ()
    assert result.graph.relations == ()

    assert (
        result.graph.metadata.reconstruction_mode
        is ReconstructionMode.RUNTIME
    )

    assert result.graph.metadata.variant == "AS-M01"


def test_canonical_graph_contains_no_evidence_or_protocol() -> None:
    result = reconstruct_observed_graph(
        system_id="astronomy-shop",
        candidates=(
            non_runtime_relation_candidate(),
            runtime_relation_candidate(),
        ),
        mode=ReconstructionMode.FUSED,
    )

    relation_dump = (
        result.graph.relations[0].model_dump()
    )

    assert "evidence" not in relation_dump
    assert "protocol" not in relation_dump


def test_build_evidence_graph_views_produces_three_modes() -> None:
    views = build_evidence_graph_views(
        system_id="astronomy-shop",
        candidates=(
            non_runtime_relation_candidate(),
            runtime_relation_candidate(),
        ),
        variant="AS-M01",
    )

    assert (
        views.non_runtime.graph.metadata.reconstruction_mode
        is ReconstructionMode.NON_RUNTIME
    )

    assert (
        views.runtime.graph.metadata.reconstruction_mode
        is ReconstructionMode.RUNTIME
    )

    assert (
        views.fused.graph.metadata.reconstruction_mode
        is ReconstructionMode.FUSED
    )


def test_fused_graph_is_structural_union_of_channel_graphs() -> None:
    non_runtime_only = CanonicalNodeCandidate(
        node=ArchitectureNode(
            id="gateway",
            type=NodeType.GATEWAY,
        ),
        evidence=(
            non_runtime_evidence(),
        ),
    )

    runtime_only = CanonicalNodeCandidate(
        node=ArchitectureNode(
            id="external",
            type=NodeType.EXTERNAL,
        ),
        evidence=(
            runtime_evidence(),
        ),
    )

    views = build_evidence_graph_views(
        system_id="astronomy-shop",
        candidates=(
            non_runtime_only,
            runtime_only,
        ),
    )

    assert (
        views.non_runtime.graph.node_ids
        == frozenset(
            {
                "gateway",
            }
        )
    )

    assert (
        views.runtime.graph.node_ids
        == frozenset(
            {
                "external",
            }
        )
    )

    assert (
        views.fused.graph.node_ids
        == frozenset(
            {
                "gateway",
                "external",
            }
        )
    )


def test_reconstruction_result_json_round_trip() -> None:
    result = reconstruct_observed_graph(
        system_id="astronomy-shop",
        candidates=(
            non_runtime_relation_candidate(),
            runtime_relation_candidate(),
        ),
        mode=ReconstructionMode.FUSED,
        variant="AS-M01",
    )

    serialized = result.model_dump_json()

    restored = type(
        result
    ).model_validate_json(
        serialized
    )

    assert restored == result