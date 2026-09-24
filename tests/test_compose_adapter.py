from pathlib import Path

from archdrift.adapters import ComposeAdapter
from archdrift.model import (
    NodeType,
    NormalizedNodeObservation,
    NormalizedRelationObservation,
)


def test_compose_adapter_extracts_services_and_service_call(
    tmp_path: Path,
) -> None:
    compose = tmp_path / "compose.yaml"

    compose.write_text(
        """
services:
  checkout:
    image: checkout
    environment:
      RECOMMENDATION_ADDR: http://recommendation:8080
      REDIS_ADDR: redis:6379
    depends_on:
      - recommendation
      - redis

  recommendation:
    image: recommendation

  redis:
    image: redis
""".strip(),
        encoding="utf-8",
    )

    adapter = ComposeAdapter(
        tmp_path,
        "compose.yaml",
        node_types={
            "checkout": NodeType.SERVICE,
            "recommendation": NodeType.SERVICE,
            "redis": NodeType.DATASTORE,
        },
    )

    observations = adapter.collect()

    nodes = tuple(
        item
        for item in observations
        if isinstance(
            item,
            NormalizedNodeObservation,
        )
    )

    relations = tuple(
        item
        for item in observations
        if isinstance(
            item,
            NormalizedRelationObservation,
        )
    )

    assert {
        node.endpoint.id
        for node in nodes
    } == {
        "checkout",
        "recommendation",
        "redis",
    }

    assert len(relations) == 1

    relation = relations[0]

    assert relation.source.id == "checkout"
    assert relation.target.id == "recommendation"
    assert relation.protocol == "http"


def test_compose_depends_on_does_not_create_call(
    tmp_path: Path,
) -> None:
    compose = tmp_path / "compose.yaml"

    compose.write_text(
        """
services:
  checkout:
    image: checkout
    depends_on:
      - recommendation

  recommendation:
    image: recommendation
""".strip(),
        encoding="utf-8",
    )

    observations = ComposeAdapter(
        tmp_path,
        "compose.yaml",
    ).collect()

    relations = tuple(
        item
        for item in observations
        if isinstance(
            item,
            NormalizedRelationObservation,
        )
    )

    assert relations == ()