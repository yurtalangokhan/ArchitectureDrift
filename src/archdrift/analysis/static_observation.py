from __future__ import annotations

from archdrift.model.evidence import (
    EvidenceRecord,
    EvidenceType,
)
from archdrift.model.observation import (
    NormalizedEndpoint,
    NormalizedRelationObservation,
)
from archdrift.model.source_static import (
    ResolvedStaticInteraction,
)


def static_interactions_to_observations(
    interactions: tuple[
        ResolvedStaticInteraction,
        ...,
    ],
) -> tuple[
    NormalizedRelationObservation,
    ...,
]:
    """
    Convert resolved source-static interactions into normalized
    architecture relation observations.

    Resolution has already established the canonical source and target.
    This function only materializes observations and preserves provenance.
    """

    observations: list[NormalizedRelationObservation] = []

    for interaction in interactions:
        finding = interaction.finding

        locator_parts = [
            f"line:{finding.line}",
            f"rule:{finding.rule_id}",
            ("resolution:" f"{interaction.resolution_basis.value}"),
        ]

        if interaction.environment_key is not None:
            locator_parts.append("env:" f"{interaction.environment_key}")

        evidence = EvidenceRecord(
            type=EvidenceType.SOURCE_CODE,
            artifact=finding.path,
            locator=";".join(locator_parts),
        )

        observations.append(
            NormalizedRelationObservation(
                source=NormalizedEndpoint(
                    id=interaction.source_service_id,
                    type=interaction.source_type,
                ),
                target=NormalizedEndpoint(
                    id=interaction.target_service_id,
                    type=interaction.target_type,
                ),
                interaction=finding.interaction,
                protocol=finding.protocol,
                evidence=(evidence,),
            )
        )

    return tuple(observations)
