from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from archdrift.model.graph import NodeType
from archdrift.model.observation import InteractionType


class SourceStaticFinding(BaseModel):
    """
    Engine-neutral source-static interaction finding.

    A finding identifies a source-code location and a target expression,
    but does not yet claim that the expression resolves to a canonical
    architecture endpoint.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    engine: Literal["semgrep"] = "semgrep"

    rule_id: str

    path: str

    line: int = Field(
        ge=1,
    )

    interaction: InteractionType

    target_expression: str

    protocol: str | None = None

    @field_validator(
        "rule_id",
        "path",
        "target_expression",
    )
    @classmethod
    def validate_non_empty(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Source-static finding values must not be empty."
            )

        return normalized


class StaticResolutionStatus(StrEnum):
    RESOLVED = "RESOLVED"

    SOURCE_NOT_RESOLVED = (
        "SOURCE_NOT_RESOLVED"
    )

    TARGET_EXPRESSION_NOT_RESOLVED = (
        "TARGET_EXPRESSION_NOT_RESOLVED"
    )

    ENDPOINT_BINDING_NOT_FOUND = (
        "ENDPOINT_BINDING_NOT_FOUND"
    )


class SourcePathRule(BaseModel):
    """
    Explicit source-tree to canonical-service mapping.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    path_prefix: str

    service_id: str

    service_type: NodeType = (
        NodeType.SERVICE
    )

    @field_validator(
        "path_prefix",
        "service_id",
    )
    @classmethod
    def validate_non_empty(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Source path rule values must not be empty."
            )

        return normalized


class EndpointBinding(BaseModel):
    """
    Resolved configuration binding from one source service environment
    variable to one canonical architecture endpoint.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    source_service_id: str

    environment_key: str

    target_service_id: str

    target_type: NodeType

    raw_value: str


class ResolvedStaticInteraction(BaseModel):
    """
    High-confidence static interaction after path and endpoint resolution.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    finding: SourceStaticFinding

    source_service_id: str

    source_type: NodeType

    environment_key: str

    target_service_id: str

    target_type: NodeType


class StaticResolution(BaseModel):
    """
    Resolution outcome for one source-static finding.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    finding: SourceStaticFinding

    status: StaticResolutionStatus

    resolved: (
        ResolvedStaticInteraction
        | None
    ) = None

    reason: str | None = None


class StaticResolutionSet(BaseModel):
    """
    Resolution results for a complete source-static finding set.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    results: tuple[
        StaticResolution,
        ...,
    ]

    @property
    def resolved(
        self,
    ) -> tuple[
        ResolvedStaticInteraction,
        ...,
    ]:
        return tuple(
            result.resolved
            for result in self.results
            if result.resolved is not None
        )

    @property
    def resolved_count(
        self,
    ) -> int:
        return len(
            self.resolved
        )

    @property
    def unresolved_count(
        self,
    ) -> int:
        return (
            len(self.results)
            - self.resolved_count
        )