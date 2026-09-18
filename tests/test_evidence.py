from datetime import UTC, datetime

from archdrift.model import (
    EvidenceChannel,
    EvidenceRecord,
    EvidenceType,
    deduplicate_evidence,
)


def test_evidence_type_vocabulary() -> None:
    assert set(EvidenceType) == {
        EvidenceType.SOURCE_CODE,
        EvidenceType.REPOSITORY_CONFIG,
        EvidenceType.DEPLOYMENT_CONFIG,
        EvidenceType.API_SPEC,
        EvidenceType.RUNTIME_TRACE,
    }


def test_static_evidence_is_non_runtime() -> None:
    evidence = EvidenceRecord(
        type=EvidenceType.DEPLOYMENT_CONFIG,
        artifact="compose.yaml",
    )

    assert evidence.channel is EvidenceChannel.NON_RUNTIME


def test_runtime_trace_is_runtime_evidence() -> None:
    evidence = EvidenceRecord(
        type=EvidenceType.RUNTIME_TRACE,
        artifact="trace.json",
        observed_at=datetime(
            2026,
            9,
            18,
            tzinfo=UTC,
        ),
    )

    assert evidence.channel is EvidenceChannel.RUNTIME


def test_artifact_is_normalized() -> None:
    evidence = EvidenceRecord(
        type=EvidenceType.SOURCE_CODE,
        artifact="  src/service.py  ",
    )

    assert evidence.artifact == "src/service.py"


def test_blank_locator_becomes_none() -> None:
    evidence = EvidenceRecord(
        type=EvidenceType.SOURCE_CODE,
        artifact="src/service.py",
        locator="   ",
    )

    assert evidence.locator is None


def test_fingerprint_is_deterministic() -> None:
    evidence_a = EvidenceRecord(
        type=EvidenceType.RUNTIME_TRACE,
        artifact="trace.json",
        locator="span-001",
    )

    evidence_b = EvidenceRecord(
        type=EvidenceType.RUNTIME_TRACE,
        artifact="trace.json",
        locator="span-001",
    )

    assert (
        evidence_a.fingerprint()
        == evidence_b.fingerprint()
    )


def test_different_evidence_has_different_fingerprint() -> None:
    evidence_a = EvidenceRecord(
        type=EvidenceType.RUNTIME_TRACE,
        artifact="trace.json",
        locator="span-001",
    )

    evidence_b = EvidenceRecord(
        type=EvidenceType.RUNTIME_TRACE,
        artifact="trace.json",
        locator="span-002",
    )

    assert (
        evidence_a.fingerprint()
        != evidence_b.fingerprint()
    )


def test_duplicate_evidence_is_removed() -> None:
    evidence = EvidenceRecord(
        type=EvidenceType.RUNTIME_TRACE,
        artifact="trace.json",
        locator="span-001",
    )

    result = deduplicate_evidence(
        [
            evidence,
            evidence,
        ]
    )

    assert result == (
        evidence,
    )