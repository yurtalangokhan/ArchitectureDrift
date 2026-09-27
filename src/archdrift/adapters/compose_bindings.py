from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from archdrift.model.graph import (
    NodeType,
)
from archdrift.model.source_static import (
    EndpointBinding,
)


class ComposeBindingError(
    ValueError
):
    """Raised when resolved Compose endpoint bindings cannot be read."""


def _environment_mapping(
    value: object,
) -> dict[str, str]:
    """
    Normalize Docker Compose environment syntax.

    docker compose config --format json normally emits an object,
    but list syntax is accepted defensively as well.
    """

    if value is None:
        return {}

    if isinstance(
        value,
        dict,
    ):
        result: dict[
            str,
            str,
        ] = {}

        for key, raw_value in value.items():
            if raw_value is None:
                continue

            result[
                str(key)
            ] = str(
                raw_value
            )

        return result

    if isinstance(
        value,
        list,
    ):
        result = {}

        for item in value:
            if not isinstance(
                item,
                str,
            ):
                continue

            if "=" not in item:
                continue

            key, raw_value = (
                item.split(
                    "=",
                    1,
                )
            )

            result[
                key
            ] = raw_value

        return result

    raise ComposeBindingError(
        "Compose service environment must be "
        "a mapping or a list."
    )


def _endpoint_host(
    value: str,
) -> str | None:
    """
    Extract a hostname from common service endpoint representations.

    Supported examples:

        currency:8080
        http://shipping:8080
        https://service:443/path
    """

    normalized = value.strip()

    if not normalized:
        return None

    try:
        if "://" in normalized:
            parsed = urlsplit(
                normalized
            )
        else:
            parsed = urlsplit(
                f"//{normalized}"
            )

    except ValueError:
        return None

    hostname = parsed.hostname

    if hostname is None:
        return None

    return hostname.strip()


class ComposeEndpointBindingAdapter:
    """
    Extract high-confidence service endpoint bindings from an already
    resolved Docker Compose document.

    No fuzzy service-name matching is performed.
    """

    def collect(
        self,
        *,
        result_file: Path,
        node_types: dict[
            str,
            NodeType,
        ],
    ) -> tuple[
        EndpointBinding,
        ...,
    ]:
        path = (
            result_file.resolve()
        )

        if not path.is_file():
            raise FileNotFoundError(
                f"Resolved Compose file not found: {path}"
            )

        try:
            document: Any = (
                json.loads(
                    path.read_text(
                        encoding="utf-8",
                    )
                )
            )

        except json.JSONDecodeError as exc:
            raise ComposeBindingError(
                f"Invalid resolved Compose JSON: {path}"
            ) from exc

        if not isinstance(
            document,
            dict,
        ):
            raise ComposeBindingError(
                "Resolved Compose root must be an object."
            )

        services = document.get(
            "services"
        )

        if not isinstance(
            services,
            dict,
        ):
            raise ComposeBindingError(
                "Resolved Compose document must contain "
                "a services object."
            )

        bindings: list[
            EndpointBinding
        ] = []

        seen: set[
            tuple[
                str,
                str,
                str,
            ]
        ] = set()

        for (
            source_service_id,
            service_document,
        ) in services.items():
            if (
                source_service_id
                not in node_types
            ):
                continue

            if not isinstance(
                service_document,
                dict,
            ):
                continue

            environment = (
                _environment_mapping(
                    service_document.get(
                        "environment"
                    )
                )
            )

            for (
                environment_key,
                raw_value,
            ) in environment.items():
                hostname = (
                    _endpoint_host(
                        raw_value
                    )
                )

                if hostname is None:
                    continue

                if hostname not in node_types:
                    continue

                identity = (
                    source_service_id,
                    environment_key,
                    hostname,
                )

                if identity in seen:
                    continue

                seen.add(
                    identity
                )

                bindings.append(
                    EndpointBinding(
                        source_service_id=(
                            source_service_id
                        ),
                        environment_key=(
                            environment_key
                        ),
                        target_service_id=(
                            hostname
                        ),
                        target_type=(
                            node_types[
                                hostname
                            ]
                        ),
                        raw_value=(
                            raw_value
                        ),
                    )
                )

        return tuple(
            sorted(
                bindings,
                key=lambda binding: (
                    binding.source_service_id,
                    binding.environment_key,
                    binding.target_service_id,
                ),
            )
        )