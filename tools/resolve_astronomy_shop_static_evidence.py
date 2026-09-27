from __future__ import annotations

from pathlib import Path

from archdrift.adapters.compose_bindings import (
    ComposeEndpointBindingAdapter,
)
from archdrift.adapters.semgrep import (
    SemgrepResultAdapter,
)
from archdrift.analysis.static_resolution import (
    StaticTargetResolver,
)
from archdrift.model import (
    NodeType,
    SourcePathRule,
    StaticResolutionStatus,
)


ASTRONOMY_NODE_TYPES = {
    "ad": NodeType.SERVICE,
    "cart": NodeType.SERVICE,
    "checkout": NodeType.SERVICE,
    "currency": NodeType.SERVICE,
    "email": NodeType.SERVICE,
    "frontend": NodeType.SERVICE,
    "kafka": NodeType.BROKER,
    "payment": NodeType.SERVICE,
    "product-catalog": NodeType.SERVICE,
    "quote": NodeType.SERVICE,
    "recommendation": NodeType.SERVICE,
    "shipping": NodeType.SERVICE,
}


def main() -> int:
    root = (
        Path.cwd().resolve()
    )

    semgrep_file = (
        root
        / "evidence"
        / "real"
        / "non-runtime"
        / "astronomy-shop"
        / "source-static"
        / "semgrep.json"
    )

    compose_file = (
        root
        / "evidence"
        / "real"
        / "non-runtime"
        / "astronomy-shop"
        / "compose.resolved.json"
    )

    findings = (
        SemgrepResultAdapter()
        .collect(
            semgrep_file
        )
    )

    bindings = (
        ComposeEndpointBindingAdapter()
        .collect(
            result_file=(
                compose_file
            ),
            node_types=(
                ASTRONOMY_NODE_TYPES
            ),
        )
    )

    resolution_set = (
        StaticTargetResolver()
        .resolve(
            findings=findings,
            source_rules=(
                SourcePathRule(
                    path_prefix=(
                        "src/frontend"
                    ),
                    service_id=(
                        "frontend"
                    ),
                ),
            ),
            bindings=bindings,
        )
    )

    print(
        "Astronomy Shop source-static target resolution"
    )

    print(
        f"Findings:   {len(findings)}"
    )

    print(
        f"Bindings:   {len(bindings)}"
    )

    print(
        f"Resolved:   {resolution_set.resolved_count}"
    )

    print(
        f"Unresolved: {resolution_set.unresolved_count}"
    )

    print()

    for result in (
        resolution_set.results
    ):
        if (
            result.status
            is StaticResolutionStatus.RESOLVED
        ):
            resolved = (
                result.resolved
            )

            assert (
                resolved is not None
            )

            print(
                "  "
                f"{resolved.source_service_id} "
                f"--{resolved.finding.interaction.value}--> "
                f"{resolved.target_service_id} "
                f"[{resolved.environment_key}; "
                f"{resolved.finding.protocol}]"
            )

            continue

        print(
            "  UNRESOLVED "
            f"{result.finding.path}:"
            f"{result.finding.line} "
            f"target={result.finding.target_expression!r} "
            f"status={result.status.value} "
            f"reason={result.reason}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )