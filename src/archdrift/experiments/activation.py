from __future__ import annotations

from archdrift.model.graph import (
    ArchitectureGraph,
    ArchitectureGraphError,
    GraphMetadata,
    GraphRole,
)
from archdrift.model.mutation import (
    AddNodeOperation,
    AddRelationOperation,
    MutationOracle,
    RemoveNodeOperation,
    RemoveRelationOperation,
)


class MutationActivationError(ValueError):
    """Raised when a controlled mutation cannot be applied safely."""


def apply_mutation(
    baseline: ArchitectureGraph,
    oracle: MutationOracle,
) -> ArchitectureGraph:
    """
    Apply a controlled mutation oracle to a baseline graph.

    Mutation operations are interpreted declaratively rather than as an
    arbitrary execution sequence.

    Execution phases:

        1. REMOVE_RELATION
        2. REMOVE_NODE
        3. ADD_NODE
        4. ADD_RELATION

    This ordering prevents newly added relations from referencing nodes that
    do not yet exist and allows explicit relation removals before node
    removal.

    The input baseline graph is immutable and remains unchanged.
    """

    if baseline.metadata.role is not GraphRole.BASELINE:
        raise MutationActivationError(
            "Mutation activation requires a BASELINE graph."
        )

    if (
        baseline.metadata.system_id
        != oracle.system_id
    ):
        raise MutationActivationError(
            "Baseline graph and mutation oracle belong to "
            "different systems: "
            f"{baseline.metadata.system_id!r} != "
            f"{oracle.system_id!r}"
        )

    graph = baseline

    try:
        # ---------------------------------------------------------------------
        # Phase 1: Remove relations
        # ---------------------------------------------------------------------

        for operation in oracle.operations:
            if not isinstance(
                operation,
                RemoveRelationOperation,
            ):
                continue

            graph = graph.without_relation(
                source=operation.relation.source,
                relation=operation.relation.relation,
                target=operation.relation.target,
            )

        # ---------------------------------------------------------------------
        # Phase 2: Remove nodes
        # ---------------------------------------------------------------------

        for operation in oracle.operations:
            if not isinstance(
                operation,
                RemoveNodeOperation,
            ):
                continue

            existing = graph.require_node(
                operation.node.id
            )

            if existing.type is not operation.node.type:
                raise MutationActivationError(
                    "REMOVE_NODE type does not match baseline node: "
                    f"{operation.node.id!r}: "
                    f"{existing.type.value} != "
                    f"{operation.node.type.value}"
                )

            graph = graph.without_node(
                operation.node.id
            )

        # ---------------------------------------------------------------------
        # Phase 3: Add nodes
        # ---------------------------------------------------------------------

        for operation in oracle.operations:
            if not isinstance(
                operation,
                AddNodeOperation,
            ):
                continue

            graph = graph.with_node(
                operation.node
            )

        # ---------------------------------------------------------------------
        # Phase 4: Add relations
        # ---------------------------------------------------------------------

        for operation in oracle.operations:
            if not isinstance(
                operation,
                AddRelationOperation,
            ):
                continue

            graph = graph.with_relation(
                operation.relation
            )

    except ArchitectureGraphError as exc:
        raise MutationActivationError(
            f"Mutation {oracle.mutation_id!r} could not be applied: {exc}"
        ) from exc

    return ArchitectureGraph(
        schema_version=graph.schema_version,
        metadata=GraphMetadata(
            system_id=baseline.metadata.system_id,
            role=GraphRole.MUTANT,
            variant=oracle.mutation_id,
            revision=baseline.metadata.revision,
        ),
        nodes=graph.nodes,
        relations=graph.relations,
    )