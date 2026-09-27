from __future__ import annotations

from pathlib import Path

from archdrift.adapters.semgrep import (
    SemgrepResultAdapter,
    SemgrepRunner,
)


def main() -> int:
    root = (
        Path.cwd().resolve()
    )

    subject_root = (
        root
        / "subjects"
        / "astronomy-shop"
    )

    rules = (
        root
        / "rules"
        / "semgrep"
        / "astronomy-shop.yaml"
    )

    output = (
        root
        / "evidence"
        / "real"
        / "non-runtime"
        / "astronomy-shop"
        / "source-static"
        / "semgrep.json"
    )

    runner = SemgrepRunner()

    version = runner.version()

    print(
        f"Semgrep: {version}"
    )

    runner.scan(
        subject_root=subject_root,
        rules=rules,
        output=output,
    )

    findings = (
        SemgrepResultAdapter()
        .collect(
            output
        )
    )

    print(
        f"Findings: {len(findings)}"
    )

    for finding in findings:
        print(
            "  "
            f"{finding.path}:{finding.line} "
            f"{finding.rule_id} "
            f"target={finding.target_expression}"
        )

    print(
        f"Result: {output}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )