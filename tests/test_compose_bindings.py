import json
from pathlib import Path

from archdrift.adapters.compose_bindings import (
    ComposeEndpointBindingAdapter,
)
from archdrift.model import (
    NodeType,
)


def test_compose_endpoint_binding_adapter_extracts_known_service_endpoint(
    tmp_path: Path,
) -> None:
    compose_file = (
        tmp_path
        / "compose.json"
    )

    compose_file.write_text(
        json.dumps(
            {
                "services": {
                    "frontend": {
                        "environment": {
                            "CURRENCY_ADDR": (
                                "currency:8080"
                            ),
                            "EXTERNAL_URL": (
                                "https://example.com"
                            ),
                        }
                    },
                    "currency": {},
                }
            }
        ),
        encoding="utf-8",
    )

    bindings = (
        ComposeEndpointBindingAdapter()
        .collect(
            result_file=(
                compose_file
            ),
            node_types={
                "frontend": (
                    NodeType.SERVICE
                ),
                "currency": (
                    NodeType.SERVICE
                ),
            },
        )
    )

    assert len(
        bindings
    ) == 1

    binding = (
        bindings[0]
    )

    assert (
        binding.source_service_id
        == "frontend"
    )

    assert (
        binding.environment_key
        == "CURRENCY_ADDR"
    )

    assert (
        binding.target_service_id
        == "currency"
    )