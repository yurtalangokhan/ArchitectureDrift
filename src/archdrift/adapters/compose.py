from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

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

_HOST_PORT_PATTERN = re.compile(
    r"^(?P<host>[A-Za-z0-9][A-Za-z0-9_.-]*)"
    r"(?::[0-9]+)?"
    r"(?:/.*)?$"
)


class ComposeAdapterError(NonRuntimeAdapterError):
    """Raised when Docker Compose evidence cannot be parsed."""


class ComposeAdapter:
    """
    Extract non-runtime architecture observations from Docker Compose.

    Supported semantics:

    - each Compose service becomes a node observation;
    - endpoint-like environment values referencing another Compose service
      become SERVICE_CALL observations when both endpoints are call-capable;
    - depends_on is deliberately NOT mapped to CALLS.
    """

    def __init__(
        self,
        repository_root: str | Path,
        compose_file: str | Path,
        *,
        node_types: dict[
            str,
            NodeType,
        ] | None = None,
        ignored_environment_keys: frozenset[
            str
        ] = frozenset(),
    ) -> None:
        self._repository_root = Path(
            repository_root
        )

        self._compose_file = compose_file

        self._node_types = (
            dict(node_types)
            if node_types is not None
            else {}
        )

        self._ignored_environment_keys = (
            ignored_environment_keys
        )

    def collect(
        self,
    ) -> tuple[NormalizedObservation, ...]:
        root = self._repository_root.resolve()

        compose_path = resolve_repository_path(
            root,
            self._compose_file,
        )

        if not compose_path.is_file():
            raise ComposeAdapterError(
                f"Compose file not found: {self._compose_file}"
            )

        document = self._load_document(
            compose_path
        )

        services = document.get(
            "services"
        )

        if not isinstance(
            services,
            dict,
        ):
            raise ComposeAdapterError(
                "Compose document must define a services mapping."
            )

        artifact = repository_artifact_id(
            root,
            compose_path,
        )

        service_names = frozenset(
            str(name)
            for name in services
        )

        observations: list[
            NormalizedObservation
        ] = []

        for service_name in sorted(
            service_names
        ):
            service_config = services[
                service_name
            ]

            if not isinstance(
                service_config,
                dict,
            ):
                raise ComposeAdapterError(
                    "Compose service configuration must be a mapping: "
                    f"{service_name}"
                )

            source_type = self._node_types.get(
                service_name,
                NodeType.SERVICE,
            )

            node_evidence = EvidenceRecord(
                type=EvidenceType.DEPLOYMENT_CONFIG,
                artifact=artifact,
                locator=f"services.{service_name}",
            )

            observations.append(
                NormalizedNodeObservation(
                    endpoint=NormalizedEndpoint(
                        id=service_name,
                        type=source_type,
                    ),
                    evidence=(
                        node_evidence,
                    ),
                )
            )

            if source_type not in {
                NodeType.SERVICE,
                NodeType.GATEWAY,
            }:
                continue

            environment = self._parse_environment(
                service_config.get(
                    "environment"
                )
            )

            for key, value in environment:
                if (
                    key
                    in self._ignored_environment_keys
                ):
                    continue

                resolved = (
                    self._resolve_service_reference(
                        value,
                        service_names,
                    )
                )

                if resolved is None:
                    continue

                target_name, protocol = resolved

                if target_name == service_name:
                    continue

                target_type = self._node_types.get(
                    target_name,
                    NodeType.SERVICE,
                )

                if target_type not in {
                    NodeType.SERVICE,
                    NodeType.GATEWAY,
                    NodeType.EXTERNAL,
                }:
                    # Endpoint configuration alone cannot determine whether a
                    # datastore is read/written or a broker is published/
                    # subscribed, so no canonical interaction is inferred.
                    continue

                evidence = EvidenceRecord(
                    type=EvidenceType.DEPLOYMENT_CONFIG,
                    artifact=artifact,
                    locator=(
                        f"services.{service_name}."
                        f"environment.{key}"
                    ),
                )

                observations.append(
                    NormalizedRelationObservation(
                        source=NormalizedEndpoint(
                            id=service_name,
                            type=source_type,
                        ),
                        target=NormalizedEndpoint(
                            id=target_name,
                            type=target_type,
                        ),
                        interaction=(
                            InteractionType.SERVICE_CALL
                        ),
                        protocol=protocol,
                        evidence=(
                            evidence,
                        ),
                    )
                )

        return tuple(observations)

    @staticmethod
    def _load_document(
        path: Path,
    ) -> dict[str, Any]:
        try:
            with path.open(
                "r",
                encoding="utf-8",
            ) as file:
                document = yaml.safe_load(
                    file
                )

        except yaml.YAMLError as exc:
            raise ComposeAdapterError(
                f"Invalid Compose YAML: {path}"
            ) from exc

        if not isinstance(
            document,
            dict,
        ):
            raise ComposeAdapterError(
                "Compose YAML root must be a mapping."
            )

        return document

    @staticmethod
    def _parse_environment(
        raw_environment: object,
    ) -> tuple[
        tuple[str, str],
        ...,
    ]:
        if raw_environment is None:
            return ()

        result: list[
            tuple[str, str]
        ] = []

        if isinstance(
            raw_environment,
            dict,
        ):
            for key, value in raw_environment.items():
                if value is None:
                    continue

                result.append(
                    (
                        str(key),
                        str(value),
                    )
                )

        elif isinstance(
            raw_environment,
            list,
        ):
            for entry in raw_environment:
                if not isinstance(
                    entry,
                    str,
                ):
                    continue

                if "=" not in entry:
                    continue

                key, value = entry.split(
                    "=",
                    1,
                )

                result.append(
                    (
                        key,
                        value,
                    )
                )

        else:
            raise ComposeAdapterError(
                "Compose environment must be a mapping or list."
            )

        return tuple(
            sorted(
                result,
                key=lambda item: item[0],
            )
        )

    @staticmethod
    def _resolve_service_reference(
        value: str,
        service_names: frozenset[str],
    ) -> tuple[str, str | None] | None:
        candidate = value.strip()

        if not candidate:
            return None

        # Variable interpolation does not provide a concrete target.
        if candidate.startswith(
            "${"
        ):
            return None

        protocol: str | None = None
        host: str | None = None

        if candidate.startswith(
            "dns:///"
        ):
            remainder = candidate[
                len("dns:///") :
            ]

            match = _HOST_PORT_PATTERN.fullmatch(
                remainder
            )

            if match is not None:
                host = match.group(
                    "host"
                )

                protocol = "dns"

        elif "://" in candidate:
            parsed = urlsplit(
                candidate
            )

            host = parsed.hostname

            if parsed.scheme:
                protocol = (
                    parsed.scheme.lower()
                )

        else:
            match = _HOST_PORT_PATTERN.fullmatch(
                candidate
            )

            if match is not None:
                host = match.group(
                    "host"
                )

        if (
            host is None
            or host not in service_names
        ):
            return None

        return (
            host,
            protocol,
        )