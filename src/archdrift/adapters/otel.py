from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

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

from collections.abc import Hashable, Mapping
from typing import TypeVar, cast

# =============================================================================
# Exceptions
# =============================================================================


class OtelAdapterError(ValueError):
    """Raised when OpenTelemetry runtime evidence cannot be parsed."""


# =============================================================================
# Span Vocabulary
# =============================================================================


class OtelSpanKind(StrEnum):
    INTERNAL = "INTERNAL"
    SERVER = "SERVER"
    CLIENT = "CLIENT"
    PRODUCER = "PRODUCER"
    CONSUMER = "CONSUMER"


_OTLP_SPAN_KIND_BY_NUMBER: dict[int, OtelSpanKind] = {
    1: OtelSpanKind.INTERNAL,
    2: OtelSpanKind.SERVER,
    3: OtelSpanKind.CLIENT,
    4: OtelSpanKind.PRODUCER,
    5: OtelSpanKind.CONSUMER,
}


# =============================================================================
# Internal Parsed Span
# =============================================================================


@dataclass(
    frozen=True,
    slots=True,
)
class _ParsedSpan:
    trace_id: str
    span_id: str
    name: str
    kind: OtelSpanKind

    resource_attributes: Mapping[str, object]
    attributes: Mapping[str, object]

    observed_at: datetime | None


# =============================================================================
# Relation Aggregation Key
# =============================================================================


@dataclass(
    frozen=True,
    slots=True,
)
class _RelationObservationKey:
    source_id: str
    source_type: NodeType

    target_id: str
    target_type: NodeType

    interaction: InteractionType

    protocol: str | None


_EvidenceKey = TypeVar(
    "_EvidenceKey",
    bound=Hashable,
)

# =============================================================================
# OTLP JSON Helpers
# =============================================================================


def _mapping(
    value: object,
) -> Mapping[str, object] | None:
    if not isinstance(value, dict):
        return None

    return cast(
        Mapping[str, object],
        value,
    )


def _sequence(
    value: object,
) -> list[object]:
    if not isinstance(value, list):
        return []

    return cast(
        list[object],
        value,
    )


def _decode_any_value(
    value: object,
) -> object:
    """
    Decode an OTLP JSON AnyValue.

    OTLP JSON represents attribute values using keys such as:

        stringValue
        boolValue
        intValue
        doubleValue
        arrayValue
        kvlistValue
    """

    mapping = _mapping(value)

    if mapping is None:
        return value

    if "stringValue" in mapping:
        return mapping["stringValue"]

    if "boolValue" in mapping:
        return mapping["boolValue"]

    if "intValue" in mapping:
        raw = mapping["intValue"]

        if isinstance(raw, int):
            return raw

        if isinstance(raw, str):
            try:
                return int(raw)
            except ValueError:
                return raw

        return raw

    if "doubleValue" in mapping:
        return mapping["doubleValue"]

    if "bytesValue" in mapping:
        return mapping["bytesValue"]

    array_value = _mapping(mapping.get("arrayValue"))

    if array_value is not None:
        return tuple(
            _decode_any_value(item) for item in _sequence(array_value.get("values"))
        )

    kvlist_value = _mapping(mapping.get("kvlistValue"))

    if kvlist_value is not None:
        return _decode_attributes(kvlist_value.get("values"))

    return mapping


def _decode_attributes(
    raw_attributes: object,
) -> dict[str, object]:
    result: dict[str, object] = {}

    for raw_attribute in _sequence(raw_attributes):
        attribute = _mapping(raw_attribute)

        if attribute is None:
            continue

        key = attribute.get("key")

        if not isinstance(
            key,
            str,
        ):
            continue

        result[key] = _decode_any_value(attribute.get("value"))

    return result


def _string_attribute(
    attributes: Mapping[str, object],
    key: str,
) -> str | None:
    value = attributes.get(key)

    if not isinstance(
        value,
        str,
    ):
        return None

    normalized = value.strip()

    if not normalized:
        return None

    return normalized


def _first_string_attribute(
    attributes: Mapping[str, object],
    *keys: str,
) -> str | None:
    for key in keys:
        value = _string_attribute(
            attributes,
            key,
        )

        if value is not None:
            return value

    return None


def _parse_span_kind(
    raw_kind: object,
) -> OtelSpanKind | None:
    if isinstance(
        raw_kind,
        int,
    ):
        return _OTLP_SPAN_KIND_BY_NUMBER.get(raw_kind)

    if not isinstance(
        raw_kind,
        str,
    ):
        return None

    normalized = raw_kind.strip().upper()

    if normalized.startswith("SPAN_KIND_"):
        normalized = normalized[len("SPAN_KIND_") :]

    try:
        return OtelSpanKind(normalized)

    except ValueError:
        return None


def _parse_timestamp(
    value: object,
) -> datetime | None:
    if value is None:
        return None

    nanoseconds: int

    if isinstance(
        value,
        int,
    ):
        nanoseconds = value

    elif isinstance(
        value,
        str,
    ):
        try:
            nanoseconds = int(value)
        except ValueError:
            return None

    else:
        return None

    return datetime.fromtimestamp(
        nanoseconds / 1_000_000_000,
        tz=UTC,
    )


def _required_span_identifier(
    span: Mapping[str, object],
    *keys: str,
) -> str:
    for key in keys:
        value = span.get(key)

        if isinstance(
            value,
            str,
        ):
            normalized = value.strip()

            if normalized:
                return normalized

    raise OtelAdapterError(f"OTLP span is missing required identifier: {keys[0]}")


# =============================================================================
# Adapter
# =============================================================================


class OtelAdapter:
    """
    Convert OTLP JSON trace data into normalized runtime observations.

    Conservative inference policy:

    - resource service.name identifies the local/source architecture node;
    - CLIENT spans may produce SERVICE_CALL observations;
    - SERVER spans do not independently produce CALLS relations;
    - PRODUCER messaging spans may produce MESSAGE_PUBLISH observations;
    - CONSUMER/receive messaging spans may produce MESSAGE_SUBSCRIBE;
    - generic database CLIENT spans are not classified as service calls;
    - unresolved arbitrary server.address values are ignored by default.

    This adapter never constructs ArchitectureGraph directly.
    """

    def __init__(
        self,
        trace_file: str | Path,
        *,
        artifact_id: str | None = None,
        aliases: Mapping[str, str] | None = None,
        node_types: Mapping[str, NodeType] | None = None,
        allow_unmapped_server_addresses: bool = False,
    ) -> None:
        self._trace_file = Path(trace_file)

        self._artifact_id = (
            artifact_id if artifact_id is not None else self._trace_file.name
        )

        self._aliases = dict(aliases if aliases is not None else {})

        self._node_types = dict(node_types if node_types is not None else {})

        self._allow_unmapped_server_addresses = allow_unmapped_server_addresses

    # =========================================================================
    # Public API
    # =========================================================================

    def collect(
        self,
    ) -> tuple[NormalizedObservation, ...]:
        spans = self._load_spans()

        node_evidence: dict[
            tuple[str, NodeType],
            list[EvidenceRecord],
        ] = {}

        relation_evidence: dict[
            _RelationObservationKey,
            list[EvidenceRecord],
        ] = {}

        for span in spans:
            source_id = self._resolve_source_service(span)

            if source_id is None:
                continue

            source_type = self._node_types.get(
                source_id,
                NodeType.SERVICE,
            )

            evidence = self._span_evidence(span)

            self._append_evidence(
                node_evidence,
                (
                    source_id,
                    source_type,
                ),
                evidence,
            )

            relation_key = self._relation_key(
                span=span,
                source_id=source_id,
                source_type=source_type,
            )

            if relation_key is None:
                continue

            self._append_evidence(
                node_evidence,
                (
                    relation_key.target_id,
                    relation_key.target_type,
                ),
                evidence,
            )

            self._append_evidence(
                relation_evidence,
                relation_key,
                evidence,
            )

        observations: list[NormalizedObservation] = []

        for (
            node_id,
            node_type,
        ), evidence_records in sorted(
            node_evidence.items(),
            key=lambda item: (
                item[0][0],
                item[0][1].value,
            ),
        ):
            observations.append(
                NormalizedNodeObservation(
                    endpoint=NormalizedEndpoint(
                        id=node_id,
                        type=node_type,
                    ),
                    evidence=tuple(evidence_records),
                )
            )

        for key, evidence_records in sorted(
            relation_evidence.items(),
            key=lambda item: (
                item[0].source_id,
                item[0].interaction.value,
                item[0].target_id,
                item[0].protocol or "",
            ),
        ):
            observations.append(
                NormalizedRelationObservation(
                    source=NormalizedEndpoint(
                        id=key.source_id,
                        type=key.source_type,
                    ),
                    target=NormalizedEndpoint(
                        id=key.target_id,
                        type=key.target_type,
                    ),
                    interaction=key.interaction,
                    protocol=key.protocol,
                    evidence=tuple(evidence_records),
                )
            )

        return tuple(observations)

    # =========================================================================
    # Span Loading
    # =========================================================================

    def _load_spans(
        self,
    ) -> tuple[_ParsedSpan, ...]:
        if not self._trace_file.is_file():
            raise OtelAdapterError(f"OTLP trace file not found: {self._trace_file}")

        try:
            with self._trace_file.open(
                "r",
                encoding="utf-8",
            ) as file:
                raw_document: object = json.load(file)

        except json.JSONDecodeError as exc:
            raise OtelAdapterError(f"Invalid OTLP JSON: {self._trace_file}") from exc

        document = _mapping(raw_document)

        if document is None:
            raise OtelAdapterError("OTLP JSON root must be an object.")

        raw_resource_spans = document.get(
            "resourceSpans",
            document.get("resource_spans"),
        )

        resource_spans = _sequence(raw_resource_spans)

        if not resource_spans:
            raise OtelAdapterError("OTLP JSON does not contain resourceSpans.")

        parsed: list[_ParsedSpan] = []

        for raw_resource_span in resource_spans:
            resource_span = _mapping(raw_resource_span)

            if resource_span is None:
                continue

            resource = _mapping(resource_span.get("resource"))

            resource_attributes = (
                _decode_attributes(resource.get("attributes"))
                if resource is not None
                else {}
            )

            raw_scope_spans = resource_span.get(
                "scopeSpans",
                resource_span.get(
                    "scope_spans",
                    resource_span.get(
                        "instrumentationLibrarySpans",
                    ),
                ),
            )

            for raw_scope_span in _sequence(raw_scope_spans):
                scope_span = _mapping(raw_scope_span)

                if scope_span is None:
                    continue

                for raw_span in _sequence(scope_span.get("spans")):
                    span = _mapping(raw_span)

                    if span is None:
                        continue

                    parsed_span = self._parse_span(
                        span,
                        resource_attributes,
                    )

                    if parsed_span is not None:
                        parsed.append(parsed_span)

        return tuple(parsed)

    @staticmethod
    def _parse_span(
        span: Mapping[str, object],
        resource_attributes: Mapping[str, object],
    ) -> _ParsedSpan | None:
        kind = _parse_span_kind(span.get("kind"))

        if kind is None:
            return None

        trace_id = _required_span_identifier(
            span,
            "traceId",
            "trace_id",
        )

        span_id = _required_span_identifier(
            span,
            "spanId",
            "span_id",
        )

        raw_name = span.get("name")

        name = (
            raw_name.strip()
            if isinstance(
                raw_name,
                str,
            )
            else ""
        )

        attributes = _decode_attributes(span.get("attributes"))

        observed_at = _parse_timestamp(
            span.get(
                "startTimeUnixNano",
                span.get("start_time_unix_nano"),
            )
        )

        return _ParsedSpan(
            trace_id=trace_id,
            span_id=span_id,
            name=name,
            kind=kind,
            resource_attributes=dict(resource_attributes),
            attributes=attributes,
            observed_at=observed_at,
        )

    # =========================================================================
    # Identity Resolution
    # =========================================================================

    def _canonical_name(
        self,
        raw_name: str,
    ) -> str:
        normalized = raw_name.strip()

        return self._aliases.get(
            normalized,
            normalized,
        )

    def _resolve_source_service(
        self,
        span: _ParsedSpan,
    ) -> str | None:
        service_name = _string_attribute(
            span.resource_attributes,
            "service.name",
        )

        if service_name is None:
            return None

        # OpenTelemetry SDK fallback values do not represent a useful
        # architecture-level service identity.
        if service_name == "unknown_service" or service_name.startswith(
            "unknown_service:"
        ):
            return None

        return self._canonical_name(service_name)

    def _resolve_target(
        self,
        span: _ParsedSpan,
    ) -> str | None:
        # Current semantic-convention field.
        peer_name = _string_attribute(
            span.attributes,
            "service.peer.name",
        )

        if peer_name is not None:
            return self._canonical_name(peer_name)

        # Backward compatibility for older instrumentation.
        legacy_peer = _string_attribute(
            span.attributes,
            "peer.service",
        )

        if legacy_peer is not None:
            return self._canonical_name(legacy_peer)

        server_address = _string_attribute(
            span.attributes,
            "server.address",
        )

        if server_address is None:
            return None

        if server_address in self._aliases:
            return self._aliases[server_address]

        canonical_address = self._canonical_name(server_address)

        if canonical_address in self._node_types:
            return canonical_address

        if self._allow_unmapped_server_addresses:
            return canonical_address

        return None

    # =========================================================================
    # Relation Classification
    # =========================================================================

    def _relation_key(
        self,
        *,
        span: _ParsedSpan,
        source_id: str,
        source_type: NodeType,
    ) -> _RelationObservationKey | None:
        if self._is_messaging_span(span):
            return self._messaging_relation_key(
                span=span,
                source_id=source_id,
                source_type=source_type,
            )

        if span.kind is not OtelSpanKind.CLIENT:
            # SERVER spans describe the receiving side and would otherwise
            # duplicate or invert outgoing CALLS observations.
            return None

        if self._is_database_span(span):
            # A generic DB client span does not tell us whether the operation
            # should be modeled as READS_FROM or WRITES_TO without additional
            # semantic classification.
            return None

        target_id = self._resolve_target(span)

        if target_id is None:
            return None

        if target_id == source_id:
            return None

        target_type = self._node_types.get(
            target_id,
            NodeType.SERVICE,
        )

        if target_type in {
            NodeType.DATASTORE,
            NodeType.BROKER,
        }:
            # Do not misclassify DB/broker access as synchronous service CALLS.
            return None

        return _RelationObservationKey(
            source_id=source_id,
            source_type=source_type,
            target_id=target_id,
            target_type=target_type,
            interaction=InteractionType.SERVICE_CALL,
            protocol=self._protocol(span),
        )

    def _messaging_relation_key(
        self,
        *,
        span: _ParsedSpan,
        source_id: str,
        source_type: NodeType,
    ) -> _RelationObservationKey | None:
        target_id = self._resolve_target(span)

        if target_id is None:
            return None

        if target_id == source_id:
            return None

        operation = _first_string_attribute(
            span.attributes,
            "messaging.operation.type",
            "messaging.operation.name",
        )

        normalized_operation = operation.lower() if operation is not None else None

        interaction: InteractionType | None = None

        if span.kind is OtelSpanKind.PRODUCER:
            interaction = InteractionType.MESSAGE_PUBLISH

        elif span.kind is OtelSpanKind.CONSUMER:
            interaction = InteractionType.MESSAGE_SUBSCRIBE

        elif normalized_operation in {
            "send",
            "publish",
        }:
            interaction = InteractionType.MESSAGE_PUBLISH

        elif normalized_operation in {
            "receive",
            "process",
            "subscribe",
        }:
            interaction = InteractionType.MESSAGE_SUBSCRIBE

        if interaction is None:
            return None

        target_type = self._node_types.get(
            target_id,
            NodeType.BROKER,
        )

        if target_type is not NodeType.BROKER:
            return None

        return _RelationObservationKey(
            source_id=source_id,
            source_type=source_type,
            target_id=target_id,
            target_type=target_type,
            interaction=interaction,
            protocol=self._protocol(span),
        )

    # =========================================================================
    # Semantic Helpers
    # =========================================================================

    @staticmethod
    def _is_database_span(
        span: _ParsedSpan,
    ) -> bool:
        return "db.system.name" in span.attributes or "db.system" in span.attributes

    @staticmethod
    def _is_messaging_span(
        span: _ParsedSpan,
    ) -> bool:
        return "messaging.system" in span.attributes

    @staticmethod
    def _protocol(
        span: _ParsedSpan,
    ) -> str | None:
        return _first_string_attribute(
            span.attributes,
            # Current RPC semantic convention.
            "rpc.system.name",
            # Compatibility with older instrumentation.
            "rpc.system",
            "url.scheme",
            "network.protocol.name",
            "messaging.system",
        )

    # =========================================================================
    # Evidence
    # =========================================================================

    def _span_evidence(
        self,
        span: _ParsedSpan,
    ) -> EvidenceRecord:
        return EvidenceRecord(
            type=EvidenceType.RUNTIME_TRACE,
            artifact=self._artifact_id,
            locator=(f"trace:{span.trace_id}/" f"span:{span.span_id}"),
            observed_at=span.observed_at,
        )

    @staticmethod
    def _append_evidence(
        collection: dict[
            _EvidenceKey,
            list[EvidenceRecord],
        ],
        key: _EvidenceKey,
        evidence: EvidenceRecord,
    ) -> None:
        collection.setdefault(
            key,
            [],
        ).append(evidence)
