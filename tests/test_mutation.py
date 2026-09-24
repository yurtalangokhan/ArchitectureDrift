from pathlib import Path

import pytest
from pydantic import ValidationError

from archdrift.model import (
    AddNodeOperation,
    AddRelationOperation,
    ArchitectureNode,
    ArchitectureRelation,
    ExpectedGraphDelta,
    MutationOperationType,
    MutationOracle,
    MutationOracleLoadError,
    NodeType,
    RelationType,
    RemoveNodeOperation,
    RemoveRelationOperation,
    load_mutation_oracle,
)

# =============================================================================
# Vocabulary
# =============================================================================


def test_mutation_operation_vocabulary() -> None:
    assert set(MutationOperationType) == {
        MutationOperationType.ADD_NODE,
        MutationOperationType.REMOVE_NODE,
        MutationOperationType.ADD_RELATION,
        MutationOperationType.REMOVE_RELATION,
    }


# =============================================================================
# Operation Models
# =============================================================================


def test_add_relation_operation_can_be_created() -> None:
    operation = AddRelationOperation(
        relation=ArchitectureRelation(
            source="checkout",
            relation=RelationType.CALLS,
            target="recommendation",
        )
    )

    assert (
        operation.operation
        is MutationOperationType.ADD_RELATION
    )

    assert operation.relation.identity == (
        "checkout",
        RelationType.CALLS,
        "recommendation",
    )


def test_remove_relation_operation_can_be_created() -> None:
    operation = RemoveRelationOperation(
        relation=ArchitectureRelation(
            source="checkout",
            relation=RelationType.CALLS,
            target="payment",
        )
    )

    assert (
        operation.operation
        is MutationOperationType.REMOVE_RELATION
    )


def test_add_node_operation_can_be_created() -> None:
    operation = AddNodeOperation(
        node=ArchitectureNode(
            id="rogue-service",
            type=NodeType.SERVICE,
        )
    )

    assert operation.node.id == "rogue-service"


def test_remove_node_operation_can_be_created() -> None:
    operation = RemoveNodeOperation(
        node=ArchitectureNode(
            id="obsolete-service",
            type=NodeType.SERVICE,
        )
    )

    assert operation.node.id == "obsolete-service"


# =============================================================================
# Expected Delta
# =============================================================================


def test_expected_delta_exposes_relation_identities() -> None:
    delta = ExpectedGraphDelta(
        added_relations=(
            ArchitectureRelation(
                source="checkout",
                relation=RelationType.CALLS,
                target="recommendation",
            ),
        ),
    )

    assert delta.added_relation_identities == frozenset(
        {
            (
                "checkout",
                RelationType.CALLS,
                "recommendation",
            )
        }
    )


def test_expected_delta_detects_empty_delta() -> None:
    delta = ExpectedGraphDelta()

    assert delta.is_empty is True


def test_expected_delta_rejects_duplicate_relations() -> None:
    relation = ArchitectureRelation(
        source="checkout",
        relation=RelationType.CALLS,
        target="recommendation",
    )

    with pytest.raises(
        ValidationError,
        match="duplicate relation identities",
    ):
        ExpectedGraphDelta(
            added_relations=(
                relation,
                relation,
            )
        )


def test_expected_delta_rejects_contradictory_relation_change() -> None:
    relation = ArchitectureRelation(
        source="checkout",
        relation=RelationType.CALLS,
        target="recommendation",
    )

    with pytest.raises(
        ValidationError,
        match="both add and remove",
    ):
        ExpectedGraphDelta(
            added_relations=(
                relation,
            ),
            removed_relations=(
                relation,
            ),
        )


# =============================================================================
# Mutation Oracle
# =============================================================================


def test_mutation_oracle_can_be_created() -> None:
    relation = ArchitectureRelation(
        source="checkout",
        relation=RelationType.CALLS,
        target="recommendation",
    )

    oracle = MutationOracle(
        mutation_id="AS-M01",
        system_id="astronomy-shop",
        description="Unexpected checkout to recommendation connector.",
        operations=(
            AddRelationOperation(
                relation=relation
            ),
        ),
        expected_delta=ExpectedGraphDelta(
            added_relations=(
                relation,
            )
        ),
        expected_violated_contracts=(
            "AS-C001",
        ),
    )

    assert oracle.mutation_id == "AS-M01"

    assert oracle.expected_violated_contracts == (
        "AS-C001",
    )


def test_mutation_oracle_requires_operation() -> None:
    with pytest.raises(
        ValidationError,
        match="at least one operation",
    ):
        MutationOracle(
            mutation_id="AS-M01",
            system_id="astronomy-shop",
            description="Invalid empty mutation.",
            operations=(),
            expected_delta=ExpectedGraphDelta(),
        )


def test_mutation_oracle_rejects_empty_expected_delta() -> None:
    node = ArchitectureNode(
        id="rogue-service",
        type=NodeType.SERVICE,
    )

    with pytest.raises(ValidationError):
        MutationOracle(
            mutation_id="AS-M01",
            system_id="astronomy-shop",
            description="Invalid mutation oracle.",
            operations=(
                AddNodeOperation(
                    node=node
                ),
            ),
            expected_delta=ExpectedGraphDelta(),
        )


def test_add_relation_operation_must_match_expected_delta() -> None:
    operation_relation = ArchitectureRelation(
        source="checkout",
        relation=RelationType.CALLS,
        target="recommendation",
    )

    expected_relation = ArchitectureRelation(
        source="checkout",
        relation=RelationType.CALLS,
        target="payment",
    )

    with pytest.raises(
        ValidationError,
        match="ADD_RELATION operations do not match",
    ):
        MutationOracle(
            mutation_id="AS-M01",
            system_id="astronomy-shop",
            description="Inconsistent mutation oracle.",
            operations=(
                AddRelationOperation(
                    relation=operation_relation
                ),
            ),
            expected_delta=ExpectedGraphDelta(
                added_relations=(
                    expected_relation,
                )
            ),
        )


def test_mutation_oracle_rejects_duplicate_contract_ids() -> None:
    relation = ArchitectureRelation(
        source="checkout",
        relation=RelationType.CALLS,
        target="recommendation",
    )

    with pytest.raises(
        ValidationError,
        match="must not contain duplicates",
    ):
        MutationOracle(
            mutation_id="AS-M01",
            system_id="astronomy-shop",
            description="Invalid oracle.",
            operations=(
                AddRelationOperation(
                    relation=relation
                ),
            ),
            expected_delta=ExpectedGraphDelta(
                added_relations=(
                    relation,
                )
            ),
            expected_violated_contracts=(
                "AS-C001",
                "AS-C001",
            ),
        )


def test_mutation_oracle_json_round_trip() -> None:
    relation = ArchitectureRelation(
        source="checkout",
        relation=RelationType.CALLS,
        target="recommendation",
    )

    oracle = MutationOracle(
        mutation_id="AS-M01",
        system_id="astronomy-shop",
        description="Unexpected connector.",
        operations=(
            AddRelationOperation(
                relation=relation
            ),
        ),
        expected_delta=ExpectedGraphDelta(
            added_relations=(
                relation,
            )
        ),
        expected_violated_contracts=(
            "AS-C001",
        ),
    )

    serialized = oracle.model_dump_json()

    restored = MutationOracle.model_validate_json(
        serialized
    )

    assert restored == oracle


# =============================================================================
# Repository Oracle
# =============================================================================


def test_load_astronomy_shop_as_m01() -> None:
    project_root = Path(__file__).resolve().parents[1]

    oracle = load_mutation_oracle(
        project_root
        / "mutations"
        / "astronomy-shop"
        / "AS-M01.yaml"
    )

    assert oracle.mutation_id == "AS-M01"
    assert oracle.system_id == "astronomy-shop"

    assert len(oracle.operations) == 1

    operation = oracle.operations[0]

    assert isinstance(
        operation,
        AddRelationOperation,
    )

    assert operation.relation.identity == (
        "checkout",
        RelationType.CALLS,
        "recommendation",
    )

    assert (
        oracle.expected_delta.added_relation_identities
        == frozenset(
            {
                (
                    "checkout",
                    RelationType.CALLS,
                    "recommendation",
                )
            }
        )
    )

    assert oracle.expected_violated_contracts == (
        "AS-C001",
    )


# =============================================================================
# YAML Boundary
# =============================================================================


def test_loader_rejects_missing_file(
    tmp_path: Path,
) -> None:
    with pytest.raises(FileNotFoundError):
        load_mutation_oracle(
            tmp_path / "missing.yaml"
        )


def test_loader_rejects_empty_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "empty.yaml"

    path.write_text(
        "",
        encoding="utf-8",
    )

    with pytest.raises(
        MutationOracleLoadError,
        match="empty",
    ):
        load_mutation_oracle(path)


def test_loader_rejects_non_mapping_root(
    tmp_path: Path,
) -> None:
    path = tmp_path / "invalid-root.yaml"

    path.write_text(
        "- item-one\n- item-two\n",
        encoding="utf-8",
    )

    with pytest.raises(
        MutationOracleLoadError,
        match="root must be a mapping",
    ):
        load_mutation_oracle(path)


def test_loader_rejects_invalid_yaml(
    tmp_path: Path,
) -> None:
    path = tmp_path / "invalid.yaml"

    path.write_text(
        "operations: [\n",
        encoding="utf-8",
    )

    with pytest.raises(
        MutationOracleLoadError,
        match="Invalid YAML",
    ):
        load_mutation_oracle(path)