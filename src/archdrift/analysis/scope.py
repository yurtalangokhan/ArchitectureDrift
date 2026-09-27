from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from archdrift.model.observation import (
    NormalizedNodeObservation,
    NormalizedObservation,
    NormalizedRelationObservation,
)


class EvidenceScopeError(ValueError):
    """Base exception for evidence-scope processing."""


class ScopeExclusionReason(StrEnum):
    NODE_OUT_OF_SCOPE = "NODE_OUT_OF_SCOPE"
    RELATION_SOURCE_OUT_OF_SCOPE = "RELATION_SOURCE_OUT_OF_SCOPE"
    RELATION_TARGET_OUT_OF_SCOPE = "RELATION_TARGET_OUT_OF_SCOPE"


class EvidenceScope(BaseModel):
    """
    Defines the explicit architecture boundary of an experiment.

    Scope is deliberately separated from evidence extraction.

    Adapters report what they observe in the subject system. EvidenceScope
    decides which observations belong to the architecture boundary used by
    the experiment.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    node_ids: frozenset[str] = Field(
        min_length=1,
    )

    @field_validator("node_ids")
    @classmethod
    def validate_node_ids(
        cls,
        value: frozenset[str],
    ) -> frozenset[str]:
        normalized = frozenset(
            node_id.strip()
            for node_id in value
        )

        if "" in normalized:
            raise ValueError(
                "Evidence-scope node ids must not be empty."
            )

        if len(normalized) != len(value):
            raise ValueError(
                "Evidence-scope node ids must be unique after normalization."
            )

        return normalized

    def contains_node(
        self,
        node_id: str,
    ) -> bool:
        return node_id in self.node_ids

    def exclusion_reason(
        self,
        observation: NormalizedObservation,
    ) -> ScopeExclusionReason | None:
        if isinstance(
            observation,
            NormalizedNodeObservation,
        ):
            if not self.contains_node(
                observation.endpoint.id
            ):
                return (
                    ScopeExclusionReason.NODE_OUT_OF_SCOPE
                )

            return None

        if isinstance(
            observation,
            NormalizedRelationObservation,
        ):
            if not self.contains_node(
                observation.source.id
            ):
                return (
                    ScopeExclusionReason.RELATION_SOURCE_OUT_OF_SCOPE
                )

            if not self.contains_node(
                observation.target.id
            ):
                return (
                    ScopeExclusionReason.RELATION_TARGET_OUT_OF_SCOPE
                )

            return None

        raise EvidenceScopeError(
            "Unsupported normalized observation type: "
            f"{type(observation).__name__}"
        )


class ExcludedObservation(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    observation: NormalizedObservation
    reason: ScopeExclusionReason


class ScopedObservationSet(BaseModel):
    """
    Result of applying an EvidenceScope.

    Excluded evidence is retained rather than silently discarded so the
    experimental boundary remains auditable.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    included: tuple[
        NormalizedObservation,
        ...,
    ]

    excluded: tuple[
        ExcludedObservation,
        ...,
    ]

    @property
    def total_count(
        self,
    ) -> int:
        return (
            len(self.included)
            + len(self.excluded)
        )

    @property
    def included_count(
        self,
    ) -> int:
        return len(
            self.included
        )

    @property
    def excluded_count(
        self,
    ) -> int:
        return len(
            self.excluded
        )

    def excluded_count_for(
        self,
        reason: ScopeExclusionReason,
    ) -> int:
        return sum(
            item.reason is reason
            for item in self.excluded
        )


def apply_evidence_scope(
    observations: tuple[
        NormalizedObservation,
        ...,
    ],
    *,
    scope: EvidenceScope,
) -> ScopedObservationSet:
    """
    Apply an explicit experiment boundary to normalized observations.

    Ordering is preserved. No architectural inference is performed here.
    """

    included: list[
        NormalizedObservation
    ] = []

    excluded: list[
        ExcludedObservation
    ] = []

    for observation in observations:
        reason = scope.exclusion_reason(
            observation
        )

        if reason is None:
            included.append(
                observation
            )

            continue

        excluded.append(
            ExcludedObservation(
                observation=observation,
                reason=reason,
            )
        )

    return ScopedObservationSet(
        included=tuple(
            included
        ),
        excluded=tuple(
            excluded
        ),
    )