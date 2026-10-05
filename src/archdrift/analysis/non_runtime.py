from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
)

from archdrift.analysis.fusion import (
    ReconstructionResult,
    reconstruct_observed_graph,
)
from archdrift.analysis.normalize import (
    canonicalize_observation,
)
from archdrift.analysis.scope import (
    EvidenceScope,
    ScopedObservationSet,
    apply_evidence_scope,
)
from archdrift.model.graph import (
    ReconstructionMode,
)
from archdrift.model.observation import (
    NormalizedObservation,
)


class NonRuntimeEvidenceView(BaseModel):
    """
    One scoped non-runtime evidence view and its reconstructed graph.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    scoped: ScopedObservationSet

    reconstruction: ReconstructionResult


class NonRuntimeEvidenceViews(BaseModel):
    """
    Ablation views inside the NON_RUNTIME evidence channel.

    deployment:
        Deployment/configuration evidence only.

    source_static:
        Source-static evidence only.

    combined:
        Union of both non-runtime evidence families.

    These are not the experiment-level NON_RUNTIME/RUNTIME/FUSED views.
    All three remain NON_RUNTIME reconstructions.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    deployment: NonRuntimeEvidenceView

    source_static: NonRuntimeEvidenceView

    combined: NonRuntimeEvidenceView


def _reconstruct_view(
    *,
    system_id: str,
    observations: tuple[
        NormalizedObservation,
        ...,
    ],
    scope: EvidenceScope,
    revision: str | None,
) -> NonRuntimeEvidenceView:
    scoped = apply_evidence_scope(
        observations,
        scope=scope,
    )

    candidates = tuple(
        canonicalize_observation(observation) for observation in scoped.included
    )

    reconstruction = reconstruct_observed_graph(
        system_id=system_id,
        candidates=candidates,
        mode=(ReconstructionMode.NON_RUNTIME),
        revision=revision,
    )

    return NonRuntimeEvidenceView(
        scoped=scoped,
        reconstruction=reconstruction,
    )


def reconstruct_non_runtime_views(
    *,
    system_id: str,
    deployment_observations: tuple[
        NormalizedObservation,
        ...,
    ],
    source_static_observations: tuple[
        NormalizedObservation,
        ...,
    ],
    scope: EvidenceScope,
    revision: str | None = None,
) -> NonRuntimeEvidenceViews:
    """
    Build deployment-only, source-static-only and combined
    non-runtime architecture reconstructions.
    """

    deployment = _reconstruct_view(
        system_id=system_id,
        observations=(deployment_observations),
        scope=scope,
        revision=revision,
    )

    source_static = _reconstruct_view(
        system_id=system_id,
        observations=(source_static_observations),
        scope=scope,
        revision=revision,
    )

    combined = _reconstruct_view(
        system_id=system_id,
        observations=(
            *deployment_observations,
            *source_static_observations,
        ),
        scope=scope,
        revision=revision,
    )

    return NonRuntimeEvidenceViews(
        deployment=deployment,
        source_static=source_static,
        combined=combined,
    )


class NonRuntimeComplementarityMetrics(BaseModel):
    """
    Relation-level complementarity between deployment/configuration
    and source-static evidence inside the NON_RUNTIME channel.

    These metrics describe evidence-family overlap and structural gain.
    They do not measure accuracy against architecture ground truth.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    deployment_relation_count: int

    source_static_relation_count: int

    combined_relation_count: int

    overlap_relation_count: int

    deployment_only_relation_count: int

    source_static_only_relation_count: int

    deployment_corroboration_rate: float | None

    source_static_corroboration_rate: float | None

    structural_gain_over_deployment_count: int

    structural_gain_over_deployment_rate: float | None


def analyze_non_runtime_complementarity(
    views: NonRuntimeEvidenceViews,
) -> NonRuntimeComplementarityMetrics:
    deployment = views.deployment.reconstruction.graph.relation_identities

    source_static = views.source_static.reconstruction.graph.relation_identities

    combined = views.combined.reconstruction.graph.relation_identities

    expected_combined = deployment | source_static

    if combined != expected_combined:
        raise ValueError(
            "Combined non-runtime relation set "
            "must equal the union of deployment "
            "and source-static relation sets."
        )

    overlap = deployment & source_static

    deployment_only = deployment - source_static

    source_static_only = source_static - deployment

    gain_count = len(source_static_only)

    return NonRuntimeComplementarityMetrics(
        deployment_relation_count=(len(deployment)),
        source_static_relation_count=(len(source_static)),
        combined_relation_count=(len(combined)),
        overlap_relation_count=(len(overlap)),
        deployment_only_relation_count=(len(deployment_only)),
        source_static_only_relation_count=(len(source_static_only)),
        deployment_corroboration_rate=(
            (len(overlap) / len(deployment)) if deployment else None
        ),
        source_static_corroboration_rate=(
            (len(overlap) / len(source_static)) if source_static else None
        ),
        structural_gain_over_deployment_count=(gain_count),
        structural_gain_over_deployment_rate=(
            (gain_count / len(deployment)) if deployment else None
        ),
    )
