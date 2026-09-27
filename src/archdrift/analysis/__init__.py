from archdrift.analysis.baseline import (
    BaselineAnalysisError,
    BaselineReconstructionAnalysis,
    analyze_baseline_reconstruction,
)
from archdrift.analysis.conformance import (
    ConformanceError,
    ConformanceEvaluationError,
    ConformanceReport,
    ConformanceStatus,
    ContractEvaluation,
    evaluate_contract,
    evaluate_contract_document,
)
from archdrift.analysis.fusion import (
    CandidateConflictError,
    EvidenceGraphViews,
    FusionError,
    NodeSupport,
    ReconstructionResult,
    RelationSupport,
    build_evidence_graph_views,
    reconstruct_observed_graph,
)
from archdrift.analysis.graph_delta import (
    GraphComparisonError,
    GraphDelta,
    GraphDeltaError,
    compute_baseline_mutant_delta,
    compute_graph_delta,
    matches_expected_delta,
)
from archdrift.analysis.metrics import (
    ContractViolationMetrics,
    EvidenceViewMetrics,
    ExperimentMetrics,
    MetricsConsistencyError,
    MetricsError,
    SetDetectionMetrics,
    StructuralDetectionMetrics,
    compute_experiment_metrics,
    compute_set_detection_metrics,
    evaluate_contract_violation_detection,
    evaluate_structural_detection,
)
from archdrift.analysis.normalize import (
    INTERACTION_TO_RELATION,
    CanonicalCandidate,
    CanonicalNodeCandidate,
    CanonicalRelationCandidate,
    canonicalize_node_observation,
    canonicalize_observation,
    canonicalize_relation_observation,
)
from archdrift.analysis.scope import (
    EvidenceScope,
    EvidenceScopeError,
    ExcludedObservation,
    ScopedObservationSet,
    ScopeExclusionReason,
    apply_evidence_scope,
)
from archdrift.analysis.static_observation import (
    static_interactions_to_observations,
)

__all__ = [
    # Graph delta
    "GraphComparisonError",
    "GraphDelta",
    "GraphDeltaError",
    "compute_baseline_mutant_delta",
    "compute_graph_delta",
    "matches_expected_delta",
    # Conformance
    "ConformanceError",
    "ConformanceEvaluationError",
    "ConformanceReport",
    "ConformanceStatus",
    "ContractEvaluation",
    "evaluate_contract",
    "evaluate_contract_document",
    # Normalization
    "INTERACTION_TO_RELATION",
    "CanonicalCandidate",
    "CanonicalNodeCandidate",
    "CanonicalRelationCandidate",
    "canonicalize_node_observation",
    "canonicalize_observation",
    "canonicalize_relation_observation",
    # Fusion
    "CandidateConflictError",
    "EvidenceGraphViews",
    "FusionError",
    "NodeSupport",
    "ReconstructionResult",
    "RelationSupport",
    "build_evidence_graph_views",
    "reconstruct_observed_graph",
    # Metrics
    "ContractViolationMetrics",
    "EvidenceViewMetrics",
    "ExperimentMetrics",
    "MetricsConsistencyError",
    "MetricsError",
    "SetDetectionMetrics",
    "StructuralDetectionMetrics",
    "compute_experiment_metrics",
    "compute_set_detection_metrics",
    "evaluate_contract_violation_detection",
    "evaluate_structural_detection",
    # Scope
    "EvidenceScope",
    "EvidenceScopeError",
    "ExcludedObservation",
    "ScopeExclusionReason",
    "ScopedObservationSet",
    "apply_evidence_scope",
    # Baseline
    "BaselineAnalysisError",
    "BaselineReconstructionAnalysis",
    "analyze_baseline_reconstruction",
    # Static observation
    "static_interactions_to_observations",
]
