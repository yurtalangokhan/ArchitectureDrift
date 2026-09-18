from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Self

import networkx as nx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from archdrift.model._validation import (
    normalize_identifier,
    normalize_optional_text,
)

# =============================================================================
# Canonical Vocabulary
# =============================================================================


class NodeType(StrEnum):
    """
    Canonical architectural node types.
    """

    SERVICE = "SERVICE"
    DATASTORE = "DATASTORE"
    BROKER = "BROKER"
    GATEWAY = "GATEWAY"
    REGISTRY = "REGISTRY"
    EXTERNAL = "EXTERNAL"


class RelationType(StrEnum):
    """
    Canonical directed architectural relation types.
    """

    CALLS = "CALLS"
    READS_FROM = "READS_FROM"
    WRITES_TO = "WRITES_TO"
    PUBLISHES_TO = "PUBLISHES_TO"
    SUBSCRIBES_TO = "SUBSCRIBES_TO"
    ROUTES_TO = "ROUTES_TO"
    DISCOVERS_VIA = "DISCOVERS_VIA"
    EXPOSES_TO = "EXPOSES_TO"


class GraphRole(StrEnum):
    """
    Experimental role represented by an architecture graph.

    Evidence mode is deliberately not represented here.

    BASELINE:
        Reference architecture before controlled mutation.

    MUTANT:
        Architecture after controlled mutation.

    OBSERVED:
        Architecture reconstructed from evidence.
    """

    BASELINE = "BASELINE"
    MUTANT = "MUTANT"
    OBSERVED = "OBSERVED"


# =============================================================================
# Exceptions
# =============================================================================


class ArchitectureGraphError(ValueError):
    """
    Base exception for canonical architecture graph operations.
    """


class DuplicateNodeError(ArchitectureGraphError):
    """
    Raised when a canonical node identifier already exists.
    """


class UnknownNodeError(ArchitectureGraphError):
    """
    Raised when an operation references an unknown node.
    """


class DuplicateRelationError(ArchitectureGraphError):
    """
    Raised when a canonical relation already exists.
    """


class UnknownRelationError(ArchitectureGraphError):
    """
    Raised when a canonical relation does not exist.
    """


# =============================================================================
# Metadata
# =============================================================================


class GraphMetadata(BaseModel):
    """
    Metadata describing one Canonical Architecture Graph.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    system_id: str

    role: GraphRole

    variant: str | None = Field(
        default=None,
        description=(
            "Optional experiment variant identifier, such as AS-M01."
        ),
    )

    revision: str | None = Field(
        default=None,
        description=(
            "Optional source-system revision used for reproducibility."
        ),
    )

    attributes: dict[str, Any] = Field(
        default_factory=dict,
    )

    @field_validator("system_id")
    @classmethod
    def validate_system_id(
        cls,
        value: str,
    ) -> str:
        return normalize_identifier(
            value,
            field_name="system_id",
        )

    @field_validator("variant")
    @classmethod
    def validate_variant(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        return normalize_identifier(
            value,
            field_name="variant",
        )

    @field_validator("revision")
    @classmethod
    def validate_revision(
        cls,
        value: str | None,
    ) -> str | None:
        return normalize_optional_text(value)


# =============================================================================
# Canonical Node
# =============================================================================


class ArchitectureNode(BaseModel):
    """
    Canonical architectural element.

    Node identity is defined exclusively by ``id``.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    id: str

    type: NodeType

    attributes: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Metadata that does not participate in canonical node identity."
        ),
    )

    @field_validator("id")
    @classmethod
    def validate_id(
        cls,
        value: str,
    ) -> str:
        return normalize_identifier(
            value,
            field_name="node id",
        )


# =============================================================================
# Canonical Relation
# =============================================================================


RelationIdentity = tuple[
    str,
    RelationType,
    str,
]


class ArchitectureRelation(BaseModel):
    """
    Directed canonical architectural relation.

    Canonical identity:

        (source, relation, target)

    Protocol, evidence source, trace identifiers, configuration locations,
    and other observational properties are deliberately excluded.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    source: str

    relation: RelationType

    target: str

    attributes: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Optional canonical metadata that does not participate "
            "in relation identity."
        ),
    )

    @field_validator(
        "source",
        "target",
    )
    @classmethod
    def validate_endpoint(
        cls,
        value: str,
    ) -> str:
        return normalize_identifier(
            value,
            field_name="relation endpoint",
        )

    @property
    def identity(self) -> RelationIdentity:
        """
        Return the canonical relation identity.
        """

        return (
            self.source,
            self.relation,
            self.target,
        )

    @property
    def networkx_key(self) -> str:
        """
        Return deterministic NetworkX MultiDiGraph edge key.
        """

        return self.relation.value


# =============================================================================
# Canonical Architecture Graph
# =============================================================================


class ArchitectureGraph(BaseModel):
    """
    Immutable Canonical Architecture Graph.

    The graph is intentionally evidence-independent.

    Mutating operations return a new graph rather than modifying the
    baseline instance in place. This behavior is especially useful for
    controlled baseline -> mutant experiments.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    schema_version: Literal["1.0"] = "1.0"

    metadata: GraphMetadata

    nodes: tuple[ArchitectureNode, ...] = ()

    relations: tuple[ArchitectureRelation, ...] = ()

    # =========================================================================
    # Validation
    # =========================================================================

    @field_validator("nodes")
    @classmethod
    def validate_nodes(
        cls,
        value: tuple[ArchitectureNode, ...],
    ) -> tuple[ArchitectureNode, ...]:
        node_ids = [
            node.id
            for node in value
        ]

        if len(node_ids) != len(set(node_ids)):
            raise ValueError(
                "Canonical architecture graph contains "
                "duplicate node identifiers."
            )

        return tuple(
            sorted(
                value,
                key=lambda node: node.id,
            )
        )

    @field_validator("relations")
    @classmethod
    def validate_relations(
        cls,
        value: tuple[ArchitectureRelation, ...],
    ) -> tuple[ArchitectureRelation, ...]:
        identities = [
            relation.identity
            for relation in value
        ]

        if len(identities) != len(set(identities)):
            raise ValueError(
                "Canonical architecture graph contains "
                "duplicate relation identities."
            )

        return tuple(
            sorted(
                value,
                key=lambda relation: (
                    relation.source,
                    relation.relation.value,
                    relation.target,
                ),
            )
        )

    @model_validator(mode="after")
    def validate_relation_endpoints(
        self,
    ) -> Self:
        node_ids = {
            node.id
            for node in self.nodes
        }

        for relation in self.relations:
            if relation.source not in node_ids:
                raise ValueError(
                    "Relation references unknown source node: "
                    f"{relation.source!r}"
                )

            if relation.target not in node_ids:
                raise ValueError(
                    "Relation references unknown target node: "
                    f"{relation.target!r}"
                )

        return self

    # =========================================================================
    # Lookup
    # =========================================================================

    def get_node(
        self,
        node_id: str,
    ) -> ArchitectureNode | None:
        """
        Return node by canonical identifier.
        """

        for node in self.nodes:
            if node.id == node_id:
                return node

        return None

    def require_node(
        self,
        node_id: str,
    ) -> ArchitectureNode:
        """
        Return node or raise UnknownNodeError.
        """

        node = self.get_node(node_id)

        if node is None:
            raise UnknownNodeError(
                f"Unknown architecture node: {node_id!r}"
            )

        return node

    def get_relation(
        self,
        *,
        source: str,
        relation: RelationType,
        target: str,
    ) -> ArchitectureRelation | None:
        """
        Return a canonical relation by identity.
        """

        identity: RelationIdentity = (
            source,
            relation,
            target,
        )

        for item in self.relations:
            if item.identity == identity:
                return item

        return None

    def require_relation(
        self,
        *,
        source: str,
        relation: RelationType,
        target: str,
    ) -> ArchitectureRelation:
        """
        Return relation or raise UnknownRelationError.
        """

        item = self.get_relation(
            source=source,
            relation=relation,
            target=target,
        )

        if item is None:
            raise UnknownRelationError(
                "Unknown architecture relation: "
                f"{source} {relation.value} {target}"
            )

        return item

    def has_relation(
        self,
        *,
        source: str,
        relation: RelationType,
        target: str,
    ) -> bool:
        """
        Return True when the canonical relation exists.
        """

        return (
            self.get_relation(
                source=source,
                relation=relation,
                target=target,
            )
            is not None
        )

    def find_relations(
        self,
        *,
        source: str | None = None,
        relation: RelationType | None = None,
        target: str | None = None,
    ) -> tuple[ArchitectureRelation, ...]:
        """
        Find relations matching optional canonical filters.
        """

        result = []

        for item in self.relations:
            if (
                source is not None
                and item.source != source
            ):
                continue

            if (
                relation is not None
                and item.relation is not relation
            ):
                continue

            if (
                target is not None
                and item.target != target
            ):
                continue

            result.append(item)

        return tuple(result)

    # =========================================================================
    # Immutable Transformations
    # =========================================================================

    def with_node(
        self,
        node: ArchitectureNode,
    ) -> ArchitectureGraph:
        """
        Return a new graph containing the supplied node.
        """

        existing = self.get_node(node.id)

        if existing is not None:
            raise DuplicateNodeError(
                f"Architecture node already exists: {node.id!r}"
            )

        return self._replace(
            nodes=(
                *self.nodes,
                node,
            ),
        )

    def without_node(
        self,
        node_id: str,
    ) -> ArchitectureGraph:
        """
        Return a new graph without the specified node.

        Incident relations are removed with the node.
        """

        self.require_node(node_id)

        nodes = tuple(
            node
            for node in self.nodes
            if node.id != node_id
        )

        relations = tuple(
            relation
            for relation in self.relations
            if (
                relation.source != node_id
                and relation.target != node_id
            )
        )

        return self._replace(
            nodes=nodes,
            relations=relations,
        )

    def with_relation(
        self,
        relation: ArchitectureRelation,
    ) -> ArchitectureGraph:
        """
        Return a new graph containing the supplied relation.
        """

        self.require_node(relation.source)
        self.require_node(relation.target)

        if self.get_relation(
            source=relation.source,
            relation=relation.relation,
            target=relation.target,
        ) is not None:
            raise DuplicateRelationError(
                "Architecture relation already exists: "
                f"{relation.source} "
                f"{relation.relation.value} "
                f"{relation.target}"
            )

        return self._replace(
            relations=(
                *self.relations,
                relation,
            ),
        )

    def without_relation(
        self,
        *,
        source: str,
        relation: RelationType,
        target: str,
    ) -> ArchitectureGraph:
        """
        Return a new graph without the specified relation.
        """

        existing = self.require_relation(
            source=source,
            relation=relation,
            target=target,
        )

        relations = tuple(
            item
            for item in self.relations
            if item.identity != existing.identity
        )

        return self._replace(
            relations=relations,
        )

    def _replace(
        self,
        *,
        nodes: tuple[ArchitectureNode, ...] | None = None,
        relations: tuple[ArchitectureRelation, ...] | None = None,
    ) -> ArchitectureGraph:
        """
        Rebuild the graph through normal Pydantic validation.

        ``model_copy(update=...)`` is deliberately not used because Pydantic
        does not validate update payloads by default.
        """

        return ArchitectureGraph(
            schema_version=self.schema_version,
            metadata=self.metadata.model_copy(
                deep=True
            ),
            nodes=(
                self.nodes
                if nodes is None
                else nodes
            ),
            relations=(
                self.relations
                if relations is None
                else relations
            ),
        )

    # =========================================================================
    # NetworkX Projection
    # =========================================================================

    def to_networkx(
        self,
    ) -> nx.MultiDiGraph[str]:
        """
        Project the canonical model into a NetworkX MultiDiGraph.

        NetworkX is an analysis representation, not the source of truth.
        """

        graph: nx.MultiDiGraph[str] = nx.MultiDiGraph()

        graph.graph.update(
            self.metadata.model_dump(
                mode="json",
                exclude_none=True,
            )
        )

        graph.graph["schema_version"] = self.schema_version

        for node in self.nodes:
            payload = node.model_dump(
                mode="json",
                exclude={"id"},
            )

            graph.add_node(
                node.id,
                **payload,
            )

        for relation in self.relations:
            payload = relation.model_dump(
                mode="json",
                exclude={
                    "source",
                    "target",
                    "relation",
                },
            )

            payload["relation"] = relation.relation.value

            graph.add_edge(
                relation.source,
                relation.target,
                key=relation.networkx_key,
                **payload,
            )

        return graph