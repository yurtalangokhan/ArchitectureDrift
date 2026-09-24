from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

import networkx as nx
from pydantic import (
    BaseModel,
    ConfigDict,
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
    """Canonical architectural node types."""

    SERVICE = "SERVICE"
    DATASTORE = "DATASTORE"
    BROKER = "BROKER"
    GATEWAY = "GATEWAY"
    REGISTRY = "REGISTRY"
    EXTERNAL = "EXTERNAL"


class RelationType(StrEnum):
    """Canonical directed architectural relation types."""

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
    Experimental role represented by a canonical architecture graph.
    """

    BASELINE = "BASELINE"
    MUTANT = "MUTANT"
    OBSERVED = "OBSERVED"


class ReconstructionMode(StrEnum):
    """
    Evidence configuration used to reconstruct an OBSERVED graph.

    This is graph-generation metadata, not evidence itself.
    """

    NON_RUNTIME = "NON_RUNTIME"
    RUNTIME = "RUNTIME"
    FUSED = "FUSED"


# =============================================================================
# Type Aliases
# =============================================================================


RelationIdentity = tuple[
    str,
    RelationType,
    str,
]


# =============================================================================
# Exceptions
# =============================================================================


class ArchitectureGraphError(ValueError):
    """Base exception for canonical graph operations."""


class DuplicateNodeError(ArchitectureGraphError):
    """Raised when a node identifier already exists."""


class UnknownNodeError(ArchitectureGraphError):
    """Raised when an operation references an unknown node."""


class DuplicateRelationError(ArchitectureGraphError):
    """Raised when a canonical relation already exists."""


class UnknownRelationError(ArchitectureGraphError):
    """Raised when a canonical relation does not exist."""


# =============================================================================
# Graph Metadata
# =============================================================================


class GraphMetadata(BaseModel):
    """
    Immutable metadata describing one canonical architecture graph.

    BASELINE:
        Original reference graph.

    MUTANT:
        Reference graph after one controlled mutation.

    OBSERVED:
        Architecture reconstructed from one evidence configuration.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    system_id: str

    role: GraphRole

    variant: str | None = None

    reconstruction_mode: ReconstructionMode | None = None

    revision: str | None = None

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

    @model_validator(mode="after")
    def validate_role_semantics(
        self,
    ) -> Self:
        if self.role is GraphRole.BASELINE:
            if self.variant is not None:
                raise ValueError(
                    "BASELINE graph must not define a variant."
                )

            if self.reconstruction_mode is not None:
                raise ValueError(
                    "BASELINE graph must not define "
                    "a reconstruction_mode."
                )

        elif self.role is GraphRole.MUTANT:
            if self.variant is None:
                raise ValueError(
                    "MUTANT graph requires a variant identifier."
                )

            if self.reconstruction_mode is not None:
                raise ValueError(
                    "MUTANT graph must not define "
                    "a reconstruction_mode."
                )

        elif self.role is GraphRole.OBSERVED:
            if self.reconstruction_mode is None:
                raise ValueError(
                    "OBSERVED graph requires a reconstruction_mode."
                )

        return self


# =============================================================================
# Canonical Node
# =============================================================================


class ArchitectureNode(BaseModel):
    """
    Canonical architectural element.

    Canonical identity is exclusively ``id``.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    id: str

    type: NodeType

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


class ArchitectureRelation(BaseModel):
    """
    Directed canonical architecture relation.

    Canonical identity:

        (source, relation, target)

    Protocols and evidence provenance deliberately do not participate in
    canonical identity.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    source: str

    relation: RelationType

    target: str

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
        """Return canonical relation identity."""

        return (
            self.source,
            self.relation,
            self.target,
        )

    @property
    def networkx_key(self) -> str:
        """Return deterministic MultiDiGraph edge key."""

        return self.relation.value


# =============================================================================
# Canonical Architecture Graph
# =============================================================================


class ArchitectureGraph(BaseModel):
    """
    Immutable Canonical Architecture Graph.

    The Pydantic representation is the domain source of truth.

    NetworkX is only an analysis projection.

    Transformation methods always return a new validated graph instance.
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
        node_ids = tuple(
            node.id
            for node in value
        )

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
        identities = tuple(
            relation.identity
            for relation in value
        )

        if len(identities) != len(set(identities)):
            raise ValueError(
                "Canonical architecture graph contains "
                "duplicate relation identities."
            )

        return tuple(
            sorted(
                value,
                key=lambda item: (
                    item.source,
                    item.relation.value,
                    item.target,
                ),
            )
        )

    @model_validator(mode="after")
    def validate_relation_endpoints(
        self,
    ) -> Self:
        node_ids = self.node_ids

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
    # Canonical Sets
    # =========================================================================

    @property
    def node_ids(self) -> frozenset[str]:
        """
        Return canonical node identifiers.

        This representation will later be used directly by Graph Delta.
        """

        return frozenset(
            node.id
            for node in self.nodes
        )

    @property
    def relation_identities(
        self,
    ) -> frozenset[RelationIdentity]:
        """
        Return canonical relation identities.

        This representation will later be used directly by Graph Delta.
        """

        return frozenset(
            relation.identity
            for relation in self.relations
        )

    # =========================================================================
    # Node Lookup
    # =========================================================================

    def get_node(
        self,
        node_id: str,
    ) -> ArchitectureNode | None:
        """Return node by canonical identifier."""

        for node in self.nodes:
            if node.id == node_id:
                return node

        return None

    def require_node(
        self,
        node_id: str,
    ) -> ArchitectureNode:
        """Return node or raise UnknownNodeError."""

        node = self.get_node(node_id)

        if node is None:
            raise UnknownNodeError(
                f"Unknown architecture node: {node_id!r}"
            )

        return node

    # =========================================================================
    # Relation Lookup
    # =========================================================================

    def get_relation(
        self,
        *,
        source: str,
        relation: RelationType,
        target: str,
    ) -> ArchitectureRelation | None:
        """Return relation by canonical identity."""

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
        """Return relation or raise UnknownRelationError."""

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
        """Return whether a canonical relation exists."""

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
        """Return canonical relations matching optional filters."""

        result: list[ArchitectureRelation] = []

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
        """Return a new graph containing the supplied node."""

        if self.get_node(node.id) is not None:
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
        Return a new graph without the supplied node.

        Incident relations are removed automatically.
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
        """Return a new graph containing the supplied relation."""

        self.require_node(
            relation.source
        )

        self.require_node(
            relation.target
        )

        if relation.identity in self.relation_identities:
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
        """Return a new graph without the supplied relation."""

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
        Create a fully revalidated graph.

        model_copy(update=...) is intentionally not used because Pydantic
        does not validate update payloads by default.
        """

        return ArchitectureGraph(
            schema_version=self.schema_version,
            metadata=self.metadata,
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
        Project the canonical graph into NetworkX.

        The returned graph is an analysis representation. Mutating it cannot
        mutate the ArchitectureGraph instance.
        """

        graph: nx.MultiDiGraph[str] = nx.MultiDiGraph()

        graph.graph["schema_version"] = self.schema_version
        graph.graph["system_id"] = self.metadata.system_id
        graph.graph["role"] = self.metadata.role.value

        if self.metadata.variant is not None:
            graph.graph["variant"] = self.metadata.variant

        if self.metadata.reconstruction_mode is not None:
            graph.graph[
                "reconstruction_mode"
            ] = self.metadata.reconstruction_mode.value

        if self.metadata.revision is not None:
            graph.graph["revision"] = self.metadata.revision

        for node in self.nodes:
            graph.add_node(
                node.id,
                type=node.type.value,
            )

        for relation in self.relations:
            graph.add_edge(
                relation.source,
                relation.target,
                key=relation.networkx_key,
                relation=relation.relation.value,
            )

        return graph