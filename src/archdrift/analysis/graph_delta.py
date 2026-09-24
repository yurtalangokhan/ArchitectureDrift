from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from archdrift.model.graph import (
    ArchitectureGraph,
    ArchitectureNode,
    ArchitectureRelation,
    GraphMetadata,
    GraphRole,
    RelationIdentity,
)
from archdrift.model.mutation import ExpectedGraphDelta

# =============================================================================
# Exceptions
# =============================================================================


class GraphDeltaError(ValueError):
    """Base exception for graph-delta analysis."""


class GraphComparisonError(GraphDeltaError):
    """
    Raised when two canonical architecture graphs cannot be meaningfully
    compared.
    """


# =============================================================================
# Graph Delta Result
# =============================================================================


class GraphDelta(BaseModel):
    """
    Immutable structural difference between two Canonical Architecture Graphs.

    The delta direction is:

        source -> target

    Therefore:

        added_*   = target - source
        removed_* = source - target

    GraphDelta contains computed analysis output and must not be confused with
    ExpectedGraphDelta, which represents mutation-oracle ground truth.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    source: GraphMetadata

    target: GraphMetadata

    added_nodes: tuple[ArchitectureNode, ...] = ()

    removed_nodes: tuple[ArchitectureNode, ...] = ()

    added_relations: tuple[ArchitectureRelation, ...] = ()

    removed_relations: tuple[ArchitectureRelation, ...] = ()

    # =========================================================================
    # Deterministic Ordering
    # =========================================================================

    @field_validator(
        "added_nodes",
        "removed_nodes",
    )
    @classmethod
    def order_nodes(
        cls,
        value: tuple[ArchitectureNode, ...],
    ) -> tuple[ArchitectureNode, ...]:
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
    def order_relations(
        cls,
        value: tuple[ArchitectureRelation, ...],
    ) -> tuple[ArchitectureRelation, ...]:
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

    # =========================================================================
    # Derived Sets
    # =========================================================================

    @property
    def is_empty(self) -> bool:
        """Return whether the graphs are structurally equivalent."""

        return not (
            self.added_nodes
            or self.removed_nodes
            or self.added_relations
            or self.removed_relations
        )

    @property
    def added_node_ids(self) -> frozenset[str]:
        """Return identifiers of added nodes."""

        return frozenset(
            node.id
            for node in self.added_nodes
        )

    @property
    def removed_node_ids(self) -> frozenset[str]:
        """Return identifiers of removed nodes."""

        return frozenset(
            node.id
            for node in self.removed_nodes
        )

    @property
    def added_relation_identities(
        self,
    ) -> frozenset[RelationIdentity]:
        """Return identities of added relations."""

        return frozenset(
            relation.identity
            for relation in self.added_relations
        )

    @property
    def removed_relation_identities(
        self,
    ) -> frozenset[RelationIdentity]:
        """Return identities of removed relations."""

        return frozenset(
            relation.identity
            for relation in self.removed_relations
        )

    @property
    def change_count(self) -> int:
        """Return the total number of structural graph changes."""

        return (
            len(self.added_nodes)
            + len(self.removed_nodes)
            + len(self.added_relations)
            + len(self.removed_relations)
        )


# =============================================================================
# Internal Helpers
# =============================================================================


def _node_map(
    graph: ArchitectureGraph,
) -> dict[str, ArchitectureNode]:
    return {
        node.id: node
        for node in graph.nodes
    }


def _relation_map(
    graph: ArchitectureGraph,
) -> dict[
    RelationIdentity,
    ArchitectureRelation,
]:
    return {
        relation.identity: relation
        for relation in graph.relations
    }


def _validate_graph_pair(
    source: ArchitectureGraph,
    target: ArchitectureGraph,
) -> None:
    """
    Validate whether two graphs can be compared.

    Node identity is canonical ``id``. A node retaining the same identifier
    while changing NodeType would therefore be ambiguous under the current
    mutation vocabulary. Such a comparison is rejected rather than silently
    losing the semantic change.
    """

    if (
        source.metadata.system_id
        != target.metadata.system_id
    ):
        raise GraphComparisonError(
            "Cannot compare architecture graphs from different systems: "
            f"{source.metadata.system_id!r} != "
            f"{target.metadata.system_id!r}"
        )

    source_nodes = _node_map(source)
    target_nodes = _node_map(target)

    common_node_ids = (
        source.node_ids
        & target.node_ids
    )

    for node_id in common_node_ids:
        source_node = source_nodes[node_id]
        target_node = target_nodes[node_id]

        if source_node.type is not target_node.type:
            raise GraphComparisonError(
                "Canonical node type changed without identity change: "
                f"{node_id!r}: "
                f"{source_node.type.value} -> "
                f"{target_node.type.value}. "
                "Node-type mutation is not supported by the current "
                "canonical mutation vocabulary."
            )


# =============================================================================
# Generic Graph Delta
# =============================================================================


def compute_graph_delta(
    source: ArchitectureGraph,
    target: ArchitectureGraph,
) -> GraphDelta:
    """
    Compute the structural delta from ``source`` to ``target``.

    The function is deliberately independent from mutation or contract
    semantics.

    Args:
        source:
            Original canonical graph.

        target:
            Canonical graph after some structural change.

    Returns:
        Immutable GraphDelta.

    Raises:
        GraphComparisonError:
            If the graphs belong to different systems or contain unsupported
            node-type changes.
    """

    _validate_graph_pair(
        source,
        target,
    )

    source_nodes = _node_map(source)
    target_nodes = _node_map(target)

    source_relations = _relation_map(source)
    target_relations = _relation_map(target)

    added_node_ids = (
        target.node_ids
        - source.node_ids
    )

    removed_node_ids = (
        source.node_ids
        - target.node_ids
    )

    added_relation_ids = (
        target.relation_identities
        - source.relation_identities
    )

    removed_relation_ids = (
        source.relation_identities
        - target.relation_identities
    )

    return GraphDelta(
        source=source.metadata,
        target=target.metadata,
        added_nodes=tuple(
            target_nodes[node_id]
            for node_id in added_node_ids
        ),
        removed_nodes=tuple(
            source_nodes[node_id]
            for node_id in removed_node_ids
        ),
        added_relations=tuple(
            target_relations[identity]
            for identity in added_relation_ids
        ),
        removed_relations=tuple(
            source_relations[identity]
            for identity in removed_relation_ids
        ),
    )


# =============================================================================
# Baseline -> Mutant Delta
# =============================================================================


def compute_baseline_mutant_delta(
    baseline: ArchitectureGraph,
    mutant: ArchitectureGraph,
) -> GraphDelta:
    """
    Compute a controlled Baseline -> Mutant graph delta.

    In addition to generic graph compatibility checks, this function enforces
    experiment-role semantics.
    """

    if baseline.metadata.role is not GraphRole.BASELINE:
        raise GraphComparisonError(
            "Baseline graph must have role BASELINE."
        )

    if mutant.metadata.role is not GraphRole.MUTANT:
        raise GraphComparisonError(
            "Mutant graph must have role MUTANT."
        )

    return compute_graph_delta(
        baseline,
        mutant,
    )


# =============================================================================
# Oracle Comparison
# =============================================================================


def matches_expected_delta(
    computed: GraphDelta,
    expected: ExpectedGraphDelta,
) -> bool:
    """
    Return whether a computed graph delta exactly matches mutation-oracle
    ground truth.

    Exact matching is intentional for controlled mutation experiments.
    """

    expected_added_node_ids = frozenset(
        node.id
        for node in expected.added_nodes
    )

    expected_removed_node_ids = frozenset(
        node.id
        for node in expected.removed_nodes
    )

    return (
        computed.added_node_ids
        == expected_added_node_ids
        and computed.removed_node_ids
        == expected_removed_node_ids
        and computed.added_relation_identities
        == expected.added_relation_identities
        and computed.removed_relation_identities
        == expected.removed_relation_identities
    )