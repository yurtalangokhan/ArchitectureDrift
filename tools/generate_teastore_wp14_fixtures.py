from __future__ import annotations

import json
from pathlib import Path

import yaml


PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)

NON_RUNTIME_DIR = (
    PROJECT_ROOT
    / "evidence"
    / "non-runtime"
    / "teastore"
)

RUNTIME_DIR = (
    PROJECT_ROOT
    / "evidence"
    / "runtime"
    / "teastore"
)

CASE_DIR = (
    PROJECT_ROOT
    / "cases"
    / "teastore"
)


COMPONENTS = {
    "webui": "SERVICE",
    "auth": "SERVICE",
    "recommender": "SERVICE",
    "persistence": "SERVICE",
    "image": "SERVICE",
    "registry": "REGISTRY",
    "database": "DATASTORE",
}


DISCOVERY_SERVICES = (
    "webui",
    "auth",
    "recommender",
    "persistence",
    "image",
)


NON_RUNTIME_MUTATIONS = {
    "TS-M02": (
        "auth",
        "image",
    ),
    "TS-M03": (
        "recommender",
        "auth",
    ),
}


RUNTIME_CALL_MUTATIONS = {
    "TS-M01": (
        "webui",
        "persistence",
    ),
    "TS-M03": (
        "recommender",
        "auth",
    ),
    "TS-M05": (
        "webui",
        "registry",
    ),
}


def attribute(
    key: str,
    value: str,
) -> dict[str, object]:
    return {
        "key": key,
        "value": {
            "stringValue": value,
        },
    }


def write_yaml(
    path: Path,
    document: object,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        yaml.safe_dump(
            document,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def write_json(
    path: Path,
    document: object,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            document,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def generate_baseline_compose() -> None:
    services: dict[str, object] = {
        "registry": {
            "image": (
                "descartesresearch/"
                "teastore-registry"
            )
        },
        "database": {
            "image": (
                "descartesresearch/"
                "teastore-db"
            )
        },
    }

    for service in DISCOVERY_SERVICES:
        environment = {
            "REGISTRY_HOST": "registry",
            "REGISTRY_PORT": "8080",
        }

        if service == "persistence":
            environment.update(
                {
                    "DB_HOST": "database",
                    "DB_PORT": "3306",
                }
            )

        services[service] = {
            "image": (
                "descartesresearch/"
                f"teastore-{service}"
            ),
            "environment": environment,
        }

    write_yaml(
        NON_RUNTIME_DIR
        / "baseline-compose.yaml",
        {
            "services": services,
        },
    )


def generate_non_runtime_mutations() -> None:
    for mutation_id, (
        source,
        target,
    ) in NON_RUNTIME_MUTATIONS.items():
        write_yaml(
            NON_RUNTIME_DIR
            / f"{mutation_id}-overlay.yaml",
            {
                "services": {
                    source: {
                        "environment": {
                            "ARCHDRIFT_DIRECT_TARGET": (
                                f"http://{target}:8080"
                            )
                        }
                    },
                    target: {},
                }
            },
        )


def internal_span(
    node_id: str,
) -> dict[str, object]:
    return {
        "traceId": (
            f"baseline-{node_id}"
        ),
        "spanId": (
            f"span-{node_id}"
        ),
        "name": "runtime presence",
        "kind": "SPAN_KIND_INTERNAL",
        "attributes": [],
    }


def client_span(
    *,
    source: str,
    target: str,
    index: int,
) -> dict[str, object]:
    return {
        "traceId": (
            f"mutation-{source}-{target}"
        ),
        "spanId": (
            f"span-{index:04d}"
        ),
        "name": (
            f"{source} to {target}"
        ),
        "kind": "SPAN_KIND_CLIENT",
        "attributes": [
            attribute(
                "service.peer.name",
                target,
            ),
            attribute(
                "url.scheme",
                "http",
            ),
        ],
    }


def resource_span(
    *,
    service_name: str,
    spans: list[
        dict[str, object]
    ],
) -> dict[str, object]:
    return {
        "resource": {
            "attributes": [
                attribute(
                    "service.name",
                    service_name,
                )
            ]
        },
        "scopeSpans": [
            {
                "spans": spans,
            }
        ],
    }


def generate_baseline_runtime() -> None:
    write_json(
        RUNTIME_DIR
        / "baseline-otel.json",
        {
            "resourceSpans": [
                resource_span(
                    service_name=node_id,
                    spans=[
                        internal_span(
                            node_id
                        )
                    ],
                )
                for node_id in COMPONENTS
            ]
        },
    )


def generate_runtime_mutations() -> None:
    for index, (
        mutation_id,
        (
            source,
            target,
        ),
    ) in enumerate(
        sorted(
            RUNTIME_CALL_MUTATIONS.items()
        ),
        start=100,
    ):
        write_json(
            RUNTIME_DIR
            / f"{mutation_id}-otel.json",
            {
                "resourceSpans": [
                    resource_span(
                        service_name=source,
                        spans=[
                            client_span(
                                source=source,
                                target=target,
                                index=index,
                            )
                        ],
                    )
                ]
            },
        )


def case_document(
    mutation_id: str,
) -> dict[str, object]:
    compose_files = [
        (
            "evidence/non-runtime/"
            "teastore/baseline-compose.yaml"
        )
    ]

    if (
        mutation_id
        in NON_RUNTIME_MUTATIONS
    ):
        compose_files.append(
            (
                "evidence/non-runtime/"
                "teastore/"
                f"{mutation_id}-overlay.yaml"
            )
        )

    otlp_files = [
        (
            "evidence/runtime/"
            "teastore/baseline-otel.json"
        )
    ]

    if (
        mutation_id
        in RUNTIME_CALL_MUTATIONS
    ):
        otlp_files.append(
            (
                "evidence/runtime/"
                "teastore/"
                f"{mutation_id}-otel.json"
            )
        )

    return {
        "schema_version": "1.0",
        "case_id": (
            f"teastore-{mutation_id}"
        ),
        "system_id": "teastore",
        "variant": mutation_id,
        "baseline_graph": (
            "graphs/baseline/"
            "teastore/baseline.yaml"
        ),
        "contract_document": (
            "contracts/teastore.yaml"
        ),
        "mutation_oracle": (
            "mutations/teastore/"
            f"{mutation_id}.yaml"
        ),
        "components": [
            {
                "id": component_id,
                "type": component_type,
            }
            for (
                component_id,
                component_type,
            ) in COMPONENTS.items()
        ],
        "non_runtime": {
            "compose_files": (
                compose_files
            ),
        },
        "runtime": {
            "otlp_files": (
                otlp_files
            ),
        },
    }


def generate_cases() -> None:
    for mutation_id in (
        "TS-M01",
        "TS-M02",
        "TS-M03",
        "TS-M04",
        "TS-M05",
    ):
        write_yaml(
            CASE_DIR
            / f"{mutation_id}.yaml",
            case_document(
                mutation_id
            ),
        )


def main() -> None:
    generate_baseline_compose()

    generate_non_runtime_mutations()

    generate_baseline_runtime()

    generate_runtime_mutations()

    generate_cases()


if __name__ == "__main__":
    main()