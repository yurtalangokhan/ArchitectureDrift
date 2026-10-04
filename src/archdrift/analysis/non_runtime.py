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
        canonicalize_observation(
            observation
        )
        for observation in scoped.included
    )

    reconstruction = (
        reconstruct_observed_graph(
            system_id=system_id,
            candidates=candidates,
            mode=(
                ReconstructionMode.NON_RUNTIME
            ),
            revision=revision,
        )
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
        observations=(
            deployment_observations
        ),
        scope=scope,
        revision=revision,
    )

    source_static = _reconstruct_view(
        system_id=system_id,
        observations=(
            source_static_observations
        ),
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