from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
)

from archdrift.model.observation import (
    NormalizedObservation,
)


class NormalizedObservationSnapshot(
    BaseModel
):
    """
    Immutable normalized evidence snapshot used by empirical experiments.

    Acquisition and evaluation are intentionally separated:
    acquisition tools create this artifact once; experiment runners consume
    the frozen snapshot without invoking external analyzers again.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    schema_version: Literal["1.0"] = "1.0"

    system_id: str

    variant: str

    observations: tuple[
        NormalizedObservation,
        ...,
    ]


def write_observation_snapshot(
    *,
    path: Path,
    system_id: str,
    variant: str,
    observations: tuple[
        NormalizedObservation,
        ...,
    ],
) -> Path:
    destination = path.resolve()

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    snapshot = (
        NormalizedObservationSnapshot(
            system_id=system_id,
            variant=variant,
            observations=observations,
        )
    )

    destination.write_text(
        snapshot.model_dump_json(
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return destination


def load_observation_snapshot(
    path: Path,
) -> NormalizedObservationSnapshot:
    source = path.resolve()

    if not source.is_file():
        raise FileNotFoundError(
            "Normalized evidence snapshot "
            f"not found: {source}"
        )

    return (
        NormalizedObservationSnapshot
        .model_validate_json(
            source.read_text(
                encoding="utf-8",
            )
        )
    )