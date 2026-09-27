from __future__ import annotations

from archdrift.analysis.scope import (
    EvidenceScope,
    ScopeExclusionReason,
    apply_evidence_scope,
)
from archdrift.model import (
    EvidenceRecord,
    EvidenceType,
    InteractionType,
    NodeType,
    NormalizedEndpoint,
    NormalizedNodeObservation,
    NormalizedRelationObservation,
)


def evidence(
    artifact: str,
) -> tuple[EvidenceRecord, ...]:
    return (
        EvidenceRecord(
            type=EvidenceType.DEPLOYMENT_CONFIG,
            artifact=artifact,
            locator="test",
        ),
    )


def test_scope_keeps_node_inside_boundary() -> None:
    observation = NormalizedNodeObservation(
        endpoint=NormalizedEndpoint(
            id="checkout",
            type=NodeType.SERVICE,
        ),
        evidence=evidence(
            "compose.yaml"
        ),
    )

    result = apply_evidence_scope(
        (
            observation,
        ),
        scope=EvidenceScope(
            node_ids=frozenset(
                {
                    "checkout",
                }
            )
        ),
    )

    assert result.included == (
        observation,
    )

    assert result.excluded == ()


def test_scope_excludes_node_outside_boundary() -> None:
    observation = NormalizedNodeObservation(
        endpoint=NormalizedEndpoint(
            id="otel-collector",
            type=NodeType.SERVICE,
        ),
        evidence=evidence(
            "compose.yaml"
        ),
    )

    result = apply_evidence_scope(
        (
            observation,
        ),
        scope=EvidenceScope(
            node_ids=frozenset(
                {
                    "checkout",
                }
            )
        ),
    )

    assert result.included == ()

    assert len(
        result.excluded
    ) == 1

    assert (
        result.excluded[0].reason
        is ScopeExclusionReason.NODE_OUT_OF_SCOPE
    )


def test_scope_keeps_relation_when_both_endpoints_are_inside() -> None:
    observation = NormalizedRelationObservation(
        source=NormalizedEndpoint(
            id="checkout",
            type=NodeType.SERVICE,
        ),
        target=NormalizedEndpoint(
            id="recommendation",
            type=NodeType.SERVICE,
        ),
        interaction=(
            InteractionType.SERVICE_CALL
        ),
        protocol="http",
        evidence=evidence(
            "compose.yaml"
        ),
    )

    result = apply_evidence_scope(
        (
            observation,
        ),
        scope=EvidenceScope(
            node_ids=frozenset(
                {
                    "checkout",
                    "recommendation",
                }
            )
        ),
    )

    assert result.included == (
        observation,
    )

    assert result.excluded == ()


def test_scope_excludes_relation_when_source_is_outside() -> None:
    observation = NormalizedRelationObservation(
        source=NormalizedEndpoint(
            id="load-generator",
            type=NodeType.SERVICE,
        ),
        target=NormalizedEndpoint(
            id="frontend",
            type=NodeType.SERVICE,
        ),
        interaction=(
            InteractionType.SERVICE_CALL
        ),
        protocol="http",
        evidence=evidence(
            "compose.yaml"
        ),
    )

    result = apply_evidence_scope(
        (
            observation,
        ),
        scope=EvidenceScope(
            node_ids=frozenset(
                {
                    "frontend",
                }
            )
        ),
    )

    assert result.included == ()

    assert (
        result.excluded[0].reason
        is ScopeExclusionReason.RELATION_SOURCE_OUT_OF_SCOPE
    )


def test_scope_excludes_relation_when_target_is_outside() -> None:
    observation = NormalizedRelationObservation(
        source=NormalizedEndpoint(
            id="frontend",
            type=NodeType.SERVICE,
        ),
        target=NormalizedEndpoint(
            id="otel-collector",
            type=NodeType.SERVICE,
        ),
        interaction=(
            InteractionType.SERVICE_CALL
        ),
        protocol="http",
        evidence=evidence(
            "compose.yaml"
        ),
    )

    result = apply_evidence_scope(
        (
            observation,
        ),
        scope=EvidenceScope(
            node_ids=frozenset(
                {
                    "frontend",
                }
            )
        ),
    )

    assert result.included == ()

    assert (
        result.excluded[0].reason
        is ScopeExclusionReason.RELATION_TARGET_OUT_OF_SCOPE
    )


def test_scope_preserves_original_observation_order() -> None:
    first = NormalizedNodeObservation(
        endpoint=NormalizedEndpoint(
            id="checkout",
            type=NodeType.SERVICE,
        ),
        evidence=evidence(
            "compose.yaml"
        ),
    )

    second = NormalizedNodeObservation(
        endpoint=NormalizedEndpoint(
            id="recommendation",
            type=NodeType.SERVICE,
        ),
        evidence=evidence(
            "compose.yaml"
        ),
    )

    result = apply_evidence_scope(
        (
            first,
            second,
        ),
        scope=EvidenceScope(
            node_ids=frozenset(
                {
                    "checkout",
                    "recommendation",
                }
            )
        ),
    )

    assert result.included == (
        first,
        second,
    )