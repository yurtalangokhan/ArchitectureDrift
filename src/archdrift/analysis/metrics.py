from __future__ import annotations

from collections.abc import Hashable, Set
from typing import TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from archdrift.analysis.conformance import (
    ConformanceReport,
    ConformanceStatus,
)
from archdrift.analysis.fusion import (
    EvidenceGraphViews,
)
from archdrift.analysis.graph_delta import (
    GraphDelta,
    compute_graph_delta,
)
from archdrift.model.graph import (
    ArchitectureGraph,
    RelationIdentity,
)
from archdrift.model.mutation import (
    ExpectedGraphDelta,
    MutationOracle,
)

_Item = TypeVar(
    "_Item",
    bound=Hashable,
)


# =============================================================================
# Exceptions
# =============================================================================


class MetricsError(ValueError):
    """Base exception for experiment metric calculation."""


class MetricsConsistencyError(MetricsError):
    """Raised when metric inputs are mutually inconsistent."""


# =============================================================================
# Shared Helpers
# =============================================================================


def _ratio(
    numerator: int,
    denominator: int,
) -> float | None:
    """
    Return a ratio or None when the metric is mathematically undefined.

    Undefined metrics are kept explicit rather than silently replaced with
    zero.
    """

    if denominator == 0:
        return None

    return numerator / denominator


# =============================================================================
# Open-World Set Detection Metrics
# =============================================================================


class SetDetectionMetrics(BaseModel):
    """
    Detection metrics for a finite expected-positive set and predicted set.

    No true-negative count is defined because the negative universe is not
    known.

    This model is suitable for canonical graph-delta elements.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    true_positive: int = Field(ge=0)

    false_positive: int = Field(ge=0)

    false_negative: int = Field(ge=0)

    @property
    def expected_positive_count(
        self,
    ) -> int:
        return self.true_positive + self.false_negative

    @property
    def predicted_positive_count(
        self,
    ) -> int:
        return self.true_positive + self.false_positive

    @property
    def precision(
        self,
    ) -> float | None:
        return _ratio(
            self.true_positive,
            self.predicted_positive_count,
        )

    @property
    def recall(
        self,
    ) -> float | None:
        return _ratio(
            self.true_positive,
            self.expected_positive_count,
        )

    @property
    def f1(
        self,
    ) -> float | None:
        precision = self.precision
        recall = self.recall

        if precision is None or recall is None:
            return None

        denominator = precision + recall

        if denominator == 0:
            return 0.0

        return 2 * precision * recall / denominator


def compute_set_detection_metrics(
    *,
    expected: Set[_Item],
    predicted: Set[_Item],
) -> SetDetectionMetrics:
    """
    Compare an expected-positive set with a predicted-positive set.
    """

    true_positive = expected & predicted

    false_positive = predicted - expected

    false_negative = expected - predicted

    return SetDetectionMetrics(
        true_positive=len(true_positive),
        false_positive=len(false_positive),
        false_negative=len(false_negative),
    )


# =============================================================================
# Structural Mutation Detection
# =============================================================================


class StructuralDetectionMetrics(BaseModel):
   
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    raw_graph_delta: GraphDelta

    added_nodes: SetDetectionMetrics
    removed_nodes: SetDetectionMetrics

    added_relations: SetDetectionMetrics
    removed_relations: SetDetectionMetrics

    overall: SetDetectionMetrics

    removal_inference_enabled: bool = False

    @property
    def predicted_delta(
        self,
    ) -> GraphDelta:
        """
        Backward-compatible alias.

        The graph delta is diagnostic only. Under open-world evidence,
        raw removals are not automatically treated as detected removals.
        """

        return self.raw_graph_delta


def _combine_detection_metrics(
    *metrics: SetDetectionMetrics,
) -> SetDetectionMetrics:
    return SetDetectionMetrics(
        true_positive=sum(metric.true_positive for metric in metrics),
        false_positive=sum(metric.false_positive for metric in metrics),
        false_negative=sum(metric.false_negative for metric in metrics),
    )


def evaluate_structural_detection(
    *,
    baseline: ArchitectureGraph,
    observed: ArchitectureGraph,
    expected: ExpectedGraphDelta,
    infer_removals: bool = False,
) -> StructuralDetectionMetrics:
    """
    Evaluate structural mutation detection against the mutation oracle.

    The reconstructed architecture is treated as open-world evidence.

    Semantics:
    - An observed element that is absent from the baseline can support an
      addition detection.
    - A baseline element that is absent from the observed graph does not,
      by itself, prove that the element was removed.
    - Removal inference is therefore disabled by default and must be
      explicitly enabled only when the evidence source provides sufficient
      completeness guarantees.

    The raw baseline-to-observed graph delta is retained for diagnostics,
    independently from the detection semantics.
    """

    if baseline.metadata.system_id != observed.metadata.system_id:
        raise MetricsConsistencyError(
            "Baseline and observed graphs must belong to the same system: "
            f"{baseline.metadata.system_id!r} != "
            f"{observed.metadata.system_id!r}"
        )

    # -------------------------------------------------------------------------
    # Diagnostic graph delta
    # -------------------------------------------------------------------------

    raw_graph_delta = compute_graph_delta(
        baseline,
        observed,
    )

    # -------------------------------------------------------------------------
    # Added nodes
    # -------------------------------------------------------------------------

    expected_added_node_ids = {node.id for node in expected.added_nodes}

    predicted_added_node_ids = set(observed.node_ids - baseline.node_ids)

    added_nodes = compute_set_detection_metrics(
        expected=expected_added_node_ids,
        predicted=predicted_added_node_ids,
    )

    # -------------------------------------------------------------------------
    # Removed nodes
    # -------------------------------------------------------------------------

    expected_removed_node_ids = {node.id for node in expected.removed_nodes}

    predicted_removed_node_ids: set[str]

    if infer_removals:
        predicted_removed_node_ids = set(raw_graph_delta.removed_node_ids)
    else:
        predicted_removed_node_ids = set()

    removed_nodes = compute_set_detection_metrics(
        expected=expected_removed_node_ids,
        predicted=predicted_removed_node_ids,
    )

    # -------------------------------------------------------------------------
    # Added relations
    # -------------------------------------------------------------------------

    expected_added_relation_ids = set(expected.added_relation_identities)

    predicted_added_relation_ids: set[RelationIdentity] = set(
        observed.relation_identities - baseline.relation_identities
    )

    added_relations = compute_set_detection_metrics(
        expected=expected_added_relation_ids,
        predicted=predicted_added_relation_ids,
    )

    # -------------------------------------------------------------------------
    # Removed relations
    # -------------------------------------------------------------------------

    expected_removed_relation_ids = set(expected.removed_relation_identities)

    predicted_removed_relation_ids: set[RelationIdentity]

    if infer_removals:
        predicted_removed_relation_ids = set(
            raw_graph_delta.removed_relation_identities
        )
    else:
        predicted_removed_relation_ids = set()

    removed_relations = compute_set_detection_metrics(
        expected=expected_removed_relation_ids,
        predicted=predicted_removed_relation_ids,
    )

    # -------------------------------------------------------------------------
    # Aggregate
    # -------------------------------------------------------------------------

    overall = _combine_detection_metrics(
        added_nodes,
        removed_nodes,
        added_relations,
        removed_relations,
    )

    return StructuralDetectionMetrics(
        raw_graph_delta=raw_graph_delta,
        added_nodes=added_nodes,
        removed_nodes=removed_nodes,
        added_relations=added_relations,
        removed_relations=removed_relations,
        overall=overall,
        removal_inference_enabled=infer_removals,
    )


# =============================================================================
# Contract Violation Detection
# =============================================================================


class ContractViolationMetrics(BaseModel):
    """
    Confusion-matrix metrics over a finite architecture-contract set.

    A ground-truth positive is a contract expected to be violated.

    NOT_EVALUABLE handling:

    - expected violation + NOT_EVALUABLE -> false negative;
    - expected non-violation + NOT_EVALUABLE -> tracked separately rather
      than incorrectly counted as a true negative.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    true_positive: int = Field(ge=0)

    false_positive: int = Field(ge=0)

    false_negative: int = Field(ge=0)

    true_negative: int = Field(ge=0)

    not_evaluable_positive: int = Field(
        default=0,
        ge=0,
    )

    not_evaluable_negative: int = Field(
        default=0,
        ge=0,
    )

    @model_validator(mode="after")
    def validate_counts(
        self,
    ) -> ContractViolationMetrics:
        if self.not_evaluable_positive > self.false_negative:
            raise ValueError("not_evaluable_positive cannot exceed false_negative.")

        return self

    @property
    def total_contracts(
        self,
    ) -> int:
        # not_evaluable_positive is already included in false_negative.
        return (
            self.true_positive
            + self.false_positive
            + self.false_negative
            + self.true_negative
            + self.not_evaluable_negative
        )

    @property
    def evaluable_contracts(
        self,
    ) -> int:
        return (
            self.total_contracts
            - self.not_evaluable_positive
            - self.not_evaluable_negative
        )

    @property
    def precision(
        self,
    ) -> float | None:
        return _ratio(
            self.true_positive,
            self.true_positive + self.false_positive,
        )

    @property
    def recall(
        self,
    ) -> float | None:
        return _ratio(
            self.true_positive,
            self.true_positive + self.false_negative,
        )

    @property
    def f1(
        self,
    ) -> float | None:
        precision = self.precision
        recall = self.recall

        if precision is None or recall is None:
            return None

        denominator = precision + recall

        if denominator == 0:
            return 0.0

        return 2 * precision * recall / denominator

    @property
    def evaluability_rate(
        self,
    ) -> float | None:
        return _ratio(
            self.evaluable_contracts,
            self.total_contracts,
        )


def evaluate_contract_violation_detection(
    *,
    report: ConformanceReport,
    expected_violations: Set[str],
) -> ContractViolationMetrics:
    """
    Compare detected contract violations against finite ground truth.
    """

    report_contract_ids = {evaluation.contract_id for evaluation in report.evaluations}

    unknown_expected = expected_violations - report_contract_ids

    if unknown_expected:
        raise MetricsConsistencyError(
            "Expected violated contracts are absent from "
            "the conformance report: " + ", ".join(sorted(unknown_expected))
        )

    true_positive = 0
    false_positive = 0
    false_negative = 0
    true_negative = 0

    not_evaluable_positive = 0
    not_evaluable_negative = 0

    for evaluation in report.evaluations:
        expected_positive = evaluation.contract_id in expected_violations

        if expected_positive:
            if evaluation.status is ConformanceStatus.VIOLATED:
                true_positive += 1

            else:
                false_negative += 1

                if evaluation.status is ConformanceStatus.NOT_EVALUABLE:
                    not_evaluable_positive += 1

            continue

        if evaluation.status is ConformanceStatus.VIOLATED:
            false_positive += 1

        elif evaluation.status is ConformanceStatus.SATISFIED:
            true_negative += 1

        else:
            not_evaluable_negative += 1

    return ContractViolationMetrics(
        true_positive=true_positive,
        false_positive=false_positive,
        false_negative=false_negative,
        true_negative=true_negative,
        not_evaluable_positive=not_evaluable_positive,
        not_evaluable_negative=not_evaluable_negative,
    )


# =============================================================================
# Per-View Metrics
# =============================================================================


class EvidenceViewMetrics(BaseModel):
    """Metrics for one evidence reconstruction configuration."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    structural: StructuralDetectionMetrics

    contract_violations: ContractViolationMetrics


class ExperimentMetrics(BaseModel):
    """
    Metrics for the three evidence configurations compared by the experiment.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    non_runtime: EvidenceViewMetrics

    runtime: EvidenceViewMetrics

    fused: EvidenceViewMetrics


def compute_experiment_metrics(
    *,
    baseline: ArchitectureGraph,
    views: EvidenceGraphViews,
    non_runtime_report: ConformanceReport,
    runtime_report: ConformanceReport,
    fused_report: ConformanceReport,
    oracle: MutationOracle,
) -> ExperimentMetrics:
    """
    Compute comparable metrics for Non-Runtime, Runtime, and Fused evidence.
    """

    expected_violations = set(oracle.expected_violated_contracts)

    def evaluate_view(
        *,
        observed: ArchitectureGraph,
        report: ConformanceReport,
    ) -> EvidenceViewMetrics:
        return EvidenceViewMetrics(
            structural=(
                evaluate_structural_detection(
                    baseline=baseline,
                    observed=observed,
                    expected=oracle.expected_delta,
                )
            ),
            contract_violations=(
                evaluate_contract_violation_detection(
                    report=report,
                    expected_violations=expected_violations,
                )
            ),
        )

    return ExperimentMetrics(
        non_runtime=evaluate_view(
            observed=views.non_runtime.graph,
            report=non_runtime_report,
        ),
        runtime=evaluate_view(
            observed=views.runtime.graph,
            report=runtime_report,
        ),
        fused=evaluate_view(
            observed=views.fused.graph,
            report=fused_report,
        ),
    )
