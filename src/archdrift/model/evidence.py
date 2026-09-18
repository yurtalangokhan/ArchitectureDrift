from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from archdrift.model._validation import (
    normalize_optional_text,
    normalize_required_text,
)


class EvidenceChannel(StrEnum):
    """
    High-level evidence channel used by the experiment.

    FUSED is deliberately not represented here because fused architecture
    is derived from multiple evidence channels rather than being evidence
    itself.
    """

    NON_RUNTIME = "NON_RUNTIME"
    RUNTIME = "RUNTIME"


class EvidenceType(StrEnum):
    """
    Origin of an architectural observation.

    Ground truth, architecture contracts, mutation oracles, and workloads
    are deliberately excluded.
    """

    SOURCE_CODE = "SOURCE_CODE"
    REPOSITORY_CONFIG = "REPOSITORY_CONFIG"
    DEPLOYMENT_CONFIG = "DEPLOYMENT_CONFIG"
    API_SPEC = "API_SPEC"
    RUNTIME_TRACE = "RUNTIME_TRACE"


class EvidenceRecord(BaseModel):
    """
    Provenance record describing why an architectural observation exists.

    Evidence records are independent from the Canonical Architecture Graph.

    Example evidence sources include:

    - Docker Compose configuration
    - .NET Aspire WithReference declarations
    - repository configuration
    - OpenAPI documents
    - OpenTelemetry traces
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    type: EvidenceType

    artifact: str = Field(
        description="Artifact containing the architectural evidence."
    )

    locator: str | None = Field(
        default=None,
        description=(
            "Optional location inside the artifact, such as a YAML path, "
            "source symbol, trace identifier, or configuration key."
        ),
    )

    observed_at: datetime | None = Field(
        default=None,
        description=(
            "Timestamp at which runtime evidence was observed."
        ),
    )

    attributes: dict[str, Any] = Field(
        default_factory=dict,
        description="Evidence-specific metadata.",
    )

    @field_validator("artifact")
    @classmethod
    def validate_artifact(
        cls,
        value: str,
    ) -> str:
        return normalize_required_text(
            value,
            field_name="artifact",
        )

    @field_validator("locator")
    @classmethod
    def validate_locator(
        cls,
        value: str | None,
    ) -> str | None:
        return normalize_optional_text(value)

    @property
    def channel(self) -> EvidenceChannel:
        """
        Return the experiment-level evidence channel.
        """

        if self.type is EvidenceType.RUNTIME_TRACE:
            return EvidenceChannel.RUNTIME

        return EvidenceChannel.NON_RUNTIME

    def fingerprint(self) -> str:
        """
        Return a deterministic SHA-256 fingerprint.

        Fingerprints are used for evidence deduplication without coupling
        evidence identity to architecture relation identity.
        """

        serialized = json.dumps(
            self.model_dump(
                mode="json",
                exclude_none=True,
            ),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        return hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()


def deduplicate_evidence(
    records: Iterable[EvidenceRecord],
) -> tuple[EvidenceRecord, ...]:
    """
    Remove duplicate evidence records and return deterministic output.
    """

    unique = {
        record.fingerprint(): record
        for record in records
    }

    return tuple(
        unique[fingerprint]
        for fingerprint in sorted(unique)
    )