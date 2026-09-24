from pathlib import Path

import pytest

from archdrift.analysis import (
    GraphComparisonError,
    compute_baseline_mutant_delta,
    compute_graph_delta,
    matches_expected_delta,
)
from archdrift.model import (
    ArchitectureGraph,
    ArchitectureNode,
    ArchitectureRelation,
    ExpectedGraphDelta,
    GraphMetadata,
    GraphRole,
    NodeType,
    RelationType,
    load_mutation_oracle,
)

# =============================================================================
# Helpers
# =============================================================================


def build_baseline() -> ArchitectureGraph:
    return ArchitectureGraph(
        metadata=GraphMetadata(
            system_id="astronomy-shop",
            role=GraphRole.BASELINE,
            revision="test-revision",
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
            ArchitectureNode(
                id="recommendation",
                type=NodeType.SERVICE,
            ),
        ),
        relations=(
            ArchitectureRelation(
                source="checkout",
                relation=RelationType.CALLS,
                target="payment",
            ),
        ),
    )


def build_as_m01_mutant() -> ArchitectureGraph:
    baseline = build_baseline()

    return ArchitectureGraph(
        metadata=GraphMetadata(
            system_id="astronomy-shop",
            role=GraphRole.MUTANT,
            variant="AS-M01",
            revision="test-revision",
        ),
        nodes=baseline.nodes,
        relations=(
            *baseline.relations,
            ArchitectureRelation(
                source="checkout",
                relation=RelationType.CALLS,
                target="recommendation",
            ),
        ),
    )


# =============================================================================
# Empty Delta
# =============================================================================


def test_identical_graphs_produce_empty_delta() -> None:
    graph = build_baseline()

    delta = compute_graph_delta(
        graph,
        graph,
    )

    assert delta.is_empty is True
    assert delta.change_count == 0

    assert delta.added_nodes == ()
    assert delta.removed_nodes == ()
    assert delta.added_relations == ()
    assert delta.removed_relations == ()


# =============================================================================
# Relation Delta
# =============================================================================


def test_added_relation_is_detected() -> None:
    baseline = build_baseline()
    mutant = build_as_m01_mutant()

    delta = compute_baseline_mutant_delta(
        baseline,
        mutant,
    )

    assert delta.change_count == 1

    assert delta.added_relation_identities == frozenset(
        {
            (
                "checkout",
                RelationType.CALLS,
                "recommendation",
            )
        }
    )

    assert delta.removed_relation_identities == frozenset()


def test_removed_relation_is_detected() -> None:
    baseline = build_baseline()

    mutant = ArchitectureGraph(
        metadata=GraphMetadata(
            system_id="astronomy-shop",
            role=GraphRole.MUTANT,
            variant="TEST-M01",
        ),
        nodes=baseline.nodes,
        relations=(),
    )

    delta = compute_baseline_mutant_delta(
        baseline,
        mutant,
    )

    assert delta.added_relation_identities == frozenset()

    assert delta.removed_relation_identities == frozenset(
        {
            (
                "checkout",
                RelationType.CALLS,
                "payment",
            )
        }
    )


# =============================================================================
# Node Delta
# =============================================================================


def test_added_node_is_detected() -> None:
    baseline = build_baseline()

    mutant = ArchitectureGraph(
        metadata=GraphMetadata(
            system_id="astronomy-shop",
            role=GraphRole.MUTANT,
            variant="TEST-M02",
        ),
        nodes=(
            *baseline.nodes,
            ArchitectureNode(
                id="rogue-service",
                type=NodeType.SERVICE,
            ),
        ),
        relations=baseline.relations,
    )

    delta = compute_baseline_mutant_delta(
        baseline,
        mutant,
    )

    assert delta.added_node_ids == frozenset(
        {
            "rogue-service",
        }
    )

    assert delta.removed_node_ids == frozenset()


def test_removed_node_and_incident_relation_are_detected() -> None:
    baseline = build_baseline()

    mutant = baseline.without_node(
        "payment"
    )

    mutant = ArchitectureGraph(
        metadata=GraphMetadata(
            system_id="astronomy-shop",
            role=GraphRole.MUTANT,
            variant="TEST-M03",
        ),
        nodes=mutant.nodes,
        relations=mutant.relations,
    )

    delta = compute_baseline_mutant_delta(
        baseline,
        mutant,
    )

    assert delta.removed_node_ids == frozenset(
        {
            "payment",
        }
    )

    assert delta.removed_relation_identities == frozenset(
        {
            (
                "checkout",
                RelationType.CALLS,
                "payment",
            )
        }
    )


# =============================================================================
# Comparison Validation
# =============================================================================


def test_graphs_from_different_systems_cannot_be_compared() -> None:
    baseline = build_baseline()

    other = ArchitectureGraph(
        metadata=GraphMetadata(
            system_id="eshop",
            role=GraphRole.MUTANT,
            variant="ES-M01",
        ),
    )

    with pytest.raises(
        GraphComparisonError,
        match="different systems",
    ):
        compute_graph_delta(
            baseline,
            other,
        )


def test_node_type_change_is_rejected() -> None:
    baseline = ArchitectureGraph(
        metadata=GraphMetadata(
            system_id="test-system",
            role=GraphRole.BASELINE,
        ),
        nodes=(
            ArchitectureNode(
                id="component",
                type=NodeType.SERVICE,
            ),
        ),
    )

    target = ArchitectureGraph(
        metadata=GraphMetadata(
            system_id="test-system",
            role=GraphRole.MUTANT,
            variant="TEST-M01",
        ),
        nodes=(
            ArchitectureNode(
                id="component",
                type=NodeType.GATEWAY,
            ),
        ),
    )

    with pytest.raises(
        GraphComparisonError,
        match="node type changed",
    ):
        compute_graph_delta(
            baseline,
            target,
        )


# =============================================================================
# Experiment Role Validation
# =============================================================================


def test_baseline_mutant_comparison_requires_baseline_role() -> None:
    invalid_baseline = ArchitectureGraph(
        metadata=GraphMetadata(
            system_id="astronomy-shop",
            role=GraphRole.MUTANT,
            variant="WRONG",
        ),
    )

    mutant = ArchitectureGraph(
        metadata=GraphMetadata(
            system_id="astronomy-shop",
            role=GraphRole.MUTANT,
            variant="AS-M01",
        ),
    )

    with pytest.raises(
        GraphComparisonError,
        match="role BASELINE",
    ):
        compute_baseline_mutant_delta(
            invalid_baseline,
            mutant,
        )


def test_baseline_mutant_comparison_requires_mutant_role() -> None:
    baseline = build_baseline()

    invalid_mutant = ArchitectureGraph(
        metadata=GraphMetadata(
            system_id="astronomy-shop",
            role=GraphRole.BASELINE,
        ),
    )

    with pytest.raises(
        GraphComparisonError,
        match="role MUTANT",
    ):
        compute_baseline_mutant_delta(
            baseline,
            invalid_mutant,
        )


# =============================================================================
# Oracle Matching
# =============================================================================


def test_as_m01_delta_matches_expected_oracle() -> None:
    baseline = build_baseline()
    mutant = build_as_m01_mutant()

    computed = compute_baseline_mutant_delta(
        baseline,
        mutant,
    )

    expected = ExpectedGraphDelta(
        added_relations=(
            ArchitectureRelation(
                source="checkout",
                relation=RelationType.CALLS,
                target="recommendation",
            ),
        )
    )

    assert matches_expected_delta(
        computed,
        expected,
    )


def test_incorrect_delta_does_not_match_oracle() -> None:
    baseline = build_baseline()
    mutant = build_as_m01_mutant()

    computed = compute_baseline_mutant_delta(
        baseline,
        mutant,
    )

    expected = ExpectedGraphDelta(
        added_relations=(
            ArchitectureRelation(
                source="checkout",
                relation=RelationType.CALLS,
                target="payment",
            ),
        )
    )

    assert not matches_expected_delta(
        computed,
        expected,
    )


# =============================================================================
# Determinism
# =============================================================================


def test_graph_delta_json_round_trip() -> None:
    baseline = build_baseline()
    mutant = build_as_m01_mutant()

    delta = compute_baseline_mutant_delta(
        baseline,
        mutant,
    )

    serialized = delta.model_dump_json()

    restored = type(delta).model_validate_json(
        serialized
    )

    assert restored == delta


def test_as_m01_computed_delta_matches_repository_oracle() -> None:
    project_root = Path(__file__).resolve().parents[1]

    oracle = load_mutation_oracle(
        project_root
        / "mutations"
        / "astronomy-shop"
        / "AS-M01.yaml"
    )

    baseline = build_baseline()
    mutant = build_as_m01_mutant()

    computed = compute_baseline_mutant_delta(
        baseline,
        mutant,
    )

    assert matches_expected_delta(
        computed,
        oracle.expected_delta,
    )