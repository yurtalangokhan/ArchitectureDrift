from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvidenceType(StrEnum):
    """
    Identifies the origin of architectural evidence.

    Ground truth and mutation oracles are deliberately not represented as
    evidence types. They belong to the experimental oracle rather than the
    observed architecture.
    """

    SOURCE_CODE = "SOURCE_CODE"
    REPOSITORY_CONFIG = "REPOSITORY_CONFIG"
    DEPLOYMENT_CONFIG = "DEPLOYMENT_CONFIG"
    API_SPEC = "API_SPEC"
    RUNTIME_TRACE = "RUNTIME_TRACE"
    WORKLOAD_ASSERTION = "WORKLOAD_ASSERTION"


class EvidenceRecord(BaseModel):
    """
    Provenance information for an observed architectural relation.

    EvidenceRecord answers the question:

        "Why do we believe this architectural relation exists?"

    Examples:
        - a Docker Compose environment variable,
        - an Aspire WithReference declaration,
        - an OpenTelemetry span,
        - a source-code service client reference.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    type: EvidenceType

    artifact: str = Field(
        min_length=1,
        description="Source artifact containing the evidence.",
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
        description="Timestamp at which runtime evidence was observed.",
    )

    attributes: dict[str, Any] = Field(
        default_factory=dict,
        description="Evidence-specific metadata.",
    )

    @field_validator("artifact")
    @classmethod
    def normalize_artifact(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("artifact must not be empty")

        return value

    @field_validator("locator")
    @classmethod
    def normalize_locator(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        return value or None

    def fingerprint(self) -> str:
        """
        Returns a deterministic SHA-256 fingerprint for the evidence record.

        The fingerprint is used to remove duplicate provenance records when
        several adapters report the same evidence.
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

        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def deduplicate_evidence(
    records: list[EvidenceRecord],
) -> list[EvidenceRecord]:
    """
    Removes duplicate evidence records while preserving deterministic order.
    """

    unique: dict[str, EvidenceRecord] = {}

    for record in records:
        unique[record.fingerprint()] = record

    return sorted(
        unique.values(),
        key=lambda item: item.fingerprint(),
    )