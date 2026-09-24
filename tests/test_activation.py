import pytest

from archdrift.experiments import (
    MutationActivationError,
    apply_mutation,
)
from archdrift.model import (
    AddRelationOperation,
    ArchitectureGraph,
    ArchitectureNode,
    ArchitectureRelation,
    ExpectedGraphDelta,
    GraphMetadata,
    GraphRole,
    MutationOracle,
    NodeType,
    RelationType,
)


def build_baseline() -> ArchitectureGraph:
    return ArchitectureGraph(
        metadata=GraphMetadata(
            system_id="astronomy-shop",
            role=GraphRole.BASELINE,
        ),
        nodes=(
            ArchitectureNode(
                id="checkout",
                type=NodeType.SERVICE,
            ),
            ArchitectureNode(
                id="recommendation",
                type=NodeType.SERVICE,
            ),
        ),
    )


def build_oracle() -> MutationOracle:
    relation = ArchitectureRelation(
        source="checkout",
        relation=RelationType.CALLS,
        target="recommendation",
    )

    return MutationOracle(
        mutation_id="AS-M01",
        system_id="astronomy-shop",
        description="Unexpected connector.",
        operations=(
            AddRelationOperation(
                relation=relation,
            ),
        ),
        expected_delta=ExpectedGraphDelta(
            added_relations=(
                relation,
            ),
        ),
        expected_violated_contracts=(
            "AS-C001",
        ),
    )


def test_apply_as_m01_relation() -> None:
    baseline = build_baseline()

    mutant = apply_mutation(
        baseline,
        build_oracle(),
    )

    assert mutant.metadata.role is GraphRole.MUTANT
    assert mutant.metadata.variant == "AS-M01"

    assert mutant.has_relation(
        source="checkout",
        relation=RelationType.CALLS,
        target="recommendation",
    )


def test_activation_does_not_mutate_baseline() -> None:
    baseline = build_baseline()

    apply_mutation(
        baseline,
        build_oracle(),
    )

    assert baseline.relations == ()


def test_activation_requires_baseline_role() -> None:
    invalid = ArchitectureGraph(
        metadata=GraphMetadata(
            system_id="astronomy-shop",
            role=GraphRole.MUTANT,
            variant="OTHER",
        ),
    )

    with pytest.raises(
        MutationActivationError,
        match="BASELINE",
    ):
        apply_mutation(
            invalid,
            build_oracle(),
        )