from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)


@pytest.mark.integration
def test_astronomy_shop_real_evidence_artifacts_are_present() -> None:
    evidence = (
        PROJECT_ROOT
        / "evidence"
        / "real"
        / "non-runtime"
        / "astronomy-shop"
        / "compose.resolved.json"
    )

    baseline = (
        PROJECT_ROOT
        / "graphs"
        / "baseline"
        / "astronomy-shop"
        / "baseline.yaml"
    )

    assert evidence.is_file()
    assert baseline.is_file()