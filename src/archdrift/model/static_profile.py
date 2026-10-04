from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from archdrift.model.graph import (
    NodeType,
)


class StaticSourceRoot(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    service_id: str
    path: str

    rule_packs: tuple[
        str,
        ...,
    ]

    exclude: tuple[
        str,
        ...,
    ] = ()

    @field_validator(
        "service_id",
        "path",
    )
    @classmethod
    def validate_non_empty(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("Static source root values must not be empty.")

        return normalized


class StaticEvidenceProfile(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    schema_version: Literal["1.0"]

    subject_id: str

    subject_root: str

    node_types: dict[
        str,
        NodeType,
    ]

    source_roots: tuple[
        StaticSourceRoot,
        ...,
    ]

    @field_validator(
        "subject_id",
        "subject_root",
    )
    @classmethod
    def validate_non_empty(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("Static evidence profile values " "must not be empty.")

        return normalized


class ComposeEvidenceProfile(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    project_directory: str = "."

    files: tuple[
        str,
        ...,
    ] = Field(
        min_length=1,
    )

    @field_validator(
        "project_directory",
    )
    @classmethod
    def validate_project_directory(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("Compose project directory " "must not be empty.")

        return normalized


class AspireEvidenceProfile(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    files: tuple[
        str,
        ...,
    ] = Field(
        min_length=1,
    )


class NonRuntimeEvidenceProfile(StaticEvidenceProfile):
    compose: ComposeEvidenceProfile | None = None

    aspire: AspireEvidenceProfile | None = None

    @model_validator(mode="after")
    def validate_deployment_source(
        self,
    ) -> NonRuntimeEvidenceProfile:
        configured = sum(
            (
                self.compose is not None,
                self.aspire is not None,
            )
        )

        if configured != 1:
            raise ValueError(
                "Exactly one deployment/config "
                "evidence source must be "
                "configured: compose or aspire."
            )

        return self
