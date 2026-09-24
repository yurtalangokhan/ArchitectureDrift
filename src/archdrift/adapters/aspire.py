from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

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
    InteractionType,
    NormalizedEndpoint,
    NormalizedNodeObservation,
    NormalizedObservation,
    NormalizedRelationObservation,
)


class AspireAdapterError(NonRuntimeAdapterError):
    """Raised when supported .NET Aspire declarations cannot be parsed."""


_RESOURCE_CALL_PATTERN = re.compile(
    r"\bbuilder"
    r"\s*\.\s*"
    r"(?P<method>"
    r"AddProject\s*<[^>]+>"
    r"|AddRedis"
    r"|AddPostgres"
    r"|AddSqlServer"
    r"|AddMongoDB"
    r"|AddRabbitMQ"
    r"|AddKafka"
    r")"
    r"\s*\(\s*"
    r'"(?P<resource_id>[^"]+)"',
    re.DOTALL,
)


_ASSIGNMENT_PATTERN = re.compile(
    r"(?P<variable>[A-Za-z_][A-Za-z0-9_]*)"
    r"\s*=\s*$"
)


_REFERENCE_PATTERN = re.compile(
    r"\.\s*WithReference"
    r"\s*\(\s*"
    r"(?P<target>[A-Za-z_][A-Za-z0-9_]*)"
    r"\s*\)"
)


@dataclass(
    frozen=True,
    slots=True,
)
class _AspireResource:
    id: str
    type: NodeType
    variable: str | None
    line: int


def _resource_type(
    method: str,
) -> NodeType:
    normalized = re.sub(
        r"\s+",
        "",
        method,
    )

    if normalized.startswith(
        "AddProject<"
    ):
        return NodeType.SERVICE

    if normalized in {
        "AddRedis",
        "AddPostgres",
        "AddSqlServer",
        "AddMongoDB",
    }:
        return NodeType.DATASTORE

    if normalized in {
        "AddRabbitMQ",
        "AddKafka",
    }:
        return NodeType.BROKER

    raise AspireAdapterError(
        f"Unsupported Aspire resource method: {method}"
    )

def _iter_statements(
    text: str,
) -> tuple[
    tuple[int, str],
    ...,
]:
    """
    Split AppHost source into semicolon-terminated statements.

    This intentionally supports the common declarative Aspire AppHost style,
    not arbitrary C# syntax.
    """

    result: list[
        tuple[int, str]
    ] = []

    start = 0

    for match in re.finditer(
        ";",
        text,
    ):
        end = match.end()

        result.append(
            (
                start,
                text[start:end],
            )
        )

        start = end

    if start < len(text):
        remainder = text[start:]

        if remainder.strip():
            result.append(
                (
                    start,
                    remainder,
                )
            )

    return tuple(result)


class AspireAdapter:
    """
    Extract supported non-runtime observations from .NET Aspire AppHost code.

    AddProject resources become SERVICE nodes.

    Supported infrastructure resource declarations become DATASTORE/BROKER
    nodes.

    A service-to-service WithReference is represented as SERVICE_CALL.

    Datastore/broker WithReference declarations are not converted into
    READS_FROM/WRITES_TO/PUBLISHES_TO/SUBSCRIBES_TO because WithReference
    alone does not provide that semantic information.
    """

    def __init__(
        self,
        repository_root: str | Path,
        apphost_file: str | Path,
    ) -> None:
        self._repository_root = Path(
            repository_root
        )

        self._apphost_file = apphost_file

    def collect(
        self,
    ) -> tuple[NormalizedObservation, ...]:
        root = self._repository_root.resolve()

        apphost_path = resolve_repository_path(
            root,
            self._apphost_file,
        )

        if not apphost_path.is_file():
            raise AspireAdapterError(
                f"AppHost file not found: {self._apphost_file}"
            )

        text = apphost_path.read_text(
            encoding="utf-8",
        )

        artifact = repository_artifact_id(
            root,
            apphost_path,
        )

        statements = _iter_statements(
            text
        )

        resources: dict[
            str,
            _AspireResource
        ] = {}

        variables: dict[
            str,
            _AspireResource
        ] = {}

        statement_resources: dict[
            int,
            _AspireResource
        ] = {}

        # ---------------------------------------------------------------------
        # Pass 1: resource discovery
        # ---------------------------------------------------------------------

        for offset, statement in statements:
            resource_match = (
                _RESOURCE_CALL_PATTERN.search(
                    statement
                )
            )

            if resource_match is None:
                continue

            method = resource_match.group(
                "method"
            )

            resource_id = resource_match.group(
                "resource_id"
            )

            node_type = _resource_type(
                method
            )

            prefix = statement[
                : resource_match.start()
            ]

            assignment = (
                _ASSIGNMENT_PATTERN.search(
                    prefix
                )
            )

            variable = (
                assignment.group(
                    "variable"
                )
                if assignment is not None
                else None
            )

            line = (
                text.count(
                    "\n",
                    0,
                    offset
                    + resource_match.start(),
                )
                + 1
            )

            if resource_id in resources:
                raise AspireAdapterError(
                    "Duplicate Aspire resource identifier: "
                    f"{resource_id!r}"
                )

            resource = _AspireResource(
                id=resource_id,
                type=node_type,
                variable=variable,
                line=line,
            )

            resources[
                resource_id
            ] = resource

            statement_resources[
                offset
            ] = resource

            if variable is not None:
                variables[
                    variable
                ] = resource

        observations: list[
            NormalizedObservation
        ] = []

        # ---------------------------------------------------------------------
        # Node observations
        # ---------------------------------------------------------------------

        for resource in sorted(
            resources.values(),
            key=lambda item: item.id,
        ):
            evidence = EvidenceRecord(
                type=EvidenceType.REPOSITORY_CONFIG,
                artifact=artifact,
                locator=(
                    f"line:{resource.line}:"
                    f"resource:{resource.id}"
                ),
            )

            observations.append(
                NormalizedNodeObservation(
                    endpoint=NormalizedEndpoint(
                        id=resource.id,
                        type=resource.type,
                    ),
                    evidence=(
                        evidence,
                    ),
                )
            )

        # ---------------------------------------------------------------------
        # Pass 2: service references
        # ---------------------------------------------------------------------

        for offset, statement in statements:
            source_resource = (
                statement_resources.get(
                    offset
                )
            )

            if source_resource is None:
                continue

            if (
                source_resource.type
                is not NodeType.SERVICE
            ):
                continue

            for reference_match in (
                _REFERENCE_PATTERN.finditer(
                    statement
                )
            ):
                target_variable = (
                    reference_match.group(
                        "target"
                    )
                )

                target_resource = (
                    variables.get(
                        target_variable
                    )
                )

                if target_resource is None:
                    # Could be a parameter or unsupported Aspire resource.
                    continue

                if (
                    target_resource.type
                    is not NodeType.SERVICE
                ):
                    # WithReference to a datastore/broker does not tell us
                    # read/write or publish/subscribe semantics.
                    continue

                line = (
                    text.count(
                        "\n",
                        0,
                        offset
                        + reference_match.start(),
                    )
                    + 1
                )

                evidence = EvidenceRecord(
                    type=EvidenceType.REPOSITORY_CONFIG,
                    artifact=artifact,
                    locator=(
                        f"line:{line}:"
                        "WithReference"
                    ),
                )

                observations.append(
                    NormalizedRelationObservation(
                        source=NormalizedEndpoint(
                            id=source_resource.id,
                            type=source_resource.type,
                        ),
                        target=NormalizedEndpoint(
                            id=target_resource.id,
                            type=target_resource.type,
                        ),
                        interaction=(
                            InteractionType.SERVICE_CALL
                        ),
                        evidence=(
                            evidence,
                        ),
                    )
                )

        return tuple(observations)