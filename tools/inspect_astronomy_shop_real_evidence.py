from __future__ import annotations

from pathlib import Path

from archdrift.adapters.compose import (
    ComposeAdapter,
)
from archdrift.analysis.scope import (
    EvidenceScope,
    ScopeExclusionReason,
    apply_evidence_scope,
)
from archdrift.model import (
    NodeType,
    NormalizedNodeObservation,
    NormalizedRelationObservation,
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
    project_root = (
        Path.cwd().resolve()
    )

    resolved_compose = (
        project_root
        / "evidence"
        / "real"
        / "non-runtime"
        / "astronomy-shop"
        / "compose.resolved.json"
    )

    if not resolved_compose.is_file():
        raise FileNotFoundError(
            "Resolved Astronomy Shop Compose evidence "
            f"does not exist: {resolved_compose}"
        )

    adapter = ComposeAdapter(
        project_root,
        resolved_compose.relative_to(
            project_root
        ),
        node_types=(
            ASTRONOMY_NODE_TYPES
        ),
    )

    raw_observations = (
        adapter.collect()
    )

    scope = EvidenceScope(
        node_ids=frozenset(
            ASTRONOMY_NODE_TYPES
        )
    )

    scoped = apply_evidence_scope(
        raw_observations,
        scope=scope,
    )

    included_nodes = tuple(
        observation
        for observation in scoped.included
        if isinstance(
            observation,
            NormalizedNodeObservation,
        )
    )

    included_relations = tuple(
        observation
        for observation in scoped.included
        if isinstance(
            observation,
            NormalizedRelationObservation,
        )
    )

    print(
        "Astronomy Shop real non-runtime evidence"
    )

    print(
        f"Raw observations:      "
        f"{len(raw_observations)}"
    )

    print(
        f"Scoped observations:   "
        f"{scoped.included_count}"
    )

    print(
        f"Excluded observations: "
        f"{scoped.excluded_count}"
    )

    print()

    print(
        f"Scoped nodes:     "
        f"{len(included_nodes)}"
    )

    print(
        f"Scoped relations: "
        f"{len(included_relations)}"
    )

    print()

    print(
        "Included relations:"
    )

    for observation in (
        included_relations
    ):
        print(
            "  "
            f"{observation.source.id} "
            f"--{observation.interaction.value}--> "
            f"{observation.target.id}"
            + (
                f" [{observation.protocol}]"
                if observation.protocol
                else ""
            )
        )

    print()

    print(
        "Scope exclusions:"
    )

    for reason in (
        ScopeExclusionReason
    ):
        count = (
            scoped.excluded_count_for(
                reason
            )
        )

        print(
            f"  {reason.value}: {count}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )