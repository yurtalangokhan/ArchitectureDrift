from pathlib import Path

from archdrift.adapters import ComposeAdapter
from archdrift.analysis import (
    canonicalize_relation_observation,
)
from archdrift.model import (
    InteractionType,
    NodeType,
    NormalizedNodeObservation,
    NormalizedRelationObservation,
    RelationType,
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

    assert {node.endpoint.id for node in nodes} == {
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


def test_compose_registry_reference_creates_discovery_observation(
    tmp_path: Path,
) -> None:
    compose = tmp_path / "compose.yaml"

    compose.write_text(
        """
services:
  webui:
    image: teastore-webui
    environment:
      REGISTRY_HOST: registry

  registry:
    image: teastore-registry
""".strip(),
        encoding="utf-8",
    )

    observations = ComposeAdapter(
        tmp_path,
        "compose.yaml",
        node_types={
            "webui": NodeType.SERVICE,
            "registry": NodeType.REGISTRY,
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

    assert len(relations) == 1

    relation = relations[0]

    assert relation.source.id == "webui"
    assert relation.target.id == "registry"

    assert relation.interaction is InteractionType.DISCOVERY

    candidate = canonicalize_relation_observation(relation)

    assert candidate.relation.relation is RelationType.DISCOVERS_VIA


def test_compose_http_url_resolves_to_service_call(
    tmp_path: Path,
) -> None:
    compose = tmp_path / "compose.yaml"

    compose.write_text(
        """
services:
  source:
    image: source
    environment:
      TARGET_URL: http://target:8080

  target:
    image: target
""".strip(),
        encoding="utf-8",
    )

    observations = ComposeAdapter(
        tmp_path,
        "compose.yaml",
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

    assert relation.source.id == "source"
    assert relation.target.id == "target"

    assert relation.interaction is InteractionType.SERVICE_CALL

    assert relation.protocol == "http"


def test_compose_bare_host_resolves_to_service_call(
    tmp_path: Path,
) -> None:
    compose = tmp_path / "compose.yaml"

    compose.write_text(
        """
services:
  source:
    environment:
      TARGET_HOST: target

  target:
    image: target
""".strip(),
        encoding="utf-8",
    )

    observations = ComposeAdapter(
        tmp_path,
        "compose.yaml",
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
    assert relations[0].target.id == "target"
    assert relations[0].protocol is None


def test_compose_datastore_endpoint_is_not_misclassified_as_call(
    tmp_path: Path,
) -> None:
    compose = tmp_path / "compose.yaml"

    compose.write_text(
        """
services:
  source:
    environment:
      REDIS_ADDR: redis:6379

  redis:
    image: redis
""".strip(),
        encoding="utf-8",
    )

    observations = ComposeAdapter(
        tmp_path,
        "compose.yaml",
        node_types={
            "source": NodeType.SERVICE,
            "redis": NodeType.DATASTORE,
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
