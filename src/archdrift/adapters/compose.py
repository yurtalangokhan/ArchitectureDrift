from __future__ import annotations

import re
from collections.abc import Mapping
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


class ComposeAdapterError(NonRuntimeAdapterError):
    """Raised when Docker Compose evidence cannot be parsed safely."""


class _ResolvedReference:
    """
    Internal value object representing a reference to another Compose service.

    This deliberately remains adapter-internal. Canonical architecture
    semantics are assigned separately.
    """

    __slots__ = (
        "target",
        "protocol",
    )

    def __init__(
        self,
        *,
        target: str,
        protocol: str | None,
    ) -> None:
        self.target = target
        self.protocol = protocol


_HOST_REFERENCE_PATTERN = re.compile(
    r"^(?P<host>[A-Za-z0-9][A-Za-z0-9_.-]*)"
    r"(?::(?P<port>[0-9]+))?"
    r"(?:/.*)?$"
)


class ComposeAdapter:
    """
    Extract conservative non-runtime architecture observations from
    Docker Compose configuration.

    Inference policy
    ----------------

    Nodes:
        Every Compose service becomes a normalized architecture node.

    Relations:
        Environment values that resolve to another Compose service may
        produce an architectural interaction.

        SERVICE/GATEWAY -> SERVICE/GATEWAY/EXTERNAL
            SERVICE_CALL

        SERVICE/GATEWAY -> REGISTRY
            DISCOVERY

        SERVICE/GATEWAY -> DATASTORE/BROKER
            No relation is inferred because an endpoint alone cannot
            distinguish READ vs WRITE or PUBLISH vs SUBSCRIBE.

    Explicit exclusions:
        - depends_on is not interpreted as CALLS.
        - unresolved external host names are ignored.
        - environment-variable interpolation without a concrete default
          target is ignored.
        - self references are ignored.

    The adapter produces NormalizedObservation values only. It never
    constructs ArchitectureGraph directly.
    """

    _CALL_CAPABLE_SOURCE_TYPES = frozenset(
        {
            NodeType.SERVICE,
            NodeType.GATEWAY,
        }
    )

    _CALL_CAPABLE_TARGET_TYPES = frozenset(
        {
            NodeType.SERVICE,
            NodeType.GATEWAY,
            NodeType.EXTERNAL,
        }
    )

    def __init__(
        self,
        repository_root: str | Path,
        compose_file: str | Path,
        *,
        node_types: Mapping[
            str,
            NodeType,
        ]
        | None = None,
        ignored_environment_keys: frozenset[
            str
        ] = frozenset(),
    ) -> None:
        self._repository_root = Path(
            repository_root
        )

        self._compose_file = Path(
            compose_file
        )

        self._node_types = dict(
            node_types
            or {}
        )

        self._ignored_environment_keys = frozenset(
            ignored_environment_keys
        )

    def collect(
        self,
    ) -> tuple[
        NormalizedObservation,
        ...,
    ]:
        """
        Collect deterministic node and relation observations.

        Node observations are emitted first, followed by relation
        observations. Each group is deterministically ordered.
        """

        root = self._repository_root.resolve()

        if not root.is_dir():
            raise ComposeAdapterError(
                f"Repository root does not exist: {root}"
            )

        compose_path = resolve_repository_path(
            root,
            self._compose_file,
        )

        document = self._load_document(
            compose_path
        )

        services = self._load_services(
            document
        )

        artifact = repository_artifact_id(
            root,
            compose_path,
        )

        service_names = frozenset(
            services
        )

        node_observations = (
            self._collect_node_observations(
                services=services,
                artifact=artifact,
            )
        )

        relation_observations = (
            self._collect_relation_observations(
                services=services,
                service_names=service_names,
                artifact=artifact,
            )
        )

        return (
            *node_observations,
            *relation_observations,
        )

    # -------------------------------------------------------------------------
    # Document loading
    # -------------------------------------------------------------------------

    @staticmethod
    def _load_document(
        path: Path,
    ) -> Mapping[str, Any]:
        if not path.is_file():
            raise ComposeAdapterError(
                f"Compose file not found: {path}"
            )

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
            Mapping,
        ):
            raise ComposeAdapterError(
                "Compose YAML root must be a mapping."
            )

        return document

    @staticmethod
    def _load_services(
        document: Mapping[str, Any],
    ) -> dict[
        str,
        Mapping[str, Any],
    ]:
        raw_services = document.get(
            "services"
        )

        if not isinstance(
            raw_services,
            Mapping,
        ):
            raise ComposeAdapterError(
                "Compose document must define a services mapping."
            )

        services: dict[
            str,
            Mapping[str, Any],
        ] = {}

        for raw_name, raw_config in raw_services.items():
            service_name = str(
                raw_name
            ).strip()

            if not service_name:
                raise ComposeAdapterError(
                    "Compose service name must not be empty."
                )

            if not isinstance(
                raw_config,
                Mapping,
            ):
                raise ComposeAdapterError(
                    "Compose service configuration must be a mapping: "
                    f"{service_name}"
                )

            services[
                service_name
            ] = raw_config

        return services

    # -------------------------------------------------------------------------
    # Node extraction
    # -------------------------------------------------------------------------

    def _collect_node_observations(
        self,
        *,
        services: Mapping[
            str,
            Mapping[str, Any],
        ],
        artifact: str,
    ) -> tuple[
        NormalizedNodeObservation,
        ...,
    ]:
        observations: list[
            NormalizedNodeObservation
        ] = []

        for service_name in sorted(
            services
        ):
            observations.append(
                NormalizedNodeObservation(
                    endpoint=self._endpoint(
                        service_name
                    ),
                    evidence=(
                        EvidenceRecord(
                            type=(
                                EvidenceType.DEPLOYMENT_CONFIG
                            ),
                            artifact=artifact,
                            locator=(
                                f"services.{service_name}"
                            ),
                        ),
                    ),
                )
            )

        return tuple(
            observations
        )

    # -------------------------------------------------------------------------
    # Relation extraction
    # -------------------------------------------------------------------------

    def _collect_relation_observations(
        self,
        *,
        services: Mapping[
            str,
            Mapping[str, Any],
        ],
        service_names: frozenset[str],
        artifact: str,
    ) -> tuple[
        NormalizedRelationObservation,
        ...,
    ]:
        observations: list[
            NormalizedRelationObservation
        ] = []

        for source_name in sorted(
            services
        ):
            source_type = self._node_type(
                source_name
            )

            if (
                source_type
                not in self._CALL_CAPABLE_SOURCE_TYPES
            ):
                continue

            environment = self._parse_environment(
                services[
                    source_name
                ].get(
                    "environment"
                )
            )

            for key, value in environment:
                if (
                    key
                    in self._ignored_environment_keys
                ):
                    continue

                reference = (
                    self._resolve_service_reference(
                        value=value,
                        service_names=service_names,
                    )
                )

                if reference is None:
                    continue

                if (
                    reference.target
                    == source_name
                ):
                    continue

                target_type = self._node_type(
                    reference.target
                )

                interaction = (
                    self._classify_interaction(
                        target_type
                    )
                )

                if interaction is None:
                    continue

                evidence = EvidenceRecord(
                    type=(
                        EvidenceType.DEPLOYMENT_CONFIG
                    ),
                    artifact=artifact,
                    locator=(
                        f"services.{source_name}."
                        f"environment.{key}"
                    ),
                )

                observations.append(
                    NormalizedRelationObservation(
                        source=NormalizedEndpoint(
                            id=source_name,
                            type=source_type,
                        ),
                        target=NormalizedEndpoint(
                            id=reference.target,
                            type=target_type,
                        ),
                        interaction=interaction,
                        protocol=reference.protocol,
                        evidence=(
                            evidence,
                        ),
                    )
                )

        return tuple(
            sorted(
                observations,
                key=lambda observation: (
                    observation.source.id,
                    observation.interaction.value,
                    observation.target.id,
                    observation.protocol or "",
                ),
            )
        )

    # -------------------------------------------------------------------------
    # Semantic classification
    # -------------------------------------------------------------------------

    @classmethod
    def _classify_interaction(
        cls,
        target_type: NodeType,
    ) -> InteractionType | None:
        if (
            target_type
            is NodeType.REGISTRY
        ):
            return (
                InteractionType.DISCOVERY
            )

        if (
            target_type
            in cls._CALL_CAPABLE_TARGET_TYPES
        ):
            return (
                InteractionType.SERVICE_CALL
            )

        return None

    def _node_type(
        self,
        service_name: str,
    ) -> NodeType:
        return self._node_types.get(
            service_name,
            NodeType.SERVICE,
        )

    def _endpoint(
        self,
        service_name: str,
    ) -> NormalizedEndpoint:
        return NormalizedEndpoint(
            id=service_name,
            type=self._node_type(
                service_name
            ),
        )

    # -------------------------------------------------------------------------
    # Environment parsing
    # -------------------------------------------------------------------------

    @staticmethod
    def _parse_environment(
        raw_environment: object,
    ) -> tuple[
        tuple[str, str],
        ...,
    ]:
        """
        Normalize Compose environment syntax.

        Supported:

            environment:
              KEY: value

        and:

            environment:
              - KEY=value

        Entries without concrete values are ignored.
        """

        if raw_environment is None:
            return ()

        result: list[
            tuple[str, str]
        ] = []

        if isinstance(
            raw_environment,
            Mapping,
        ):
            for raw_key, raw_value in (
                raw_environment.items()
            ):
                if raw_value is None:
                    continue

                key = str(
                    raw_key
                ).strip()

                value = str(
                    raw_value
                ).strip()

                if (
                    not key
                    or not value
                ):
                    continue

                result.append(
                    (
                        key,
                        value,
                    )
                )

        elif isinstance(
            raw_environment,
            list,
        ):
            for raw_entry in raw_environment:
                if not isinstance(
                    raw_entry,
                    str,
                ):
                    continue

                if "=" not in raw_entry:
                    # KEY without a concrete value is inherited from
                    # the shell environment and therefore not
                    # deterministic evidence.
                    continue

                raw_key, raw_value = (
                    raw_entry.split(
                        "=",
                        1,
                    )
                )

                key = raw_key.strip()
                value = raw_value.strip()

                if (
                    not key
                    or not value
                ):
                    continue

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

    # -------------------------------------------------------------------------
    # Service reference resolution
    # -------------------------------------------------------------------------

    @classmethod
    def _resolve_service_reference(
        cls,
        *,
        value: str,
        service_names: frozenset[str],
    ) -> _ResolvedReference | None:
        """
        Resolve an environment value to a Compose service.

        Supported examples:

            recommendation
            recommendation:8080
            recommendation:8080/api
            http://recommendation:8080
            https://recommendation:8443/api
            grpc://recommendation:8080
            dns:///recommendation:8080

        Only hosts that correspond to services declared in the same
        Compose document are accepted.
        """

        candidate = value.strip()

        if not candidate:
            return None

        if cls._is_unresolved_interpolation(
            candidate
        ):
            return None

        resolved = (
            cls._parse_uri_reference(
                candidate
            )
        )

        if resolved is None:
            resolved = (
                cls._parse_host_reference(
                    candidate
                )
            )

        if resolved is None:
            return None

        if (
            resolved.target
            not in service_names
        ):
            return None

        return resolved

    @staticmethod
    def _is_unresolved_interpolation(
        value: str,
    ) -> bool:
        """
        Reject values whose target depends entirely on runtime shell
        interpolation.

        Examples rejected:

            ${RECOMMENDATION_ADDR}
            ${HOST}:${PORT}

        Concrete values such as ordinary URLs remain unaffected.
        """

        return "${" in value

    @classmethod
    def _parse_uri_reference(
        cls,
        value: str,
    ) -> _ResolvedReference | None:
        # gRPC commonly uses the DNS resolver form:
        #
        #     dns:///recommendation:8080
        #
        # urllib treats the endpoint as a path because this URI has no
        # authority component, so handle it explicitly.
        if value.lower().startswith(
            "dns:///"
        ):
            endpoint = value[
                len("dns:///") :
            ]

            host = (
                cls._extract_host(
                    endpoint
                )
            )

            if host is None:
                return None

            return _ResolvedReference(
                target=host,
                protocol="dns",
            )

        if "://" not in value:
            return None

        try:
            parsed = urlsplit(
                value
            )

            host = parsed.hostname

        except ValueError:
            return None

        if host is None:
            return None

        host = host.strip()

        if not host:
            return None

        protocol = (
            parsed.scheme.strip().lower()
            if parsed.scheme
            else None
        )

        return _ResolvedReference(
            target=host,
            protocol=protocol,
        )

    @classmethod
    def _parse_host_reference(
        cls,
        value: str,
    ) -> _ResolvedReference | None:
        host = cls._extract_host(
            value
        )

        if host is None:
            return None

        return _ResolvedReference(
            target=host,
            protocol=None,
        )

    @staticmethod
    def _extract_host(
        value: str,
    ) -> str | None:
        match = (
            _HOST_REFERENCE_PATTERN.fullmatch(
                value.strip()
            )
        )

        if match is None:
            return None

        host = match.group(
            "host"
        )

        return (
            host
            if host
            else None
        )