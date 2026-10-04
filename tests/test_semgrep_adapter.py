from __future__ import annotations

import json
from pathlib import Path

import pytest

from archdrift.adapters.semgrep import (
    SemgrepResultAdapter,
    SemgrepResultError,
)
from archdrift.model import (
    InteractionType,
)


def test_semgrep_result_adapter_extracts_target_expression(
    tmp_path: Path,
) -> None:
    result_file = tmp_path / "semgrep.json"

    result_file.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "check_id": ("archdrift.typescript.grpc-client"),
                        "path": ("src/frontend/gateways/" "rpc/Currency.gateway.ts"),
                        "start": {
                            "line": 9,
                            "col": 16,
                        },
                        "end": {
                            "line": 9,
                            "col": 80,
                        },
                        "extra": {
                            "message": ("ARCHDRIFT_TARGET=" "CURRENCY_ADDR"),
                            "severity": "INFO",
                            "metadata": {
                                "archdrift": {
                                    "interaction": ("SERVICE_CALL"),
                                    "protocol": "grpc",
                                }
                            },
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    findings = SemgrepResultAdapter().collect(result_file)

    assert len(findings) == 1

    finding = findings[0]

    assert finding.rule_id == "archdrift.typescript.grpc-client"

    assert finding.path == ("src/frontend/gateways/" "rpc/Currency.gateway.ts")

    assert finding.line == 9

    assert finding.interaction is InteractionType.SERVICE_CALL

    assert finding.target_expression == "CURRENCY_ADDR"

    assert finding.protocol == "grpc"


def test_semgrep_result_adapter_rejects_non_archdrift_rule(
    tmp_path: Path,
) -> None:
    result_file = tmp_path / "semgrep.json"

    result_file.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "check_id": "foreign.rule",
                        "path": "source.ts",
                        "start": {
                            "line": 1,
                        },
                        "extra": {
                            "message": "ARCHDRIFT_TARGET=CURRENCY_ADDR",
                            "metadata": {
                                "archdrift": {
                                    "interaction": "SERVICE_CALL",
                                    "protocol": "grpc",
                                }
                            },
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        SemgrepResultError,
        match="not an ArchitectureDrift rule",
    ):
        (SemgrepResultAdapter().collect(result_file))


def test_semgrep_result_adapter_rejects_empty_target_expression(
    tmp_path: Path,
) -> None:
    result_file = tmp_path / "semgrep.json"

    result_file.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "check_id": ("archdrift.typescript.fetch"),
                        "path": ("src/frontend/gateways/" "http/Shipping.gateway.ts"),
                        "start": {
                            "line": 31,
                        },
                        "extra": {
                            "message": ("ARCHDRIFT_TARGET="),
                            "metadata": {
                                "archdrift": {
                                    "interaction": ("SERVICE_CALL"),
                                    "protocol": "http",
                                }
                            },
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        SemgrepResultError,
        match="empty target expression",
    ):
        (SemgrepResultAdapter().collect(result_file))


def test_semgrep_result_adapter_normalizes_prefixed_rule_id_and_extracts_target(
    tmp_path: Path,
) -> None:
    result_file = tmp_path / "semgrep.json"

    result_file.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "check_id": (
                            "rules.semgrep." "archdrift.typescript.grpc-client"
                        ),
                        "path": ("src/frontend/gateways/" "rpc/Currency.gateway.ts"),
                        "start": {
                            "line": 9,
                            "col": 16,
                        },
                        "end": {
                            "line": 9,
                            "col": 93,
                        },
                        "extra": {
                            "message": ("ARCHDRIFT_TARGET=" "CURRENCY_ADDR"),
                            "severity": "INFO",
                            "metadata": {
                                "archdrift": {
                                    "interaction": ("SERVICE_CALL"),
                                    "protocol": "grpc",
                                }
                            },
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    findings = SemgrepResultAdapter().collect(result_file)

    assert len(findings) == 1

    finding = findings[0]

    assert finding.rule_id == "archdrift.typescript.grpc-client"

    assert finding.target_expression == "CURRENCY_ADDR"

    assert finding.interaction is InteractionType.SERVICE_CALL

    assert finding.protocol == "grpc"


def test_semgrep_result_adapter_rejects_missing_target_marker(
    tmp_path: Path,
) -> None:
    result_file = tmp_path / "semgrep.json"

    result_file.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "check_id": ("rules.semgrep." "archdrift.typescript.fetch"),
                        "path": ("src/frontend/gateways/" "http/Shipping.gateway.ts"),
                        "start": {
                            "line": 31,
                        },
                        "extra": {
                            "message": ("invalid message"),
                            "metadata": {
                                "archdrift": {
                                    "interaction": ("SERVICE_CALL"),
                                    "protocol": "http",
                                }
                            },
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        SemgrepResultError,
        match="target marker",
    ):
        (SemgrepResultAdapter().collect(result_file))
