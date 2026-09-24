from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from archdrift.model._validation import (
    normalize_identifier,
    normalize_optional_text,
)
from archdrift.model.evidence import (
    EvidenceChannel,
    EvidenceRecord,
    deduplicate_evidence,
)
from archdrift.model.graph import (
    ArchitectureNode,
    NodeType,
)


class ObservationKind(StrEnum):
    """Supported normalized observation kinds."""

    NODE = "NODE"
    RELATION = "RELATION"


class InteractionType(StrEnum):
    """
    Technology-independent interaction semantics.

    These are normalized evidence semantics, not canonical graph relations.
    """

    SERVICE_CALL = "SERVICE_CALL"

    DATA_READ = "DATA_READ"
    DATA_WRITE = "DATA_WRITE"

    MESSAGE_PUBLISH = "MESSAGE_PUBLISH"
    MESSAGE_SUBSCRIBE = "MESSAGE_SUBSCRIBE"

    ROUTE = "ROUTE"
    DISCOVERY = "DISCOVERY"
    EXPOSURE = "EXPOSURE"


def _normalize_evidence(
    evidence: tuple[EvidenceRecord, ...],
) -> tuple[EvidenceRecord, ...]:
    if not evidence:
        raise ValueError(
            "Normalized observation requires at least one evidence record."
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
            "Normalized observation cannot combine multiple evidence "
            "channels. Cross-channel aggregation belongs to evidence fusion."
        )

    return normalized


def _evidence_channel(
    evidence: tuple[EvidenceRecord, ...],
) -> EvidenceChannel:
    return evidence[0].channel


class NormalizedEndpoint(BaseModel):
    """
    Technology-independent architecture endpoint resolved by an adapter.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    id: str
    type: NodeType

    @field_validator("id")
    @classmethod
    def validate_id(
        cls,
        value: str,
    ) -> str:
        return normalize_identifier(
            value,
            field_name="normalized endpoint id",
        )

    def to_architecture_node(
        self,
    ) -> ArchitectureNode:
        return ArchitectureNode(
            id=self.id,
            type=self.type,
        )


class NormalizedNodeObservation(BaseModel):
    """
    Evidence-backed observation that an architectural node exists.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    kind: Literal[
        ObservationKind.NODE
    ] = ObservationKind.NODE

    endpoint: NormalizedEndpoint

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
        return _normalize_evidence(value)

    @property
    def channel(self) -> EvidenceChannel:
        return _evidence_channel(
            self.evidence
        )


class NormalizedRelationObservation(BaseModel):
    """
    Evidence-backed technology-independent interaction observation.

    Protocol is retained as evidence-level metadata and does not participate
    in canonical relation identity.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    kind: Literal[
        ObservationKind.RELATION
    ] = ObservationKind.RELATION

    source: NormalizedEndpoint
    target: NormalizedEndpoint

    interaction: InteractionType

    protocol: str | None = None

    evidence: tuple[
        EvidenceRecord,
        ...,
    ]

    @field_validator("protocol")
    @classmethod
    def normalize_protocol(
        cls,
        value: str | None,
    ) -> str | None:
        normalized = normalize_optional_text(
            value
        )

        if normalized is None:
            return None

        return normalized.lower()

    @field_validator("evidence")
    @classmethod
    def validate_evidence(
        cls,
        value: tuple[EvidenceRecord, ...],
    ) -> tuple[EvidenceRecord, ...]:
        return _normalize_evidence(value)

    @property
    def channel(self) -> EvidenceChannel:
        return _evidence_channel(
            self.evidence
        )


NormalizedObservation = Annotated[
    NormalizedNodeObservation
    | NormalizedRelationObservation,
    Field(discriminator="kind"),
]