from __future__ import annotations

import copy
from enum import StrEnum
from typing import Any, Literal, Self

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# =============================================================================
# Canonical Vocabulary
# =============================================================================


class NodeType(StrEnum):
    """
    Canonical architectural node types.

    These types are deliberately technology-independent so that architecture
    reconstructed from different evidence channels can be compared using the
    same graph vocabulary.
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


# =============================================================================
# Exceptions
# =============================================================================


class ArchitectureGraphError(Exception):
    """
    Base exception for Canonical Architecture Graph operations.
    """


class DuplicateNodeError(ArchitectureGraphError):
    """
    Raised when a node with the same canonical identifier already exists.
    """


class UnknownNodeError(ArchitectureGraphError):
    """
    Raised when an operation references a node that does not exist.
    """


class DuplicateRelationError(ArchitectureGraphError):
    """
    Raised when the same canonical relation already exists.
    """


class UnknownRelationError(ArchitectureGraphError):
    """
    Raised when an operation references a relation that does not exist.
    """


# =============================================================================
# Validation Helpers
# =============================================================================


def _validate_identifier(value: str) -> str:
    """
    Validate and normalize canonical identifiers.

    Canonical identifiers must:

    - not be empty
    - not contain whitespace

    Examples:

        checkout
        recommendation
        frontend-proxy
        postgres
        kafka
        service-a
    """

    normalized = value.strip()

    if not normalized:
        raise ValueError("Identifier must not be empty.")

    if any(character.isspace() for character in normalized):
        raise ValueError(
            f"Identifier must not contain whitespace: {value!r}"
        )

    return normalized


# =============================================================================
# Canonical Domain Models
# =============================================================================


class ArchitectureNode(BaseModel):
    """
    Canonical architectural element.

    Node identity is determined only by ``id``.

    Evidence-specific information must not be used as graph identity.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    id: str = Field(
        description="Stable canonical identifier of the architectural element."
    )

    type: NodeType = Field(
        description="Canonical architectural node type."
    )

    name: str | None = Field(
        default=None,
        description="Optional human-readable node name.",
    )

    attributes: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Optional metadata that does not participate in node identity."
        ),
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return _validate_identifier(value)


class ArchitectureRelation(BaseModel):
    """
    Directed canonical relation between two architecture nodes.

    Canonical relation identity is:

        source + relation type + target

    Example:

        checkout --CALLS--> recommendation
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    source: str = Field(
        description="Canonical source node identifier."
    )

    target: str = Field(
        description="Canonical target node identifier."
    )

    type: RelationType = Field(
        description="Canonical architectural relation type."
    )

    attributes: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Optional relation metadata such as protocol or endpoint. "
            "Metadata does not participate in relation identity."
        ),
    )

    @field_validator("source", "target")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        return _validate_identifier(value)

    @property
    def signature(self) -> tuple[str, RelationType, str]:
        """
        Return the canonical relation identity.
        """

        return (
            self.source,
            self.type,
            self.target,
        )


class CanonicalArchitectureModel(BaseModel):
    """
    Serializable representation of a Canonical Architecture Graph.

    This model is independent from NetworkX and can later be serialized
    to JSON/YAML or used by mutation and graph-delta analysis.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    schema_version: Literal["1.0"] = "1.0"

    system_id: str = Field(
        description="Identifier of the case system."
    )

    nodes: list[ArchitectureNode] = Field(
        default_factory=list,
    )

    relations: list[ArchitectureRelation] = Field(
        default_factory=list,
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
    )

    @field_validator("system_id")
    @classmethod
    def validate_system_id(cls, value: str) -> str:
        return _validate_identifier(value)

    @model_validator(mode="after")
    def validate_graph_invariants(self) -> Self:
        """
        Validate graph-level invariants.

        Invariants:

        1. Node identifiers must be unique.
        2. Every relation source must exist.
        3. Every relation target must exist.
        4. Canonical relation signatures must be unique.
        """

        node_ids = [
            node.id
            for node in self.nodes
        ]

        if len(node_ids) != len(set(node_ids)):
            raise ValueError(
                "Canonical architecture contains duplicate node identifiers."
            )

        known_nodes = set(node_ids)

        relation_signatures: set[
            tuple[str, RelationType, str]
        ] = set()

        for relation in self.relations:
            if relation.source not in known_nodes:
                raise ValueError(
                    "Relation references unknown source node: "
                    f"{relation.source!r}"
                )

            if relation.target not in known_nodes:
                raise ValueError(
                    "Relation references unknown target node: "
                    f"{relation.target!r}"
                )

            if relation.signature in relation_signatures:
                raise ValueError(
                    "Canonical architecture contains duplicate relation: "
                    f"{relation.source} "
                    f"{relation.type.value} "
                    f"{relation.target}"
                )

            relation_signatures.add(
                relation.signature
            )

        return self


# =============================================================================
# Canonical Architecture Graph
# =============================================================================


class CanonicalArchitectureGraph:
    """
    Runtime representation of the Canonical Architecture Graph.

    Internally NetworkX MultiDiGraph is used.

    MultiDiGraph is required because the same source-target node pair may
    contain multiple architectural relation types.

    Example:

        gateway --ROUTES_TO--> service
        gateway --CALLS-----> service

    NetworkX remains an implementation detail and is not exposed directly.
    """

    def __init__(
        self,
        system_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._system_id = _validate_identifier(system_id)

        self._metadata = copy.deepcopy(
            metadata or {}
        )

        self._graph = nx.MultiDiGraph()

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def system_id(self) -> str:
        """
        Return case-system identifier.
        """

        return self._system_id

    @property
    def node_count(self) -> int:
        """
        Return number of canonical architecture nodes.
        """

        return self._graph.number_of_nodes()

    @property
    def relation_count(self) -> int:
        """
        Return number of canonical architecture relations.
        """

        return self._graph.number_of_edges()

    @property
    def metadata(self) -> dict[str, Any]:
        """
        Return a defensive copy of graph metadata.
        """

        return copy.deepcopy(
            self._metadata
        )

    # =========================================================================
    # Node Operations
    # =========================================================================

    def add_node(
        self,
        node: ArchitectureNode,
    ) -> None:
        """
        Add a node to the canonical graph.

        Duplicate identifiers are rejected.
        """

        if self._graph.has_node(node.id):
            raise DuplicateNodeError(
                f"Node already exists: {node.id!r}"
            )

        stored_node = node.model_copy(
            deep=True
        )

        self._graph.add_node(
            stored_node.id,
            model=stored_node,
        )

    def has_node(
        self,
        node_id: str,
    ) -> bool:
        """
        Return True when a node exists.
        """

        return self._graph.has_node(
            node_id
        )

    def get_node(
        self,
        node_id: str,
    ) -> ArchitectureNode:
        """
        Retrieve a node by canonical identifier.
        """

        if not self._graph.has_node(node_id):
            raise UnknownNodeError(
                f"Unknown node: {node_id!r}"
            )

        node: ArchitectureNode = (
            self._graph.nodes[node_id]["model"]
        )

        return node.model_copy(
            deep=True
        )

    def remove_node(
        self,
        node_id: str,
    ) -> None:
        """
        Remove a canonical node.

        NetworkX automatically removes incident relations.

        This capability will later be used by controlled mutation operators.
        """

        if not self._graph.has_node(node_id):
            raise UnknownNodeError(
                f"Unknown node: {node_id!r}"
            )

        self._graph.remove_node(
            node_id
        )

    # =========================================================================
    # Relation Operations
    # =========================================================================

    def add_relation(
        self,
        relation: ArchitectureRelation,
    ) -> None:
        """
        Add a directed architectural relation.

        Source and target nodes must already exist.

        Relation identity is:

            source + relation type + target
        """

        if not self._graph.has_node(
            relation.source
        ):
            raise UnknownNodeError(
                f"Unknown source node: {relation.source!r}"
            )

        if not self._graph.has_node(
            relation.target
        ):
            raise UnknownNodeError(
                f"Unknown target node: {relation.target!r}"
            )

        edge_key = relation.type.value

        if self._graph.has_edge(
            relation.source,
            relation.target,
            key=edge_key,
        ):
            raise DuplicateRelationError(
                "Relation already exists: "
                f"{relation.source} "
                f"{relation.type.value} "
                f"{relation.target}"
            )

        stored_relation = relation.model_copy(
            deep=True
        )

        self._graph.add_edge(
            stored_relation.source,
            stored_relation.target,
            key=edge_key,
            model=stored_relation,
        )

    def has_relation(
        self,
        source: str,
        relation_type: RelationType,
        target: str,
    ) -> bool:
        """
        Return True when the canonical relation exists.
        """

        return self._graph.has_edge(
            source,
            target,
            key=relation_type.value,
        )

    def get_relation(
        self,
        source: str,
        relation_type: RelationType,
        target: str,
    ) -> ArchitectureRelation:
        """
        Retrieve a canonical architecture relation.
        """

        if not self.has_relation(
            source=source,
            relation_type=relation_type,
            target=target,
        ):
            raise UnknownRelationError(
                "Unknown relation: "
                f"{source} "
                f"{relation_type.value} "
                f"{target}"
            )

        relation: ArchitectureRelation = (
            self._graph.edges[
                source,
                target,
                relation_type.value,
            ]["model"]
        )

        return relation.model_copy(
            deep=True
        )

    def remove_relation(
        self,
        source: str,
        relation_type: RelationType,
        target: str,
    ) -> None:
        """
        Remove one canonical architecture relation.
        """

        if not self.has_relation(
            source=source,
            relation_type=relation_type,
            target=target,
        ):
            raise UnknownRelationError(
                "Unknown relation: "
                f"{source} "
                f"{relation_type.value} "
                f"{target}"
            )

        self._graph.remove_edge(
            source,
            target,
            key=relation_type.value,
        )

    # =========================================================================
    # Collections
    # =========================================================================

    def nodes(
        self,
    ) -> tuple[ArchitectureNode, ...]:
        """
        Return nodes in deterministic order.

        Deterministic ordering is important for repeatable experiments.
        """

        nodes = [
            data["model"].model_copy(deep=True)
            for _, data
            in self._graph.nodes(data=True)
        ]

        nodes.sort(
            key=lambda node: node.id
        )

        return tuple(nodes)

    def relations(
        self,
    ) -> tuple[ArchitectureRelation, ...]:
        """
        Return relations in deterministic order.
        """

        relations = [
            data["model"].model_copy(deep=True)
            for _, _, _, data
            in self._graph.edges(
                keys=True,
                data=True,
            )
        ]

        relations.sort(
            key=lambda relation: (
                relation.source,
                relation.type.value,
                relation.target,
            )
        )

        return tuple(relations)

    # =========================================================================
    # Serialization Model
    # =========================================================================

    def to_model(
        self,
    ) -> CanonicalArchitectureModel:
        """
        Convert graph into its serializable canonical model.
        """

        return CanonicalArchitectureModel(
            system_id=self.system_id,
            nodes=list(self.nodes()),
            relations=list(self.relations()),
            metadata=self.metadata,
        )

    @classmethod
    def from_model(
        cls,
        model: CanonicalArchitectureModel,
    ) -> CanonicalArchitectureGraph:
        """
        Build a graph from a serialized canonical model.
        """

        graph = cls(
            system_id=model.system_id,
            metadata=copy.deepcopy(
                model.metadata
            ),
        )

        for node in model.nodes:
            graph.add_node(node)

        for relation in model.relations:
            graph.add_relation(relation)

        return graph

    # =========================================================================
    # Controlled Mutation Support
    # =========================================================================

    def copy(
        self,
    ) -> CanonicalArchitectureGraph:
        """
        Create an independent graph copy.

        Controlled architectural mutations must always operate on a copy of
        the baseline graph rather than modifying the baseline in-place.
        """

        canonical_model = self.to_model().model_copy(
            deep=True
        )

        return CanonicalArchitectureGraph.from_model(
            canonical_model
        )

    # =========================================================================
    # NetworkX Interoperability
    # =========================================================================

    def as_networkx(
        self,
    ) -> nx.MultiDiGraph:
        """
        Return a defensive copy of the internal NetworkX graph.

        Returning a copy prevents consumers from bypassing graph invariants.
        """

        return copy.deepcopy(
            self._graph
        )