from __future__ import annotations

from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
)

from archdrift.adapters.base import (
    NonRuntimeAdapterError,
    repository_artifact_id,
    resolve_repository_path,
)
from archdrift.model.evidence import (
    EvidenceRecord,
    EvidenceType,
)
from archdrift.model.graph import NodeType
from archdrift.model.observation import (
    NormalizedEndpoint,
    NormalizedNodeObservation,
    NormalizedObservation,
)


class RepositoryServiceSpec(BaseModel):
    """
    Explicit repository-level service discovery specification.

    This identifies component roots only. It contains no relation ground truth.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    id: str

    path: str

    type: NodeType = NodeType.SERVICE

    markers: tuple[str, ...] = ()

    @field_validator("path")
    @classmethod
    def validate_path(
        cls,
        value: str,
    ) -> str:
        path = Path(value)

        if path.is_absolute():
            raise ValueError(
                "Repository service path must be relative."
            )

        if ".." in path.parts:
            raise ValueError(
                "Repository service path must not contain '..'."
            )

        return value

    @field_validator("markers")
    @classmethod
    def validate_markers(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        normalized = tuple(
            sorted(
                set(value)
            )
        )

        for marker in normalized:
            path = Path(marker)

            if path.is_absolute():
                raise ValueError(
                    "Repository marker must be relative."
                )

            if ".." in path.parts:
                raise ValueError(
                    "Repository marker must not contain '..'."
                )

        return normalized


class RepositoryAdapter:
    """
    Produce node observations from explicit repository component roots.

    This adapter deliberately does not infer CALLS relations from arbitrary
    text occurrences.
    """

    def __init__(
        self,
        repository_root: str | Path,
        services: tuple[
            RepositoryServiceSpec,
            ...,
        ],
    ) -> None:
        self._repository_root = Path(
            repository_root
        )

        self._services = tuple(
            sorted(
                services,
                key=lambda service: service.id,
            )
        )

    def collect(
        self,
    ) -> tuple[NormalizedObservation, ...]:
        root = self._repository_root.resolve()

        if not root.is_dir():
            raise NonRuntimeAdapterError(
                f"Repository root does not exist: {root}"
            )

        observations: list[
            NormalizedObservation
        ] = []

        for service in self._services:
            service_path = resolve_repository_path(
                root,
                service.path,
            )

            if not service_path.is_dir():
                raise NonRuntimeAdapterError(
                    "Repository service directory does not exist: "
                    f"{service.path}"
                )

            evidence: list[
                EvidenceRecord
            ] = []

            if service.markers:
                for marker in service.markers:
                    marker_path = (
                        resolve_repository_path(
                            service_path,
                            marker,
                        )
                    )

                    if not marker_path.is_file():
                        continue

                    evidence.append(
                        EvidenceRecord(
                            type=EvidenceType.SOURCE_CODE,
                            artifact=repository_artifact_id(
                                root,
                                marker_path,
                            ),
                            locator=(
                                f"service:{service.id}"
                            ),
                        )
                    )

                if not evidence:
                    raise NonRuntimeAdapterError(
                        "No configured repository marker exists for "
                        f"service {service.id!r}."
                    )

            else:
                evidence.append(
                    EvidenceRecord(
                        type=EvidenceType.SOURCE_CODE,
                        artifact=repository_artifact_id(
                            root,
                            service_path,
                        ),
                        locator="service-root",
                    )
                )

            observations.append(
                NormalizedNodeObservation(
                    endpoint=NormalizedEndpoint(
                        id=service.id,
                        type=service.type,
                    ),
                    evidence=tuple(evidence),
                )
            )

        return tuple(observations)