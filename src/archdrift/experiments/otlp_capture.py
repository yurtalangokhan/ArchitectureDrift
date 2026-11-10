from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from archdrift.adapters.otel import (
    OtelAdapter,
)
from archdrift.analysis.normalize import (
    CanonicalRelationCandidate,
    canonicalize_observation,
)
from archdrift.model.graph import (
    NodeType,
    RelationType,
)


class OtlpCaptureError(
    RuntimeError
):
    """Raised when captured OTLP data cannot be normalized."""


def merge_otlp_json_lines(
    *,
    source: str | Path,
    destination: str | Path,
) -> int:
    """
    Merge newline-delimited OTLP TracesData records into one
    OTLP JSON document consumable by OtelAdapter.
    """

    source_path = Path(source)
    destination_path = Path(destination)

    if not source_path.is_file():
        raise FileNotFoundError(
            f"OTLP JSONL file not found: {source_path}"
        )

    resource_spans: list[
        object
    ] = []

    record_count = 0

    for line_number, raw_line in enumerate(
        source_path.read_text(
            encoding="utf-8"
        ).splitlines(),
        start=1,
    ):
        line = raw_line.strip()

        if not line:
            continue

        try:
            document = json.loads(
                line
            )

        except json.JSONDecodeError as exc:
            raise OtlpCaptureError(
                "Invalid OTLP JSON record at "
                f"line {line_number}: {source_path}"
            ) from exc

        if not isinstance(
            document,
            dict,
        ):
            raise OtlpCaptureError(
                "OTLP JSON record must be an object: "
                f"line {line_number}"
            )

        spans = document.get(
            "resourceSpans",
            document.get(
                "resource_spans"
            ),
        )

        if spans is None:
            continue

        if not isinstance(
            spans,
            list,
        ):
            raise OtlpCaptureError(
                "OTLP resourceSpans must be a list: "
                f"line {line_number}"
            )

        resource_spans.extend(
            spans
        )

        record_count += 1

    if not resource_spans:
        raise OtlpCaptureError(
            "Captured OTLP file contains "
            "no resourceSpans."
        )

    destination_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination_path.write_text(
        json.dumps(
            {
                "resourceSpans": (
                    resource_spans
                )
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return record_count


def relation_present(
    *,
    trace_file: str | Path,
    node_types: Mapping[
        str,
        NodeType,
    ],
    source: str,
    relation: RelationType,
    target: str,
) -> bool:
    observations = OtelAdapter(
        trace_file,
        node_types=node_types,
    ).collect()

    candidates = tuple(
        canonicalize_observation(
            observation
        )
        for observation in observations
    )

    return any(
        isinstance(
            candidate,
            CanonicalRelationCandidate,
        )
        and candidate.relation.source
        == source
        and candidate.relation.relation
        is relation
        and candidate.relation.target
        == target
        for candidate in candidates
    )