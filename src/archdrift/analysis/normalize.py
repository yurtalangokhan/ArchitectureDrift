from __future__ import annotations

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)

from archdrift.model.evidence import (
    EvidenceChannel,
    EvidenceRecord,
    deduplicate_evidence,
)
from archdrift.model.graph import (
    ArchitectureNode,
    ArchitectureRelation,
    RelationIdentity,
    RelationType,
)
from archdrift.model.observation import (
    InteractionType,
    NormalizedNodeObservation,
    NormalizedObservation,
    NormalizedRelationObservation,
)

INTERACTION_TO_RELATION: dict[
    InteractionType,
    RelationType,
] = {
    InteractionType.SERVICE_CALL: RelationType.CALLS,
    InteractionType.DATA_READ: RelationType.READS_FROM,
    InteractionType.DATA_WRITE: RelationType.WRITES_TO,
    InteractionType.MESSAGE_PUBLISH: RelationType.PUBLISHES_TO,
    InteractionType.MESSAGE_SUBSCRIBE: RelationType.SUBSCRIBES_TO,
    InteractionType.ROUTE: RelationType.ROUTES_TO,
    InteractionType.DISCOVERY: RelationType.DISCOVERS_VIA,
    InteractionType.EXPOSURE: RelationType.EXPOSES_TO,
}


def _normalize_candidate_evidence(
    evidence: tuple[EvidenceRecord, ...],
) -> tuple[EvidenceRecord, ...]:
    if not evidence:
        raise ValueError(
            "Canonical candidate requires at least one evidence record."
        )

    normalized = deduplicate_evidence(
        evidence
    )

    channels = {
        record.channel
        for record in normalized
    }

    if len(channels) != 1:
        raise ValueError(
            "Canonical candidate cannot combine multiple evidence channels."
        )

    return normalized


def _evidence_channel(
    evidence: tuple[EvidenceRecord, ...],
) -> EvidenceChannel:
    return evidence[0].channel


class CanonicalNodeCandidate(BaseModel):
    """Evidence-backed candidate for one canonical node."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    node: ArchitectureNode

    evidence: tuple[
        EvidenceRecord,
        ...,
    ]

    @field_validator("evidence")
    @classmethod
    def validate_evidence(
        cls,
        value: tuple[EvidenceRecord, ...],
    ) -> tuple[EvidenceRecord, ...]:
        return _normalize_candidate_evidence(
            value
        )

    @property
    def channel(self) -> EvidenceChannel:
        return _evidence_channel(
            self.evidence
        )

    @property
    def identity(self) -> str:
        return self.node.id


class CanonicalRelationCandidate(BaseModel):
    """Evidence-backed candidate for one canonical relation."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    source_node: ArchitectureNode
    target_node: ArchitectureNode

    relation: ArchitectureRelation

    protocol: str | None = None

    evidence: tuple[
        EvidenceRecord,
        ...,
    ]

    @field_validator("evidence")
    @classmethod
    def validate_evidence(
        cls,
        value: tuple[EvidenceRecord, ...],
    ) -> tuple[EvidenceRecord, ...]:
        return _normalize_candidate_evidence(
            value
        )

    @model_validator(mode="after")
    def validate_relation_endpoints(
        self,
    ) -> Self:
        if (
            self.relation.source
            != self.source_node.id
        ):
            raise ValueError(
                "Canonical relation source does not match source_node."
            )

        if (
            self.relation.target
            != self.target_node.id
        ):
            raise ValueError(
                "Canonical relation target does not match target_node."
            )

        return self

    @property
    def channel(self) -> EvidenceChannel:
        return _evidence_channel(
            self.evidence
        )

    @property
    def identity(
        self,
    ) -> RelationIdentity:
        return self.relation.identity


CanonicalCandidate = (
    CanonicalNodeCandidate
    | CanonicalRelationCandidate
)


def canonicalize_node_observation(
    observation: NormalizedNodeObservation,
) -> CanonicalNodeCandidate:
    return CanonicalNodeCandidate(
        node=observation.endpoint.to_architecture_node(),
        evidence=observation.evidence,
    )


def canonicalize_relation_observation(
    observation: NormalizedRelationObservation,
) -> CanonicalRelationCandidate:
    source_node = (
        observation.source.to_architecture_node()
    )

    target_node = (
        observation.target.to_architecture_node()
    )

    relation = ArchitectureRelation(
        source=source_node.id,
        relation=INTERACTION_TO_RELATION[
            observation.interaction
        ],
        target=target_node.id,
    )

    return CanonicalRelationCandidate(
        source_node=source_node,
        target_node=target_node,
        relation=relation,
        protocol=observation.protocol,
        evidence=observation.evidence,
    )


def canonicalize_observation(
    observation: NormalizedObservation,
) -> CanonicalCandidate:
    if isinstance(
        observation,
        NormalizedNodeObservation,
    ):
        return canonicalize_node_observation(
            observation
        )

    if isinstance(
        observation,
        NormalizedRelationObservation,
    ):
        return canonicalize_relation_observation(
            observation
        )

    raise TypeError(
        f"Unsupported normalized observation: {type(observation)!r}"
    )