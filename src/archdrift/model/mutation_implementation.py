from __future__ import annotations

from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)

from archdrift.model._validation import (
    normalize_identifier,
    normalize_required_text,
)


class MutationImplementationError(
    ValueError
):
    """Base error for source-level mutation implementations."""


class MutationImplementationLoadError(
    MutationImplementationError
):
    """Raised when the implementation manifest cannot be loaded."""


class MutationImplementation(BaseModel):
    """
    Source-level implementation of one graph-level mutation oracle.

    The oracle specifies WHAT architectural change is expected.
    The patch specifies HOW that change is injected into a pinned subject.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    mutation_id: str

    system_id: str

    oracle: str

    patch: str

    @field_validator(
        "mutation_id",
        "system_id",
    )
    @classmethod
    def validate_identifier(
        cls,
        value: str,
        info: object,
    ) -> str:
        field_name = getattr(
            info,
            "field_name",
            "identifier",
        )

        return normalize_identifier(
            value,
            field_name=str(field_name),
        )

    @field_validator(
        "oracle",
        "patch",
    )
    @classmethod
    def validate_path(
        cls,
        value: str,
    ) -> str:
        return normalize_required_text(
            value,
            field_name="mutation implementation path",
        )


class MutationImplementationManifest(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    schema_version: Literal["1.0"] = "1.0"

    implementations: tuple[
        MutationImplementation,
        ...,
    ]

    @model_validator(
        mode="after"
    )
    def validate_implementations(
        self,
    ) -> Self:
        if not self.implementations:
            raise ValueError(
                "Mutation implementation manifest "
                "must not be empty."
            )

        identities = tuple(
            (
                implementation.system_id,
                implementation.mutation_id,
            )
            for implementation
            in self.implementations
        )

        if len(identities) != len(
            set(identities)
        ):
            raise ValueError(
                "Mutation implementation manifest "
                "contains duplicate identities."
            )

        mutation_ids = tuple(
            implementation.mutation_id
            for implementation
            in self.implementations
        )

        if len(mutation_ids) != len(
            set(mutation_ids)
        ):
            raise ValueError(
                "Mutation ids must be globally unique "
                "inside the implementation manifest."
            )

        return self

    def require(
        self,
        mutation_id: str,
    ) -> MutationImplementation:
        for implementation in (
            self.implementations
        ):
            if (
                implementation.mutation_id
                == mutation_id
            ):
                return implementation

        raise MutationImplementationError(
            "Unknown mutation implementation: "
            f"{mutation_id!r}"
        )


def load_mutation_implementation_manifest(
    path: str | Path,
) -> MutationImplementationManifest:
    manifest_path = Path(
        path
    )

    if not manifest_path.is_file():
        raise FileNotFoundError(
            "Mutation implementation manifest "
            f"not found: {manifest_path}"
        )

    try:
        document = yaml.safe_load(
            manifest_path.read_text(
                encoding="utf-8",
            )
        )

    except yaml.YAMLError as exc:
        raise MutationImplementationLoadError(
            "Invalid mutation implementation "
            f"manifest YAML: {manifest_path}"
        ) from exc

    if not isinstance(
        document,
        dict,
    ):
        raise MutationImplementationLoadError(
            "Mutation implementation manifest "
            "root must be a mapping."
        )

    return (
        MutationImplementationManifest
        .model_validate(
            document
        )
    )