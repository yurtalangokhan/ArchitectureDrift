from __future__ import annotations

import json
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]

NON_RUNTIME_DIR = (
    PROJECT_ROOT
    / "evidence"
    / "non-runtime"
    / "astronomy-shop"
)

RUNTIME_DIR = (
    PROJECT_ROOT
    / "evidence"
    / "runtime"
    / "astronomy-shop"
)

CASE_DIR = (
    PROJECT_ROOT
    / "cases"
    / "astronomy-shop"
)


SERVICES = {
    "ad": "SERVICE",
    "cart": "SERVICE",
    "checkout": "SERVICE",
    "currency": "SERVICE",
    "email": "SERVICE",
    "frontend": "SERVICE",
    "kafka": "BROKER",
    "payment": "SERVICE",
    "product-catalog": "SERVICE",
    "quote": "SERVICE",
    "recommendation": "SERVICE",
    "shipping": "SERVICE",
}


BASELINE_CALLS = (
    ("frontend", "ad", "grpc"),
    ("frontend", "recommendation", "grpc"),
    ("frontend", "product-catalog", "grpc"),
    ("frontend", "cart", "grpc"),
    ("frontend", "checkout", "grpc"),
    ("checkout", "cart", "grpc"),
    ("checkout", "payment", "grpc"),
    ("checkout", "shipping", "http"),
    ("checkout", "email", "http"),
    ("checkout", "product-catalog", "grpc"),
    ("checkout", "currency", "grpc"),
    ("recommendation", "product-catalog", "grpc"),
    ("shipping", "quote", "http"),
)


NON_RUNTIME_MUTATIONS = {
    "AS-M02": (
        "payment",
        "shipping",
    ),
    "AS-M03": (
        "frontend",
        "payment",
    ),
}


RUNTIME_CALL_MUTATIONS = {
    "AS-M01": (
        "checkout",
        "recommendation",
    ),
    "AS-M03": (
        "frontend",
        "payment",
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


def client_span(
    source: str,
    target: str,
    index: int,
    protocol: str,
) -> dict[str, object]:
    attributes = [
        attribute(
            "service.peer.name",
            target,
        )
    ]

    if protocol == "grpc":
        attributes.append(
            attribute(
                "rpc.system.name",
                "grpc",
            )
        )

    else:
        attributes.append(
            attribute(
                "url.scheme",
                "http",
            )
        )

    return {
        "traceId": f"baseline-{source}-{target}",
        "spanId": f"span-{index:04d}",
        "name": f"{source} to {target}",
        "kind": "SPAN_KIND_CLIENT",
        "attributes": attributes,
    }


def resource_span(
    service: str,
    spans: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "resource": {
            "attributes": [
                attribute(
                    "service.name",
                    service,
                )
            ]
        },
        "scopeSpans": [
            {
                "spans": spans,
            }
        ],
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
        service: {}
        for service in SERVICES
    }

    environment_by_source: dict[
        str,
        dict[str, str],
    ] = {}

    for index, (
        source,
        target,
        _,
    ) in enumerate(
        BASELINE_CALLS,
        start=1,
    ):
        environment_by_source.setdefault(
            source,
            {},
        )[
            f"ARCHDRIFT_TARGET_{index:02d}"
        ] = f"http://{target}:8080"

    for source, environment in (
        environment_by_source.items()
    ):
        services[source] = {
            "environment": environment,
        }

    write_yaml(
        NON_RUNTIME_DIR
        / "baseline-compose.yaml",
        {
            "services": services,
        },
    )


def generate_non_runtime_overlays() -> None:
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
                            "ARCHDRIFT_MUTATION_TARGET": (
                                f"http://{target}:8080"
                            )
                        }
                    },
                    target: {},
                }
            },
        )


def generate_baseline_otlp() -> None:
    spans_by_source: dict[
        str,
        list[dict[str, object]],
    ] = {}

    for index, (
        source,
        target,
        protocol,
    ) in enumerate(
        BASELINE_CALLS,
        start=1,
    ):
        spans_by_source.setdefault(
            source,
            [],
        ).append(
            client_span(
                source,
                target,
                index,
                protocol,
            )
        )

    resource_spans = [
        resource_span(
            source,
            spans,
        )
        for source, spans in sorted(
            spans_by_source.items()
        )
    ]

    # Keep Kafka visible as a reconstructed node even though baseline
    # messaging relations are outside this synchronous baseline.
    resource_spans.append(
        resource_span(
            "kafka",
            [
                {
                    "traceId": "baseline-kafka",
                    "spanId": "span-kafka-0001",
                    "name": "kafka runtime presence",
                    "kind": "SPAN_KIND_INTERNAL",
                    "attributes": [],
                }
            ],
        )
    )

    write_json(
        RUNTIME_DIR
        / "baseline-otel.json",
        {
            "resourceSpans": resource_spans,
        },
    )


def generate_runtime_call_mutations() -> None:
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
                        source,
                        [
                            client_span(
                                source,
                                target,
                                index,
                                "grpc",
                            )
                        ],
                    )
                ]
            },
        )


def generate_runtime_messaging_mutations() -> None:
    write_json(
        RUNTIME_DIR
        / "AS-M05-otel.json",
        {
            "resourceSpans": [
                resource_span(
                    "frontend",
                    [
                        {
                            "traceId": "AS-M05-trace",
                            "spanId": "AS-M05-span",
                            "name": "unexpected kafka publish",
                            "kind": "SPAN_KIND_PRODUCER",
                            "attributes": [
                                attribute(
                                    "messaging.system",
                                    "kafka",
                                ),
                                attribute(
                                    "server.address",
                                    "kafka",
                                ),
                                attribute(
                                    "messaging.operation.type",
                                    "send",
                                ),
                            ],
                        }
                    ],
                )
            ]
        },
    )

    write_json(
        RUNTIME_DIR
        / "AS-M06-otel.json",
        {
            "resourceSpans": [
                resource_span(
                    "checkout",
                    [
                        {
                            "traceId": "AS-M06-trace",
                            "spanId": "AS-M06-span",
                            "name": "unexpected kafka consume",
                            "kind": "SPAN_KIND_CONSUMER",
                            "attributes": [
                                attribute(
                                    "messaging.system",
                                    "kafka",
                                ),
                                attribute(
                                    "server.address",
                                    "kafka",
                                ),
                                attribute(
                                    "messaging.operation.type",
                                    "process",
                                ),
                            ],
                        }
                    ],
                )
            ]
        },
    )


def case_document(
    mutation_id: str,
) -> dict[str, object]:
    compose_files = [
        "evidence/non-runtime/astronomy-shop/baseline-compose.yaml"
    ]

    if mutation_id in NON_RUNTIME_MUTATIONS:
        compose_files.append(
            "evidence/non-runtime/astronomy-shop/"
            f"{mutation_id}-overlay.yaml"
        )

    otlp_files = [
        "evidence/runtime/astronomy-shop/baseline-otel.json"
    ]

    if mutation_id in {
        "AS-M01",
        "AS-M03",
        "AS-M05",
        "AS-M06",
    }:
        otlp_files.append(
            "evidence/runtime/astronomy-shop/"
            f"{mutation_id}-otel.json"
        )

    return {
        "schema_version": "1.0",
        "case_id": (
            f"astronomy-shop-{mutation_id}"
        ),
        "system_id": "astronomy-shop",
        "variant": mutation_id,
        "baseline_graph": (
            "graphs/baseline/astronomy-shop/baseline.yaml"
        ),
        "contract_document": (
            "contracts/astronomy-shop.yaml"
        ),
        "mutation_oracle": (
            "mutations/astronomy-shop/"
            f"{mutation_id}.yaml"
        ),
        "components": [
            {
                "id": component_id,
                "type": component_type,
            }
            for component_id, component_type in (
                SERVICES.items()
            )
        ],
        "non_runtime": {
            "compose_files": compose_files,
        },
        "runtime": {
            "otlp_files": otlp_files,
        },
    }


def generate_cases() -> None:
    for mutation_id in (
        "AS-M01",
        "AS-M02",
        "AS-M03",
        "AS-M04",
        "AS-M05",
        "AS-M06",
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
    generate_non_runtime_overlays()

    generate_baseline_otlp()
    generate_runtime_call_mutations()
    generate_runtime_messaging_mutations()

    generate_cases()


if __name__ == "__main__":
    main()