import json
from pathlib import Path

from archdrift.adapters import OtelAdapter
from archdrift.analysis import (
    canonicalize_relation_observation,
)
from archdrift.model import (
    EvidenceChannel,
    InteractionType,
    NodeType,
    NormalizedNodeObservation,
    NormalizedRelationObservation,
    RelationType,
)


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


def write_otlp(
    path: Path,
    *,
    service_name: str,
    spans: list[dict[str, object]],
) -> None:
    document = {
        "resourceSpans": [
            {
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
        ]
    }

    path.write_text(
        json.dumps(
            document
        ),
        encoding="utf-8",
    )


def client_span(
    *,
    span_id: str,
    attributes: list[
        dict[str, object]
    ],
) -> dict[str, object]:
    return {
        "traceId": "trace-001",
        "spanId": span_id,
        "name": "outgoing request",
        "kind": "SPAN_KIND_CLIENT",
        "startTimeUnixNano": "1750000000000000000",
        "attributes": attributes,
    }


def test_client_span_creates_runtime_service_call(
    tmp_path: Path,
) -> None:
    trace_file = tmp_path / "traces.json"

    write_otlp(
        trace_file,
        service_name="checkout",
        spans=[
            client_span(
                span_id="span-001",
                attributes=[
                    attribute(
                        "service.peer.name",
                        "recommendation",
                    ),
                    attribute(
                        "rpc.system.name",
                        "grpc",
                    ),
                ],
            )
        ],
    )

    observations = OtelAdapter(
        trace_file,
        artifact_id=(
            "astronomy-shop/traces.json"
        ),
    ).collect()

    relations = tuple(
        observation
        for observation in observations
        if isinstance(
            observation,
            NormalizedRelationObservation,
        )
    )

    assert len(relations) == 1

    relation = relations[0]

    assert relation.source.id == "checkout"

    assert (
        relation.target.id
        == "recommendation"
    )

    assert (
        relation.interaction
        is InteractionType.SERVICE_CALL
    )

    assert relation.protocol == "grpc"

    assert (
        relation.channel
        is EvidenceChannel.RUNTIME
    )


def test_runtime_call_canonicalizes_to_calls(
    tmp_path: Path,
) -> None:
    trace_file = tmp_path / "traces.json"

    write_otlp(
        trace_file,
        service_name="checkout",
        spans=[
            client_span(
                span_id="span-001",
                attributes=[
                    attribute(
                        "service.peer.name",
                        "recommendation",
                    ),
                    attribute(
                        "rpc.system.name",
                        "grpc",
                    ),
                ],
            )
        ],
    )

    observations = OtelAdapter(
        trace_file
    ).collect()

    relation = next(
        observation
        for observation in observations
        if isinstance(
            observation,
            NormalizedRelationObservation,
        )
    )

    candidate = (
        canonicalize_relation_observation(
            relation
        )
    )

    assert candidate.identity == (
        "checkout",
        RelationType.CALLS,
        "recommendation",
    )


def test_legacy_peer_service_is_supported(
    tmp_path: Path,
) -> None:
    trace_file = tmp_path / "traces.json"

    write_otlp(
        trace_file,
        service_name="checkout",
        spans=[
            client_span(
                span_id="span-001",
                attributes=[
                    attribute(
                        "peer.service",
                        "recommendation",
                    )
                ],
            )
        ],
    )

    observations = OtelAdapter(
        trace_file
    ).collect()

    relations = tuple(
        observation
        for observation in observations
        if isinstance(
            observation,
            NormalizedRelationObservation,
        )
    )

    assert len(relations) == 1

    assert (
        relations[0].target.id
        == "recommendation"
    )


def test_server_address_can_be_mapped_to_canonical_service(
    tmp_path: Path,
) -> None:
    trace_file = tmp_path / "traces.json"

    write_otlp(
        trace_file,
        service_name="checkoutservice",
        spans=[
            client_span(
                span_id="span-001",
                attributes=[
                    attribute(
                        "server.address",
                        "recommendationservice",
                    ),
                    attribute(
                        "url.scheme",
                        "http",
                    ),
                ],
            )
        ],
    )

    observations = OtelAdapter(
        trace_file,
        aliases={
            "checkoutservice": "checkout",
            "recommendationservice": (
                "recommendation"
            ),
        },
    ).collect()

    relation = next(
        observation
        for observation in observations
        if isinstance(
            observation,
            NormalizedRelationObservation,
        )
    )

    assert relation.source.id == "checkout"

    assert (
        relation.target.id
        == "recommendation"
    )


def test_unmapped_server_address_is_not_inferred(
    tmp_path: Path,
) -> None:
    trace_file = tmp_path / "traces.json"

    write_otlp(
        trace_file,
        service_name="checkout",
        spans=[
            client_span(
                span_id="span-001",
                attributes=[
                    attribute(
                        "server.address",
                        "api.example.com",
                    )
                ],
            )
        ],
    )

    observations = OtelAdapter(
        trace_file
    ).collect()

    relations = tuple(
        observation
        for observation in observations
        if isinstance(
            observation,
            NormalizedRelationObservation,
        )
    )

    assert relations == ()


def test_server_span_does_not_create_calls_relation(
    tmp_path: Path,
) -> None:
    trace_file = tmp_path / "traces.json"

    write_otlp(
        trace_file,
        service_name="recommendation",
        spans=[
            {
                "traceId": "trace-001",
                "spanId": "span-002",
                "name": "incoming request",
                "kind": "SPAN_KIND_SERVER",
                "attributes": [
                    attribute(
                        "client.address",
                        "checkout",
                    )
                ],
            }
        ],
    )

    observations = OtelAdapter(
        trace_file
    ).collect()

    nodes = tuple(
        observation
        for observation in observations
        if isinstance(
            observation,
            NormalizedNodeObservation,
        )
    )

    relations = tuple(
        observation
        for observation in observations
        if isinstance(
            observation,
            NormalizedRelationObservation,
        )
    )

    assert len(nodes) == 1
    assert nodes[0].endpoint.id == "recommendation"

    assert relations == ()


def test_database_client_span_is_not_misclassified_as_service_call(
    tmp_path: Path,
) -> None:
    trace_file = tmp_path / "traces.json"

    write_otlp(
        trace_file,
        service_name="checkout",
        spans=[
            client_span(
                span_id="span-001",
                attributes=[
                    attribute(
                        "service.peer.name",
                        "orders-db",
                    ),
                    attribute(
                        "db.system.name",
                        "postgresql",
                    ),
                ],
            )
        ],
    )

    observations = OtelAdapter(
        trace_file,
        node_types={
            "orders-db": NodeType.DATASTORE,
        },
    ).collect()

    relations = tuple(
        observation
        for observation in observations
        if isinstance(
            observation,
            NormalizedRelationObservation,
        )
    )

    assert relations == ()


def test_producer_span_creates_publish_observation(
    tmp_path: Path,
) -> None:
    trace_file = tmp_path / "traces.json"

    write_otlp(
        trace_file,
        service_name="checkout",
        spans=[
            {
                "traceId": "trace-001",
                "spanId": "span-001",
                "name": "publish orders",
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

    observations = OtelAdapter(
        trace_file,
        node_types={
            "kafka": NodeType.BROKER,
        },
    ).collect()

    relation = next(
        observation
        for observation in observations
        if isinstance(
            observation,
            NormalizedRelationObservation,
        )
    )

    assert (
        relation.interaction
        is InteractionType.MESSAGE_PUBLISH
    )

    assert relation.target.id == "kafka"
    assert relation.target.type is NodeType.BROKER

    candidate = (
        canonicalize_relation_observation(
            relation
        )
    )

    assert candidate.relation.relation is (
        RelationType.PUBLISHES_TO
    )


def test_consumer_span_creates_subscribe_observation(
    tmp_path: Path,
) -> None:
    trace_file = tmp_path / "traces.json"

    write_otlp(
        trace_file,
        service_name="order-worker",
        spans=[
            {
                "traceId": "trace-001",
                "spanId": "span-001",
                "name": "process orders",
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

    observations = OtelAdapter(
        trace_file,
        node_types={
            "kafka": NodeType.BROKER,
        },
    ).collect()

    relation = next(
        observation
        for observation in observations
        if isinstance(
            observation,
            NormalizedRelationObservation,
        )
    )

    assert (
        relation.interaction
        is InteractionType.MESSAGE_SUBSCRIBE
    )

    candidate = (
        canonicalize_relation_observation(
            relation
        )
    )

    assert candidate.relation.relation is (
        RelationType.SUBSCRIBES_TO
    )


def test_runtime_evidence_contains_stable_span_locator(
    tmp_path: Path,
) -> None:
    trace_file = tmp_path / "traces.json"

    write_otlp(
        trace_file,
        service_name="checkout",
        spans=[
            client_span(
                span_id="span-007",
                attributes=[
                    attribute(
                        "service.peer.name",
                        "recommendation",
                    )
                ],
            )
        ],
    )

    observations = OtelAdapter(
        trace_file,
        artifact_id=(
            "runtime/astronomy-shop/otel.json"
        ),
    ).collect()

    relation = next(
        observation
        for observation in observations
        if isinstance(
            observation,
            NormalizedRelationObservation,
        )
    )

    evidence = relation.evidence[0]

    assert (
        evidence.artifact
        == "runtime/astronomy-shop/otel.json"
    )

    assert (
        evidence.locator
        == "trace:trace-001/span:span-007"
    )

    assert (
        evidence.channel
        is EvidenceChannel.RUNTIME
    )


def test_unknown_service_is_not_promoted_to_architecture_node(
    tmp_path: Path,
) -> None:
    trace_file = tmp_path / "traces.json"

    write_otlp(
        trace_file,
        service_name="unknown_service:python",
        spans=[
            client_span(
                span_id="span-001",
                attributes=[
                    attribute(
                        "service.peer.name",
                        "recommendation",
                    )
                ],
            )
        ],
    )

    observations = OtelAdapter(
        trace_file
    ).collect()

    assert observations == ()