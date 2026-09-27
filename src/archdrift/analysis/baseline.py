from __future__ import annotations

from dataclasses import dataclass

from archdrift.analysis.coverage import (
    BaselineCoverageMetrics,
    evaluate_baseline_coverage,
)
from archdrift.analysis.fusion import (
    ReconstructionResult,
    reconstruct_observed_graph,
)
from archdrift.analysis.normalize import (
    CanonicalCandidate,
    canonicalize_observation,
)
from archdrift.analysis.scope import (
    EvidenceScope,
    ScopedObservationSet,
    apply_evidence_scope,
)
from archdrift.model.graph import (
    ArchitectureGraph,
    GraphRole,
    ReconstructionMode,
)
from archdrift.model.observation import (
    NormalizedObservation,
)


class BaselineAnalysisError(ValueError):
    """Raised when baseline reconstruction inputs violate analysis invariants."""


@dataclass(
    frozen=True,
    slots=True,
)
class BaselineReconstructionAnalysis:
    """
    Result of reconstructing a baseline architecture from real evidence.

    The result deliberately preserves three distinct concepts:

    - scoped: evidence admitted by the experiment boundary;
    - reconstruction: architecture inferred from admitted evidence;
    - coverage: comparison against independently curated baseline ground truth.
    """

    scoped: ScopedObservationSet

    candidates: tuple[
        CanonicalCandidate,
        ...,
    ]

    reconstruction: ReconstructionResult

    coverage: BaselineCoverageMetrics


def analyze_baseline_reconstruction(
    *,
    baseline: ArchitectureGraph,
    observations: tuple[
        NormalizedObservation,
        ...,
    ],
    scope: EvidenceScope,
    revision: str | None = None,
) -> BaselineReconstructionAnalysis:
    """
    Reconstruct a NON_RUNTIME architecture graph and measure baseline coverage.

    This function performs no evidence extraction. Adapters remain responsible
    for producing NormalizedObservation instances.

    Processing pipeline:

        normalized observations
            -> explicit experiment scope
            -> canonical candidates
            -> NON_RUNTIME reconstruction
            -> baseline coverage

    Baseline absence is interpreted as NOT_OBSERVED, never as removal.
    """

    if baseline.metadata.role is not GraphRole.BASELINE:
        raise BaselineAnalysisError(
            "Baseline reconstruction requires a graph with role BASELINE."
        )

    scoped = apply_evidence_scope(
        observations,
        scope=scope,
    )

    candidates = tuple(
        canonicalize_observation(
            observation
        )
        for observation in scoped.included
    )

    reconstruction = reconstruct_observed_graph(
        system_id=baseline.metadata.system_id,
        candidates=candidates,
        mode=ReconstructionMode.NON_RUNTIME,
        revision=revision,
    )

    coverage = evaluate_baseline_coverage(
        baseline=baseline,
        observed=reconstruction.graph,
    )

    return BaselineReconstructionAnalysis(
        scoped=scoped,
        candidates=candidates,
        reconstruction=reconstruction,
        coverage=coverage,
    )