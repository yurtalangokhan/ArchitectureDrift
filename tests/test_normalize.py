import pytest
from pydantic import ValidationError

from archdrift.analysis import (
    INTERACTION_TO_RELATION,
    CanonicalNodeCandidate,
    CanonicalRelationCandidate,
    canonicalize_observation,
    canonicalize_relation_observation,
)
from archdrift.model import (
    EvidenceChannel,
    EvidenceRecord,
    EvidenceType,
    InteractionType,
    NodeType,
    NormalizedEndpoint,
    NormalizedNodeObservation,
    NormalizedRelationObservation,
    RelationType,
)

# =============================================================================
# Helpers
# =============================================================================


def source_evidence(
    artifact: str = "src/checkout/client.py",
) -> EvidenceRecord:
    return EvidenceRecord(
        type=EvidenceType.SOURCE_CODE,
        artifact=artifact,
    )


def repository_evidence(
    artifact: str = "docker-compose.yml",
) -> EvidenceRecord:
    return EvidenceRecord(
        type=EvidenceType.REPOSITORY_CONFIG,
        artifact=artifact,
    )


def runtime_evidence(
    artifact: str = "trace-001",
) -> EvidenceRecord:
    return EvidenceRecord(
        type=EvidenceType.RUNTIME_TRACE,
        artifact=artifact,
    )


def checkout_endpoint() -> NormalizedEndpoint:
    return NormalizedEndpoint(
        id="checkout",
        type=NodeType.SERVICE,
    )


def recommendation_endpoint() -> NormalizedEndpoint:
    return NormalizedEndpoint(
        id="recommendation",
        type=NodeType.SERVICE,
    )


# =============================================================================
# Mapping Vocabulary
# =============================================================================


@pytest.mark.parametrize(
    ("interaction", "expected_relation"),
    (
        (
            InteractionType.SERVICE_CALL,
            RelationType.CALLS,
        ),
        (
            InteractionType.DATA_READ,
            RelationType.READS_FROM,
        ),
        (
            InteractionType.DATA_WRITE,
            RelationType.WRITES_TO,
        ),
        (
            InteractionType.MESSAGE_PUBLISH,
            RelationType.PUBLISHES_TO,
        ),
        (
            InteractionType.MESSAGE_SUBSCRIBE,
            RelationType.SUBSCRIBES_TO,
        ),
        (
            InteractionType.ROUTE,
            RelationType.ROUTES_TO,
        ),
        (
            InteractionType.DISCOVERY,
            RelationType.DISCOVERS_VIA,
        ),
        (
            InteractionType.EXPOSURE,
            RelationType.EXPOSES_TO,
        ),
    ),
)
def test_interaction_mapping_is_complete(
    interaction: InteractionType,
    expected_relation: RelationType,
) -> None:
    assert INTERACTION_TO_RELATION[interaction] is expected_relation


def test_every_interaction_has_canonical_mapping() -> None:
    assert set(INTERACTION_TO_RELATION) == set(InteractionType)


# =============================================================================
# Endpoint
# =============================================================================


def test_normalized_endpoint_creates_architecture_node() -> None:
    endpoint = checkout_endpoint()

    node = endpoint.to_architecture_node()

    assert node.id == "checkout"
    assert node.type is NodeType.SERVICE


# =============================================================================
# Evidence Boundary
# =============================================================================


def test_node_observation_requires_evidence() -> None:
    with pytest.raises(
        ValidationError,
        match="at least one evidence record",
    ):
        NormalizedNodeObservation(
            endpoint=checkout_endpoint(),
            evidence=(),
        )


def test_relation_observation_requires_evidence() -> None:
    with pytest.raises(
        ValidationError,
        match="at least one evidence record",
    ):
        NormalizedRelationObservation(
            source=checkout_endpoint(),
            target=recommendation_endpoint(),
            interaction=InteractionType.SERVICE_CALL,
            evidence=(),
        )


def test_normalized_observation_rejects_mixed_evidence_channels() -> None:
    with pytest.raises(
        ValidationError,
        match="multiple evidence channels",
    ):
        NormalizedRelationObservation(
            source=checkout_endpoint(),
            target=recommendation_endpoint(),
            interaction=InteractionType.SERVICE_CALL,
            evidence=(
                source_evidence(),
                runtime_evidence(),
            ),
        )


def test_multiple_non_runtime_records_are_allowed() -> None:
    observation = NormalizedRelationObservation(
        source=checkout_endpoint(),
        target=recommendation_endpoint(),
        interaction=InteractionType.SERVICE_CALL,
        evidence=(
            source_evidence(),
            repository_evidence(),
        ),
    )

    assert observation.channel is EvidenceChannel.NON_RUNTIME

    assert len(observation.evidence) == 2


def test_duplicate_evidence_is_deduplicated() -> None:
    evidence = source_evidence()

    observation = NormalizedRelationObservation(
        source=checkout_endpoint(),
        target=recommendation_endpoint(),
        interaction=InteractionType.SERVICE_CALL,
        evidence=(
            evidence,
            evidence,
        ),
    )

    assert len(observation.evidence) == 1


# =============================================================================
# Relation Canonicalization
# =============================================================================


def test_service_call_becomes_calls_relation() -> None:
    observation = NormalizedRelationObservation(
        source=checkout_endpoint(),
        target=recommendation_endpoint(),
        interaction=InteractionType.SERVICE_CALL,
        protocol="HTTP",
        evidence=(source_evidence(),),
    )

    candidate = canonicalize_relation_observation(observation)

    assert candidate.relation.identity == (
        "checkout",
        RelationType.CALLS,
        "recommendation",
    )

    assert candidate.protocol == "http"

    assert candidate.channel is EvidenceChannel.NON_RUNTIME


def test_runtime_service_call_becomes_same_canonical_relation() -> None:
    observation = NormalizedRelationObservation(
        source=checkout_endpoint(),
        target=recommendation_endpoint(),
        interaction=InteractionType.SERVICE_CALL,
        protocol="gRPC",
        evidence=(runtime_evidence(),),
    )

    candidate = canonicalize_relation_observation(observation)

    assert candidate.relation.identity == (
        "checkout",
        RelationType.CALLS,
        "recommendation",
    )

    assert candidate.protocol == "grpc"

    assert candidate.channel is EvidenceChannel.RUNTIME


def test_protocol_does_not_change_canonical_identity() -> None:
    http_observation = NormalizedRelationObservation(
        source=checkout_endpoint(),
        target=recommendation_endpoint(),
        interaction=InteractionType.SERVICE_CALL,
        protocol="http",
        evidence=(source_evidence(),),
    )

    grpc_observation = NormalizedRelationObservation(
        source=checkout_endpoint(),
        target=recommendation_endpoint(),
        interaction=InteractionType.SERVICE_CALL,
        protocol="grpc",
        evidence=(runtime_evidence(),),
    )

    http_candidate = canonicalize_relation_observation(http_observation)

    grpc_candidate = canonicalize_relation_observation(grpc_observation)

    assert http_candidate.identity == grpc_candidate.identity


# =============================================================================
# Node Canonicalization
# =============================================================================


def test_node_observation_becomes_node_candidate() -> None:
    observation = NormalizedNodeObservation(
        endpoint=checkout_endpoint(),
        evidence=(repository_evidence(),),
    )

    candidate = canonicalize_observation(observation)

    assert isinstance(
        candidate,
        CanonicalNodeCandidate,
    )

    assert candidate.node.id == "checkout"

    assert candidate.channel is EvidenceChannel.NON_RUNTIME


# =============================================================================
# Relation Candidate Integrity
# =============================================================================


def test_relation_candidate_contains_endpoint_nodes() -> None:
    observation = NormalizedRelationObservation(
        source=checkout_endpoint(),
        target=recommendation_endpoint(),
        interaction=InteractionType.SERVICE_CALL,
        evidence=(runtime_evidence(),),
    )

    candidate = canonicalize_observation(observation)

    assert isinstance(
        candidate,
        CanonicalRelationCandidate,
    )

    assert candidate.source_node.id == "checkout"

    assert candidate.target_node.id == "recommendation"


def test_canonical_relation_contains_no_protocol() -> None:
    observation = NormalizedRelationObservation(
        source=checkout_endpoint(),
        target=recommendation_endpoint(),
        interaction=InteractionType.SERVICE_CALL,
        protocol="grpc",
        evidence=(runtime_evidence(),),
    )

    candidate = canonicalize_relation_observation(observation)

    dumped_relation = candidate.relation.model_dump()

    assert "protocol" not in dumped_relation
    assert "evidence" not in dumped_relation


# =============================================================================
# Experimental Separation
# =============================================================================


def test_non_runtime_and_runtime_remain_separate_candidates() -> None:
    non_runtime = canonicalize_relation_observation(
        NormalizedRelationObservation(
            source=checkout_endpoint(),
            target=recommendation_endpoint(),
            interaction=InteractionType.SERVICE_CALL,
            protocol="http",
            evidence=(source_evidence(),),
        )
    )

    runtime = canonicalize_relation_observation(
        NormalizedRelationObservation(
            source=checkout_endpoint(),
            target=recommendation_endpoint(),
            interaction=InteractionType.SERVICE_CALL,
            protocol="http",
            evidence=(runtime_evidence(),),
        )
    )

    assert non_runtime.identity == runtime.identity

    assert non_runtime.channel is EvidenceChannel.NON_RUNTIME

    assert runtime.channel is EvidenceChannel.RUNTIME

    assert non_runtime != runtime
