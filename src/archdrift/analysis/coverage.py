from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from archdrift.model.graph import (
    ArchitectureGraph,
    RelationIdentity,
)


class BaselineCoverageMetrics(BaseModel):
    """
    Coverage of a ground-truth baseline architecture by an observed graph.

    This is presence-based coverage.

    A baseline element absent from the observed graph is classified as
    not observed, not removed.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    baseline_node_count: int = Field(
        ge=0,
    )

    observed_baseline_node_count: int = Field(
        ge=0,
    )

    baseline_relation_count: int = Field(
        ge=0,
    )

    observed_baseline_relation_count: int = Field(
        ge=0,
    )

    unexpected_node_ids: frozenset[str]

    not_observed_node_ids: frozenset[str]

    unexpected_relation_identities: frozenset[
        RelationIdentity
    ]

    not_observed_relation_identities: frozenset[
        RelationIdentity
    ]

    @property
    def node_coverage(
        self,
    ) -> float | None:
        if self.baseline_node_count == 0:
            return None

        return (
            self.observed_baseline_node_count
            / self.baseline_node_count
        )

    @property
    def relation_coverage(
        self,
    ) -> float | None:
        if self.baseline_relation_count == 0:
            return None

        return (
            self.observed_baseline_relation_count
            / self.baseline_relation_count
        )


def evaluate_baseline_coverage(
    *,
    baseline: ArchitectureGraph,
    observed: ArchitectureGraph,
) -> BaselineCoverageMetrics:
    """
    Measure how much of a baseline architecture is present in an
    evidence-reconstructed graph.

    Absence is intentionally represented as NOT_OBSERVED rather than
    structural removal.
    """

    if (
        baseline.metadata.system_id
        != observed.metadata.system_id
    ):
        raise ValueError(
            "Baseline and observed graphs must belong "
            "to the same system."
        )

    baseline_nodes = set(
        baseline.node_ids
    )

    observed_nodes = set(
        observed.node_ids
    )

    baseline_relations = set(
        baseline.relation_identities
    )

    observed_relations = set(
        observed.relation_identities
    )

    observed_baseline_nodes = (
        baseline_nodes
        & observed_nodes
    )

    observed_baseline_relations = (
        baseline_relations
        & observed_relations
    )

    return BaselineCoverageMetrics(
        baseline_node_count=len(
            baseline_nodes
        ),
        observed_baseline_node_count=len(
            observed_baseline_nodes
        ),
        baseline_relation_count=len(
            baseline_relations
        ),
        observed_baseline_relation_count=len(
            observed_baseline_relations
        ),
        unexpected_node_ids=frozenset(
            observed_nodes
            - baseline_nodes
        ),
        not_observed_node_ids=frozenset(
            baseline_nodes
            - observed_nodes
        ),
        unexpected_relation_identities=frozenset(
            observed_relations
            - baseline_relations
        ),
        not_observed_relation_identities=frozenset(
            baseline_relations
            - observed_relations
        ),
    )