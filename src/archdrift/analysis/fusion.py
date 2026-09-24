from __future__ import annotations

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)

from archdrift.analysis.normalize import (
    CanonicalCandidate,
    CanonicalNodeCandidate,
    CanonicalRelationCandidate,
)
from archdrift.model.evidence import (
    EvidenceChannel,
    EvidenceRecord,
    deduplicate_evidence,
)
from archdrift.model.graph import (
    ArchitectureGraph,
    ArchitectureNode,
    ArchitectureRelation,
    GraphMetadata,
    GraphRole,
    NodeType,
    ReconstructionMode,
    RelationIdentity,
)


# =============================================================================
# Exceptions
# =============================================================================


class FusionError(ValueError):
    """Base exception for evidence reconstruction and fusion."""


class CandidateConflictError(FusionError):
    """
    Raised when candidate evidence produces incompatible canonical semantics.
    """


# =============================================================================
# Support Models
# =============================================================================


class NodeSupport(BaseModel):
    """
    Provenance supporting one canonical architecture node.

    Evidence remains outside ArchitectureGraph.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    node: ArchitectureNode

    evidence: tuple[
        EvidenceRecord,
        ...,
    ]

    @field_validator("evidence")
    @classmethod
    def normalize_evidence(
        cls,
        value: tuple[
            EvidenceRecord,
            ...,
        ],
    ) -> tuple[
        EvidenceRecord,
        ...,
    ]:
        if not value:
            raise ValueError(
                "Node support requires at least one evidence record."
            )

        return deduplicate_evidence(
            value
        )

    @property
    def channels(
        self,
    ) -> tuple[EvidenceChannel, ...]:
        return tuple(
            sorted(
                {
                    evidence.channel
                    for evidence in self.evidence
                },
                key=lambda channel: channel.value,
            )
        )

    @property
    def is_cross_channel(
        self,
    ) -> bool:
        return len(
            self.channels
        ) > 1


class RelationSupport(BaseModel):
    """
    Provenance supporting one canonical architecture relation.

    Protocols and evidence provenance do not participate in canonical
    relation identity.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    relation: ArchitectureRelation

    protocols: tuple[
        str,
        ...,
    ] = ()

    evidence: tuple[
        EvidenceRecord,
        ...,
    ]

    @field_validator("protocols")
    @classmethod
    def normalize_protocols(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        normalized = tuple(
            sorted(
                {
                    protocol.strip().lower()
                    for protocol in value
                    if protocol.strip()
                }
            )
        )

        return normalized

    @field_validator("evidence")
    @classmethod
    def normalize_evidence(
        cls,
        value: tuple[
            EvidenceRecord,
            ...,
        ],
    ) -> tuple[
        EvidenceRecord,
        ...,
    ]:
        if not value:
            raise ValueError(
                "Relation support requires at least one evidence record."
            )

        return deduplicate_evidence(
            value
        )

    @property
    def channels(
        self,
    ) -> tuple[EvidenceChannel, ...]:
        return tuple(
            sorted(
                {
                    evidence.channel
                    for evidence in self.evidence
                },
                key=lambda channel: channel.value,
            )
        )

    @property
    def is_cross_channel(
        self,
    ) -> bool:
        return len(
            self.channels
        ) > 1


# =============================================================================
# Reconstruction Result
# =============================================================================


class ReconstructionResult(BaseModel):
    """
    One reconstructed canonical architecture graph plus its provenance.

    ArchitectureGraph remains evidence-free. Support records provide the
    explainability/provenance layer.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    graph: ArchitectureGraph

    node_support: tuple[
        NodeSupport,
        ...,
    ] = ()

    relation_support: tuple[
        RelationSupport,
        ...,
    ] = ()

    @field_validator("node_support")
    @classmethod
    def normalize_node_support(
        cls,
        value: tuple[
            NodeSupport,
            ...,
        ],
    ) -> tuple[
        NodeSupport,
        ...,
    ]:
        node_ids = tuple(
            support.node.id
            for support in value
        )

        if len(node_ids) != len(
            set(node_ids)
        ):
            raise ValueError(
                "Reconstruction result contains duplicate node support."
            )

        return tuple(
            sorted(
                value,
                key=lambda support: support.node.id,
            )
        )

    @field_validator("relation_support")
    @classmethod
    def normalize_relation_support(
        cls,
        value: tuple[
            RelationSupport,
            ...,
        ],
    ) -> tuple[
        RelationSupport,
        ...,
    ]:
        identities = tuple(
            support.relation.identity
            for support in value
        )

        if len(identities) != len(
            set(identities)
        ):
            raise ValueError(
                "Reconstruction result contains duplicate relation support."
            )

        return tuple(
            sorted(
                value,
                key=lambda support: (
                    support.relation.source,
                    support.relation.relation.value,
                    support.relation.target,
                ),
            )
        )

    @model_validator(mode="after")
    def validate_graph_support_consistency(
        self,
    ) -> Self:
        supported_node_ids = frozenset(
            support.node.id
            for support in self.node_support
        )

        supported_relation_ids = frozenset(
            support.relation.identity
            for support in self.relation_support
        )

        if (
            supported_node_ids
            != self.graph.node_ids
        ):
            raise ValueError(
                "Node support must exactly match reconstructed graph nodes."
            )

        if (
            supported_relation_ids
            != self.graph.relation_identities
        ):
            raise ValueError(
                "Relation support must exactly match reconstructed "
                "graph relations."
            )

        return self

    def get_node_support(
        self,
        node_id: str,
    ) -> NodeSupport | None:
        for support in self.node_support:
            if support.node.id == node_id:
                return support

        return None

    def get_relation_support(
        self,
        identity: RelationIdentity,
    ) -> RelationSupport | None:
        for support in self.relation_support:
            if (
                support.relation.identity
                == identity
            ):
                return support

        return None


# =============================================================================
# Experiment Views
# =============================================================================


class EvidenceGraphViews(BaseModel):
    """
    The three evidence configurations compared by the experiment.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    non_runtime: ReconstructionResult

    runtime: ReconstructionResult

    fused: ReconstructionResult

    @model_validator(mode="after")
    def validate_modes(
        self,
    ) -> Self:
        if (
            self.non_runtime.graph.metadata.reconstruction_mode
            is not ReconstructionMode.NON_RUNTIME
        ):
            raise ValueError(
                "non_runtime view must use NON_RUNTIME reconstruction mode."
            )

        if (
            self.runtime.graph.metadata.reconstruction_mode
            is not ReconstructionMode.RUNTIME
        ):
            raise ValueError(
                "runtime view must use RUNTIME reconstruction mode."
            )

        if (
            self.fused.graph.metadata.reconstruction_mode
            is not ReconstructionMode.FUSED
        ):
            raise ValueError(
                "fused view must use FUSED reconstruction mode."
            )

        return self


# =============================================================================
# Candidate Selection
# =============================================================================


def _candidate_selected(
    candidate: CanonicalCandidate,
    mode: ReconstructionMode,
) -> bool:
    if mode is ReconstructionMode.FUSED:
        return True

    if mode is ReconstructionMode.NON_RUNTIME:
        return (
            candidate.channel
            is EvidenceChannel.NON_RUNTIME
        )

    if mode is ReconstructionMode.RUNTIME:
        return (
            candidate.channel
            is EvidenceChannel.RUNTIME
        )

    raise FusionError(
        f"Unsupported reconstruction mode: {mode!r}"
    )


# =============================================================================
# Reconstruction
# =============================================================================


def reconstruct_observed_graph(
    *,
    system_id: str,
    candidates: tuple[
        CanonicalCandidate,
        ...,
    ],
    mode: ReconstructionMode,
    variant: str | None = None,
    revision: str | None = None,
) -> ReconstructionResult:
    """
    Reconstruct one canonical observed graph from evidence-backed candidates.

    NON_RUNTIME:
        Only non-runtime candidates are selected.

    RUNTIME:
        Only runtime candidates are selected.

    FUSED:
        Candidates from both evidence channels are combined by canonical
        identity.

    No statistical weighting or confidence threshold is applied.
    """

    selected = tuple(
        candidate
        for candidate in candidates
        if _candidate_selected(
            candidate,
            mode,
        )
    )

    node_types: dict[
        str,
        NodeType,
    ] = {}

    node_evidence: dict[
        str,
        list[EvidenceRecord],
    ] = {}

    relation_models: dict[
        RelationIdentity,
        ArchitectureRelation,
    ] = {}

    relation_evidence: dict[
        RelationIdentity,
        list[EvidenceRecord],
    ] = {}

    relation_protocols: dict[
        RelationIdentity,
        set[str],
    ] = {}

    def register_node(
        node: ArchitectureNode,
        evidence: tuple[
            EvidenceRecord,
            ...,
        ],
    ) -> None:
        existing_type = node_types.get(
            node.id
        )

        if (
            existing_type is not None
            and existing_type is not node.type
        ):
            raise CandidateConflictError(
                "Conflicting canonical node types for "
                f"{node.id!r}: "
                f"{existing_type.value} != "
                f"{node.type.value}"
            )

        node_types[
            node.id
        ] = node.type

        node_evidence.setdefault(
            node.id,
            [],
        ).extend(
            evidence
        )

    for candidate in selected:
        if isinstance(
            candidate,
            CanonicalNodeCandidate,
        ):
            register_node(
                candidate.node,
                candidate.evidence,
            )

            continue

        if isinstance(
            candidate,
            CanonicalRelationCandidate,
        ):
            # Relation evidence also proves that its two endpoints participated
            # in an observed architectural interaction.
            register_node(
                candidate.source_node,
                candidate.evidence,
            )

            register_node(
                candidate.target_node,
                candidate.evidence,
            )

            identity = (
                candidate.relation.identity
            )

            relation_models.setdefault(
                identity,
                candidate.relation,
            )

            relation_evidence.setdefault(
                identity,
                [],
            ).extend(
                candidate.evidence
            )

            if candidate.protocol is not None:
                relation_protocols.setdefault(
                    identity,
                    set(),
                ).add(
                    candidate.protocol
                )

            continue

        raise TypeError(
            f"Unsupported canonical candidate: {type(candidate)!r}"
        )

    nodes = tuple(
        ArchitectureNode(
            id=node_id,
            type=node_type,
        )
        for node_id, node_type in node_types.items()
    )

    relations = tuple(
        relation_models.values()
    )

    graph = ArchitectureGraph(
        metadata=GraphMetadata(
            system_id=system_id,
            role=GraphRole.OBSERVED,
            variant=variant,
            reconstruction_mode=mode,
            revision=revision,
        ),
        nodes=nodes,
        relations=relations,
    )

    node_support = tuple(
        NodeSupport(
            node=ArchitectureNode(
                id=node_id,
                type=node_types[node_id],
            ),
            evidence=tuple(
                node_evidence[node_id]
            ),
        )
        for node_id in node_types
    )

    relation_support = tuple(
        RelationSupport(
            relation=relation,
            protocols=tuple(
                relation_protocols.get(
                    identity,
                    set(),
                )
            ),
            evidence=tuple(
                relation_evidence[
                    identity
                ]
            ),
        )
        for identity, relation in relation_models.items()
    )

    return ReconstructionResult(
        graph=graph,
        node_support=node_support,
        relation_support=relation_support,
    )


def build_evidence_graph_views(
    *,
    system_id: str,
    candidates: tuple[
        CanonicalCandidate,
        ...,
    ],
    variant: str | None = None,
    revision: str | None = None,
) -> EvidenceGraphViews:
    """
    Build all three experimental reconstruction views from one candidate set.
    """

    return EvidenceGraphViews(
        non_runtime=reconstruct_observed_graph(
            system_id=system_id,
            candidates=candidates,
            mode=ReconstructionMode.NON_RUNTIME,
            variant=variant,
            revision=revision,
        ),
        runtime=reconstruct_observed_graph(
            system_id=system_id,
            candidates=candidates,
            mode=ReconstructionMode.RUNTIME,
            variant=variant,
            revision=revision,
        ),
        fused=reconstruct_observed_graph(
            system_id=system_id,
            candidates=candidates,
            mode=ReconstructionMode.FUSED,
            variant=variant,
            revision=revision,
        ),
    )