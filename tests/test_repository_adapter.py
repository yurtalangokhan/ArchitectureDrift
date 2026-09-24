from pathlib import Path

from archdrift.adapters import (
    RepositoryAdapter,
    RepositoryServiceSpec,
)
from archdrift.model import (
    EvidenceChannel,
    NodeType,
    NormalizedNodeObservation,
)


def test_repository_adapter_discovers_configured_service(
    tmp_path: Path,
) -> None:
    service_root = (
        tmp_path
        / "src"
        / "checkout"
    )

    service_root.mkdir(
        parents=True
    )

    dockerfile = (
        service_root
        / "Dockerfile"
    )

    dockerfile.write_text(
        "FROM python:3.12\n",
        encoding="utf-8",
    )

    adapter = RepositoryAdapter(
        tmp_path,
        services=(
            RepositoryServiceSpec(
                id="checkout",
                path="src/checkout",
                type=NodeType.SERVICE,
                markers=(
                    "Dockerfile",
                ),
            ),
        ),
    )

    observations = adapter.collect()

    assert len(observations) == 1

    observation = observations[0]

    assert isinstance(
        observation,
        NormalizedNodeObservation,
    )

    assert observation.endpoint.id == "checkout"
    assert observation.endpoint.type is NodeType.SERVICE

    assert (
        observation.channel
        is EvidenceChannel.NON_RUNTIME
    )

    assert (
        observation.evidence[0].artifact
        == "src/checkout/Dockerfile"
    )