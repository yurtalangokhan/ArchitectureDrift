from pathlib import Path

from archdrift.adapters import AspireAdapter
from archdrift.model import (
    NodeType,
    NormalizedNodeObservation,
    NormalizedRelationObservation,
)


def test_aspire_adapter_extracts_resources_and_reference(
    tmp_path: Path,
) -> None:
    apphost = tmp_path / "src" / "AppHost" / "Program.cs"

    apphost.parent.mkdir(parents=True)

    apphost.write_text(
        """
var catalog = builder
    .AddProject<Projects.Catalog>("catalog");

var basket = builder
    .AddProject<Projects.Basket>("basket")
    .WithReference(catalog);

var redis = builder
    .AddRedis("redis");
""".strip(),
        encoding="utf-8",
    )

    observations = AspireAdapter(
        tmp_path,
        "src/AppHost/Program.cs",
    ).collect()

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

    node_types = {item.endpoint.id: item.endpoint.type for item in nodes}

    assert node_types == {
        "basket": NodeType.SERVICE,
        "catalog": NodeType.SERVICE,
        "redis": NodeType.DATASTORE,
    }

    assert len(relations) == 1

    assert relations[0].source.id == "basket"
    assert relations[0].target.id == "catalog"


def test_aspire_datastore_reference_is_not_misclassified(
    tmp_path: Path,
) -> None:
    apphost = tmp_path / "Program.cs"

    apphost.write_text(
        """
var redis = builder.AddRedis("redis");

builder
    .AddProject<Projects.Basket>("basket")
    .WithReference(redis);
""".strip(),
        encoding="utf-8",
    )

    observations = AspireAdapter(
        tmp_path,
        "Program.cs",
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


def test_aspire_adapter_supports_single_line_resource_declarations(
    tmp_path: Path,
) -> None:
    apphost = tmp_path / "Program.cs"

    apphost.write_text(
        """
var catalog = builder.AddProject<Projects.Catalog>("catalog");
var redis = builder.AddRedis("redis");
""".strip(),
        encoding="utf-8",
    )

    observations = AspireAdapter(
        tmp_path,
        "Program.cs",
    ).collect()

    nodes = tuple(
        item
        for item in observations
        if isinstance(
            item,
            NormalizedNodeObservation,
        )
    )

    node_types = {item.endpoint.id: item.endpoint.type for item in nodes}

    assert node_types == {
        "catalog": NodeType.SERVICE,
        "redis": NodeType.DATASTORE,
    }
