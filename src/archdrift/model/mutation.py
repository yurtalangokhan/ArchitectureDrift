from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, Self

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from archdrift.model._validation import (
    normalize_identifier,
    normalize_optional_text,
    normalize_required_text,
)
from archdrift.model.graph import (
    ArchitectureNode,
    ArchitectureRelation,
    NodeType,
    RelationIdentity,
)

# =============================================================================
# Exceptions
# =============================================================================


class MutationOracleError(ValueError):
    """Base exception for mutation-oracle operations."""


class MutationOracleLoadError(MutationOracleError):
    """Raised when a mutation-oracle document cannot be loaded."""


# =============================================================================
# Mutation Vocabulary
# =============================================================================


class MutationOperationType(StrEnum):
    """
    Primitive controlled mutation operations.

    The vocabulary deliberately operates on the Canonical Architecture Graph
    rather than technology-specific implementation constructs.
    """

    ADD_NODE = "ADD_NODE"
    REMOVE_NODE = "REMOVE_NODE"
    ADD_RELATION = "ADD_RELATION"
    REMOVE_RELATION = "REMOVE_RELATION"


# =============================================================================
# Mutation Operation Models
# =============================================================================


class MutationOperationBase(BaseModel):
    """Base type for one controlled graph mutation operation."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )


class AddNodeOperation(MutationOperationBase):
    """Add one canonical architecture node."""

    operation: Literal[
        MutationOperationType.ADD_NODE
    ] = MutationOperationType.ADD_NODE

    node: ArchitectureNode


class RemoveNodeOperation(MutationOperationBase):
    """Remove one canonical architecture node."""

    operation: Literal[
        MutationOperationType.REMOVE_NODE
    ] = MutationOperationType.REMOVE_NODE

    node: ArchitectureNode


class AddRelationOperation(MutationOperationBase):
    """Add one canonical architecture relation."""

    operation: Literal[
        MutationOperationType.ADD_RELATION
    ] = MutationOperationType.ADD_RELATION

    relation: ArchitectureRelation


class RemoveRelationOperation(MutationOperationBase):
    """Remove one canonical architecture relation."""

    operation: Literal[
        MutationOperationType.REMOVE_RELATION
    ] = MutationOperationType.REMOVE_RELATION

    relation: ArchitectureRelation


MutationOperation = Annotated[
    AddNodeOperation
    | RemoveNodeOperation
    | AddRelationOperation
    | RemoveRelationOperation,
    Field(discriminator="operation"),
]


# =============================================================================
# Expected Graph Delta
# =============================================================================


class ExpectedGraphDelta(BaseModel):
    """
    Ground-truth graph delta expected after mutation activation.

    This model is intentionally independent from the future
    ``analysis.graph_delta.GraphDelta`` result model.

    The former is oracle data. The latter will be computed from graphs.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    added_nodes: tuple[ArchitectureNode, ...] = ()

    removed_nodes: tuple[ArchitectureNode, ...] = ()

    added_relations: tuple[ArchitectureRelation, ...] = ()

    removed_relations: tuple[ArchitectureRelation, ...] = ()

    @field_validator(
        "added_nodes",
        "removed_nodes",
    )
    @classmethod
    def validate_nodes(
        cls,
        value: tuple[ArchitectureNode, ...],
    ) -> tuple[ArchitectureNode, ...]:
        identities = tuple(
            node.id
            for node in value
        )

        if len(identities) != len(set(identities)):
            raise ValueError(
                "Expected graph delta contains duplicate node identifiers."
            )

        return tuple(
            sorted(
                value,
                key=lambda node: node.id,
            )
        )

    @field_validator(
        "added_relations",
        "removed_relations",
    )
    @classmethod
    def validate_relations(
        cls,
        value: tuple[ArchitectureRelation, ...],
    ) -> tuple[ArchitectureRelation, ...]:
        identities = tuple(
            relation.identity
            for relation in value
        )

        if len(identities) != len(set(identities)):
            raise ValueError(
                "Expected graph delta contains duplicate relation identities."
            )

        return tuple(
            sorted(
                value,
                key=lambda relation: (
                    relation.source,
                    relation.relation.value,
                    relation.target,
                ),
            )
        )

    @model_validator(mode="after")
    def validate_no_contradictory_delta(
        self,
    ) -> Self:
        added_node_ids = {
            node.id
            for node in self.added_nodes
        }

        removed_node_ids = {
            node.id
            for node in self.removed_nodes
        }

        contradictory_nodes = (
            added_node_ids
            & removed_node_ids
        )

        if contradictory_nodes:
            values = ", ".join(
                sorted(contradictory_nodes)
            )

            raise ValueError(
                "Expected graph delta cannot both add and remove "
                f"the same node: {values}"
            )

        added_relation_ids = {
            relation.identity
            for relation in self.added_relations
        }

        removed_relation_ids = {
            relation.identity
            for relation in self.removed_relations
        }

        contradictory_relations = (
            added_relation_ids
            & removed_relation_ids
        )

        if contradictory_relations:
            raise ValueError(
                "Expected graph delta cannot both add and remove "
                "the same canonical relation."
            )

        return self

    @property
    def is_empty(self) -> bool:
        """Return whether the expected delta contains no graph change."""

        return not (
            self.added_nodes
            or self.removed_nodes
            or self.added_relations
            or self.removed_relations
        )

    @property
    def added_relation_identities(
        self,
    ) -> frozenset[RelationIdentity]:
        """Return expected added canonical relation identities."""

        return frozenset(
            relation.identity
            for relation in self.added_relations
        )

    @property
    def removed_relation_identities(
        self,
    ) -> frozenset[RelationIdentity]:
        """Return expected removed canonical relation identities."""

        return frozenset(
            relation.identity
            for relation in self.removed_relations
        )


# =============================================================================
# Mutation Oracle Metadata
# =============================================================================


class MutationOracleMetadata(BaseModel):
    """
    Optional immutable metadata associated with one controlled mutation.

    Metadata does not participate in mutation semantics.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    case_system: str | None = None

    purpose: str | None = None

    revision: str | None = None

    @field_validator(
        "case_system",
        "purpose",
        "revision",
    )
    @classmethod
    def normalize_text(
        cls,
        value: str | None,
    ) -> str | None:
        return normalize_optional_text(value)


# =============================================================================
# Internal Identity Helpers
# =============================================================================


def _node_oracle_identity(
    node: ArchitectureNode,
) -> tuple[str, NodeType]:
    return (
        node.id,
        node.type,
    )


def _operation_sort_key(
    operation: MutationOperation,
) -> tuple[str, str, str, str]:
    if isinstance(
        operation,
        (AddNodeOperation, RemoveNodeOperation),
    ):
        return (
            operation.operation.value,
            operation.node.id,
            operation.node.type.value,
            "",
        )

    return (
        operation.operation.value,
        operation.relation.source,
        operation.relation.relation.value,
        operation.relation.target,
    )


# =============================================================================
# Mutation Oracle
# =============================================================================


class MutationOracle(BaseModel):
    """
    Ground-truth specification for one controlled architectural mutation.

    ``operations`` describes the graph changes intentionally injected into
    the baseline architecture.

    ``expected_delta`` independently records the graph-level oracle against
    which the future graph-delta analysis result will be evaluated.

    ``expected_violated_contracts`` identifies architecture contracts that
    are expected to become violated after mutation activation.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    schema_version: Literal["1.0"] = "1.0"

    mutation_id: str

    system_id: str

    description: str

    rationale: str | None = None

    operations: tuple[
        MutationOperation,
        ...,
    ]

    expected_delta: ExpectedGraphDelta

    expected_violated_contracts: tuple[str, ...] = ()

    metadata: MutationOracleMetadata = Field(
        default_factory=MutationOracleMetadata,
    )

    @field_validator(
        "mutation_id",
        "system_id",
    )
    @classmethod
    def validate_identifier(
        cls,
        value: str,
        info: object,
    ) -> str:
        field_name = getattr(
            info,
            "field_name",
            "identifier",
        )

        return normalize_identifier(
            value,
            field_name=str(field_name),
        )

    @field_validator("description")
    @classmethod
    def validate_description(
        cls,
        value: str,
    ) -> str:
        return normalize_required_text(
            value,
            field_name="description",
        )

    @field_validator("rationale")
    @classmethod
    def validate_rationale(
        cls,
        value: str | None,
    ) -> str | None:
        return normalize_optional_text(value)

    @field_validator("operations")
    @classmethod
    def validate_operations(
        cls,
        value: tuple[
            MutationOperation,
            ...,
        ],
    ) -> tuple[
        MutationOperation,
        ...,
    ]:
        if not value:
            raise ValueError(
                "Mutation oracle requires at least one operation."
            )

        sorted_operations = tuple(
            sorted(
                value,
                key=_operation_sort_key,
            )
        )

        operation_keys = tuple(
            _operation_sort_key(operation)
            for operation in sorted_operations
        )

        if len(operation_keys) != len(set(operation_keys)):
            raise ValueError(
                "Mutation oracle contains duplicate operations."
            )

        return sorted_operations

    @field_validator("expected_violated_contracts")
    @classmethod
    def validate_expected_contracts(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        normalized = tuple(
            normalize_identifier(
                contract_id,
                field_name="contract id",
            )
            for contract_id in value
        )

        if len(normalized) != len(set(normalized)):
            raise ValueError(
                "Expected violated contracts must not contain duplicates."
            )

        return tuple(sorted(normalized))

    @model_validator(mode="after")
    def validate_oracle_consistency(
        self,
    ) -> Self:
        added_nodes: set[
            tuple[str, NodeType]
        ] = set()

        removed_nodes: set[
            tuple[str, NodeType]
        ] = set()

        added_relations: set[
            RelationIdentity
        ] = set()

        removed_relations: set[
            RelationIdentity
        ] = set()

        for operation in self.operations:
            if isinstance(
                operation,
                AddNodeOperation,
            ):
                added_nodes.add(
                    _node_oracle_identity(
                        operation.node
                    )
                )

            elif isinstance(
                operation,
                RemoveNodeOperation,
            ):
                removed_nodes.add(
                    _node_oracle_identity(
                        operation.node
                    )
                )

            elif isinstance(
                operation,
                AddRelationOperation,
            ):
                added_relations.add(
                    operation.relation.identity
                )

            elif isinstance(
                operation,
                RemoveRelationOperation,
            ):
                removed_relations.add(
                    operation.relation.identity
                )

        contradictory_nodes = {
            node_id
            for node_id, _ in added_nodes
        } & {
            node_id
            for node_id, _ in removed_nodes
        }

        if contradictory_nodes:
            values = ", ".join(
                sorted(contradictory_nodes)
            )

            raise ValueError(
                "Mutation operations cannot both add and remove "
                f"the same node: {values}"
            )

        if added_relations & removed_relations:
            raise ValueError(
                "Mutation operations cannot both add and remove "
                "the same canonical relation."
            )

        expected_added_nodes = {
            _node_oracle_identity(node)
            for node in self.expected_delta.added_nodes
        }

        expected_removed_nodes = {
            _node_oracle_identity(node)
            for node in self.expected_delta.removed_nodes
        }

        if added_nodes != expected_added_nodes:
            raise ValueError(
                "ADD_NODE operations do not match "
                "expected_delta.added_nodes."
            )

        if removed_nodes != expected_removed_nodes:
            raise ValueError(
                "REMOVE_NODE operations do not match "
                "expected_delta.removed_nodes."
            )

        if (
            added_relations
            != self.expected_delta.added_relation_identities
        ):
            raise ValueError(
                "ADD_RELATION operations do not match "
                "expected_delta.added_relations."
            )

        if (
            removed_relations
            != self.expected_delta.removed_relation_identities
        ):
            raise ValueError(
                "REMOVE_RELATION operations do not match "
                "expected_delta.removed_relations."
            )

        if self.expected_delta.is_empty:
            raise ValueError(
                "Controlled mutation must produce a non-empty "
                "expected graph delta."
            )

        return self


# =============================================================================
# YAML Loader
# =============================================================================


def load_mutation_oracle(
    path: str | Path,
) -> MutationOracle:
    """
    Load and validate one mutation-oracle YAML document.

    YAML syntax and root-structure failures are translated into a stable
    domain-level exception.

    Pydantic ValidationError intentionally propagates so callers retain
    field-level validation details.
    """

    oracle_path = Path(path)

    if not oracle_path.is_file():
        raise FileNotFoundError(
            f"Mutation oracle file not found: {oracle_path}"
        )

    try:
        with oracle_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            raw_document = yaml.safe_load(file)

    except yaml.YAMLError as exc:
        raise MutationOracleLoadError(
            f"Invalid YAML in mutation oracle file: {oracle_path}"
        ) from exc

    if raw_document is None:
        raise MutationOracleLoadError(
            f"Mutation oracle file is empty: {oracle_path}"
        )

    if not isinstance(raw_document, dict):
        raise MutationOracleLoadError(
            "Mutation oracle YAML root must be a mapping."
        )

    return MutationOracle.model_validate(
        raw_document
    )