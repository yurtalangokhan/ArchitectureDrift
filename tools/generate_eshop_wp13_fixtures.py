from __future__ import annotations

import json
from pathlib import Path

import yaml


PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

NON_RUNTIME_DIR = (
    PROJECT_ROOT
    / "evidence"
    / "non-runtime"
    / "eshop"
)

RUNTIME_DIR = (
    PROJECT_ROOT
    / "evidence"
    / "runtime"
    / "eshop"
)

CASE_DIR = (
    PROJECT_ROOT
    / "cases"
    / "eshop"
)


COMPONENTS = {
    "basket-api": "SERVICE",
    "catalog-api": "SERVICE",
    "identity-api": "SERVICE",
    "ordering-api": "SERVICE",
    "order-processor": "SERVICE",
    "payment-processor": "SERVICE",
    "webhooks-api": "SERVICE",
    "webhooksclient": "SERVICE",
    "webapp": "SERVICE",
    "redis": "DATASTORE",
    "postgres": "DATASTORE",
    "eventbus": "BROKER",
}


BASELINE_CALLS = (
    (
        "webapp",
        "basket-api",
    ),
    (
        "webapp",
        "catalog-api",
    ),
    (
        "webapp",
        "ordering-api",
    ),
    (
        "webhooksclient",
        "webhooks-api",
    ),
)


NON_RUNTIME_MUTATIONS = {
    "ES-M02": (
        "webapp",
        "webhooks-api",
    ),
    "ES-M03": (
        "ordering-api",
        "catalog-api",
    ),
}


RUNTIME_CALL_MUTATIONS = {
    "ES-M01": (
        "basket-api",
        "catalog-api",
    ),
    "ES-M03": (
        "ordering-api",
        "catalog-api",
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


def write_text(
    path: Path,
    content: str,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        content.strip()
        + "\n",
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


def generate_baseline_apphost() -> None:
    write_text(
        NON_RUNTIME_DIR
        / "baseline-apphost.cs",
        """
var builder = DistributedApplication.CreateBuilder(args);

var redis = builder.AddRedis("redis");
var eventbus = builder.AddRabbitMQ("eventbus");
var postgres = builder.AddPostgres("postgres");

var identityApi =
    builder.AddProject<Projects.Identity_API>("identity-api");

var basketApi =
    builder.AddProject<Projects.Basket_API>("basket-api")
        .WithReference(redis)
        .WithReference(eventbus);

var catalogApi =
    builder.AddProject<Projects.Catalog_API>("catalog-api")
        .WithReference(eventbus);

var orderingApi =
    builder.AddProject<Projects.Ordering_API>("ordering-api")
        .WithReference(eventbus);

builder
    .AddProject<Projects.OrderProcessor>("order-processor")
    .WithReference(eventbus);

builder
    .AddProject<Projects.PaymentProcessor>("payment-processor")
    .WithReference(eventbus);

var webhooksApi =
    builder.AddProject<Projects.Webhooks_API>("webhooks-api")
        .WithReference(eventbus);

var webhooksClient =
    builder.AddProject<Projects.WebhookClient>("webhooksclient")
        .WithReference(webhooksApi);

var webapp =
    builder.AddProject<Projects.WebApp>("webapp")
        .WithReference(basketApi)
        .WithReference(catalogApi)
        .WithReference(orderingApi)
        .WithReference(eventbus);

builder.Build().Run();
""",
    )


def mutation_apphost(
    *,
    source: str,
    target: str,
) -> str:
    source_variable = (
        source.replace(
            "-",
            "_",
        )
    )

    target_variable = (
        target.replace(
            "-",
            "_",
        )
    )

    return f"""
var builder = DistributedApplication.CreateBuilder(args);

var {target_variable} =
    builder.AddProject<Projects.Target>("{target}");

var {source_variable} =
    builder.AddProject<Projects.Source>("{source}")
        .WithReference({target_variable});

builder.Build().Run();
"""


def generate_non_runtime_mutations() -> None:
    for mutation_id, (
        source,
        target,
    ) in NON_RUNTIME_MUTATIONS.items():
        write_text(
            NON_RUNTIME_DIR
            / f"{mutation_id}-apphost.cs",
            mutation_apphost(
                source=source,
                target=target,
            ),
        )


def client_span(
    *,
    source: str,
    target: str,
    span_id: str,
) -> dict[str, object]:
    return {
        "traceId": (
            f"trace-{source}-{target}"
        ),
        "spanId": span_id,
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
                "rpc.system.name",
                "http",
            ),
        ],
    }


def internal_span(
    node_id: str,
) -> dict[str, object]:
    return {
        "traceId": (
            f"trace-presence-{node_id}"
        ),
        "spanId": (
            f"span-presence-{node_id}"
        ),
        "name": "runtime presence",
        "kind": "SPAN_KIND_INTERNAL",
        "attributes": [],
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
    spans_by_source: dict[
        str,
        list[dict[str, object]],
    ] = {
        node_id: [
            internal_span(
                node_id
            )
        ]
        for node_id in COMPONENTS
    }

    for index, (
        source,
        target,
    ) in enumerate(
        BASELINE_CALLS,
        start=1,
    ):
        spans_by_source[
            source
        ].append(
            client_span(
                source=source,
                target=target,
                span_id=(
                    f"span-call-{index:03d}"
                ),
            )
        )

    document = {
        "resourceSpans": [
            resource_span(
                service_name=node_id,
                spans=spans,
            )
            for node_id, spans in sorted(
                spans_by_source.items()
            )
        ]
    }

    write_json(
        RUNTIME_DIR
        / "baseline-otel.json",
        document,
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
                        service_name=source,
                        spans=[
                            client_span(
                                source=source,
                                target=target,
                                span_id=(
                                    f"span-{index}"
                                ),
                            )
                        ],
                    )
                ]
            },
        )


def generate_runtime_messaging_mutation() -> None:
    write_json(
        RUNTIME_DIR
        / "ES-M05-otel.json",
        {
            "resourceSpans": [
                resource_span(
                    service_name="webapp",
                    spans=[
                        {
                            "traceId": (
                                "trace-ES-M05"
                            ),
                            "spanId": (
                                "span-ES-M05"
                            ),
                            "name": (
                                "unexpected eventbus consume"
                            ),
                            "kind": (
                                "SPAN_KIND_CONSUMER"
                            ),
                            "attributes": [
                                attribute(
                                    "messaging.system",
                                    "rabbitmq",
                                ),
                                attribute(
                                    "server.address",
                                    "eventbus",
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
    aspire_files = [
        (
            "evidence/non-runtime/eshop/"
            "baseline-apphost.cs"
        )
    ]

    if mutation_id in NON_RUNTIME_MUTATIONS:
        aspire_files.append(
            (
                "evidence/non-runtime/eshop/"
                f"{mutation_id}-apphost.cs"
            )
        )

    otlp_files = [
        (
            "evidence/runtime/eshop/"
            "baseline-otel.json"
        )
    ]

    if mutation_id in {
        "ES-M01",
        "ES-M03",
        "ES-M05",
    }:
        otlp_files.append(
            (
                "evidence/runtime/eshop/"
                f"{mutation_id}-otel.json"
            )
        )

    return {
        "schema_version": "1.0",
        "case_id": (
            f"eshop-{mutation_id}"
        ),
        "system_id": "eshop",
        "variant": mutation_id,
        "baseline_graph": (
            "graphs/baseline/eshop/"
            "baseline.yaml"
        ),
        "contract_document": (
            "contracts/eshop.yaml"
        ),
        "mutation_oracle": (
            "mutations/eshop/"
            f"{mutation_id}.yaml"
        ),
        "components": [
            {
                "id": component_id,
                "type": component_type,
            }
            for component_id, component_type
            in COMPONENTS.items()
        ],
        "non_runtime": {
            "aspire_files": (
                aspire_files
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
        "ES-M01",
        "ES-M02",
        "ES-M03",
        "ES-M04",
        "ES-M05",
    ):
        write_yaml(
            CASE_DIR
            / f"{mutation_id}.yaml",
            case_document(
                mutation_id
            ),
        )


def main() -> None:
    generate_baseline_apphost()

    generate_non_runtime_mutations()

    generate_baseline_runtime()

    generate_runtime_call_mutations()

    generate_runtime_messaging_mutation()

    generate_cases()


if __name__ == "__main__":
    main()