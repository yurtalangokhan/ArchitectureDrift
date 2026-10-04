from __future__ import annotations

import argparse
from pathlib import Path

from archdrift.experiments.static_profile import (
    load_static_evidence_profile,
)
from archdrift.experiments.static_runner import (
    StaticEvidenceRunner,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--subject",
        required=True,
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    root = Path.cwd().resolve()

    subject_id = args.subject

    profile = load_static_evidence_profile(
        root / "cases" / "real-evidence.yaml",
        subject_id=subject_id,
    )

    result = StaticEvidenceRunner().run(
        profile=profile,
        subject_root=(root / profile.subject_root),
        rule_pack_root=(root / "rules" / "semgrep" / "packs"),
        output_root=(
            root
            / "evidence"
            / "real"
            / "non-runtime"
            / subject_id
            / "source-static"
            / "raw"
        ),
    )

    print(f"Subject:  {result.subject_id}")

    print(f"Findings: {len(result.findings)}")

    print()

    for finding in result.findings:
        print(
            f"{finding.path}:"
            f"{finding.line} "
            f"{finding.interaction.value} "
            f"target="
            f"{finding.target_expression!r} "
            f"protocol="
            f"{finding.protocol or '-'} "
            f"rule="
            f"{finding.rule_id}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
