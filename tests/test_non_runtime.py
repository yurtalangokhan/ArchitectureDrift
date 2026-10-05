from archdrift.analysis.non_runtime import (
    analyze_non_runtime_complementarity,
    reconstruct_non_runtime_views,
)
from archdrift.analysis.scope import (
    EvidenceScope,
)
from archdrift.model import (
    EvidenceRecord,
    EvidenceType,
    InteractionType,
    NodeType,
    NormalizedEndpoint,
    NormalizedRelationObservation,
    RelationType,
)


def _relation(
    *,
    target: str,
    evidence_type: EvidenceType,
) -> NormalizedRelationObservation:
    return NormalizedRelationObservation(
        source=NormalizedEndpoint(
            id="webapp",
            type=NodeType.SERVICE,
        ),
        target=NormalizedEndpoint(
            id=target,
            type=NodeType.SERVICE,
        ),
        interaction=(InteractionType.SERVICE_CALL),
        evidence=(
            EvidenceRecord(
                type=evidence_type,
                artifact="fixture",
            ),
        ),
    )


def test_non_runtime_views_keep_ablation_boundaries() -> None:
    result = reconstruct_non_runtime_views(
        system_id="test-system",
        deployment_observations=(
            _relation(
                target="catalog-api",
                evidence_type=(EvidenceType.REPOSITORY_CONFIG),
            ),
        ),
        source_static_observations=(
            _relation(
                target="ordering-api",
                evidence_type=(EvidenceType.SOURCE_CODE),
            ),
        ),
        scope=EvidenceScope(
            node_ids=frozenset(
                {
                    "webapp",
                    "catalog-api",
                    "ordering-api",
                }
            )
        ),
    )

    deployment_graph = result.deployment.reconstruction.graph

    static_graph = result.source_static.reconstruction.graph

    combined_graph = result.combined.reconstruction.graph

    assert deployment_graph.relation_identities == frozenset(
        {
            (
                "webapp",
                RelationType.CALLS,
                "catalog-api",
            )
        }
    )

    assert static_graph.relation_identities == frozenset(
        {
            (
                "webapp",
                RelationType.CALLS,
                "ordering-api",
            )
        }
    )

    assert combined_graph.relation_identities == frozenset(
        {
            (
                "webapp",
                RelationType.CALLS,
                "catalog-api",
            ),
            (
                "webapp",
                RelationType.CALLS,
                "ordering-api",
            ),
        }
    )


def test_non_runtime_complementarity_metrics() -> None:
    views = reconstruct_non_runtime_views(
        system_id="test-system",
        deployment_observations=(
            _relation(
                target="catalog-api",
                evidence_type=(EvidenceType.REPOSITORY_CONFIG),
            ),
            _relation(
                target="basket-api",
                evidence_type=(EvidenceType.REPOSITORY_CONFIG),
            ),
        ),
        source_static_observations=(
            _relation(
                target="catalog-api",
                evidence_type=(EvidenceType.SOURCE_CODE),
            ),
            _relation(
                target="ordering-api",
                evidence_type=(EvidenceType.SOURCE_CODE),
            ),
        ),
        scope=EvidenceScope(
            node_ids=frozenset(
                {
                    "webapp",
                    "catalog-api",
                    "basket-api",
                    "ordering-api",
                }
            )
        ),
    )

    metrics = analyze_non_runtime_complementarity(views)

    assert metrics.deployment_relation_count == 2

    assert metrics.source_static_relation_count == 2

    assert metrics.combined_relation_count == 3

    assert metrics.overlap_relation_count == 1

    assert metrics.deployment_only_relation_count == 1

    assert metrics.source_static_only_relation_count == 1

    assert metrics.deployment_corroboration_rate == 0.5

    assert metrics.source_static_corroboration_rate == 0.5

    assert metrics.structural_gain_over_deployment_count == 1

    assert metrics.structural_gain_over_deployment_rate == 0.5
