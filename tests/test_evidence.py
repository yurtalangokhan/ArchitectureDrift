from archdrift.model.evidence import (
    EvidenceRecord,
    EvidenceType,
    deduplicate_evidence,
)


def test_evidence_fingerprint_is_deterministic() -> None:
    first = EvidenceRecord(
        type=EvidenceType.RUNTIME_TRACE,
        artifact="traces.json",
        locator="trace-001",
        attributes={
            "service": "checkout",
            "target": "payment",
        },
    )

    second = EvidenceRecord(
        type=EvidenceType.RUNTIME_TRACE,
        artifact="traces.json",
        locator="trace-001",
        attributes={
            "target": "payment",
            "service": "checkout",
        },
    )

    assert first.fingerprint() == second.fingerprint()


def test_different_evidence_has_different_fingerprint() -> None:
    first = EvidenceRecord(
        type=EvidenceType.RUNTIME_TRACE,
        artifact="traces.json",
        locator="trace-001",
    )

    second = EvidenceRecord(
        type=EvidenceType.RUNTIME_TRACE,
        artifact="traces.json",
        locator="trace-002",
    )

    assert first.fingerprint() != second.fingerprint()


def test_duplicate_evidence_is_removed() -> None:
    evidence = EvidenceRecord(
        type=EvidenceType.DEPLOYMENT_CONFIG,
        artifact="compose.yaml",
        locator="PAYMENT_ADDR",
    )

    result = deduplicate_evidence(
        [
            evidence,
            evidence,
            evidence,
        ]
    )

    assert len(result) == 1
    assert result[0] == evidence