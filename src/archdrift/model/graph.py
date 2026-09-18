from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import networkx as nx
import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from archdrift.model.evidence import (
    EvidenceRecord,
    deduplicate_evidence,
)


class NodeType(StrEnum):
    SERVICE = "SERVICE"
    DATASTORE = "DATASTORE"
    BROKER = "BROKER"
    GATEWAY = "GATEWAY"
    REGISTRY = "REGISTRY"
    EXTERNAL = "EXTERNAL"


class RelationType(StrEnum):
    CALLS = "CALLS"
    READS_FROM = "READS_FROM"
    WRITES_TO = "WRITES_TO"
    PUBLISHES_TO = "PUBLISHES_TO"
    SUBSCRIBES_TO = "SUBSCRIBES_TO"
    ROUTES_TO = "ROUTES_TO"
    DISCOVERS_VIA = "DISCOVERS_VIA"
    EXPOSES_TO = "EXPOSES_TO"


class GraphView(StrEnum):
    """
    Identifies the architectural view represented by a graph.
    """

    CANONICAL = "CANONICAL"
    CONTRACT = "CONTRACT"
    SOURCE = "SOURCE"
    DEPLOYMENT = "DEPLOYMENT"
    NON_RUNTIME = "NON_RUNTIME"
    RUNTIME = "RUNTIME"
    FUSED = "FUSED"


class GraphMetadata(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    system_id: str = Field(min_length=1)

    variant: str = Field(
        default="baseline",
        min_length=1,
    )

    revision: str | None = None

    view: GraphView = GraphView.CANONICAL

    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("system_id", "variant")
    @classmethod
    def normalize_required_string(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("value must not be empty")

        return value

    @field_validator("revision")
    @classmethod
    def normalize_optional_string(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        value = value.strip()

        return value or None


class ArchitectureNode(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    id: str = Field(min_length=1)

    type: NodeType

    subtype: str | None = None

    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("node id must not be empty")

        return value

    @field_validator("subtype")
    @classmethod
    def normalize_subtype(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        value = value.strip()

        return value or None


class ArchitectureEdge(BaseModel):
    """
    Typed directed architectural relation.

    Edge identity:

        (source, target, relation, protocol)

    Protocol is part of the identity because a change such as:

        HTTP -> gRPC

    must be observable as an architectural graph delta.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    source: str = Field(min_length=1)

    target: str = Field(min_length=1)

    relation: RelationType

    protocol: str | None = None

    evidence: list[EvidenceRecord] = Field(default_factory=list)

    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source", "target")
    @classmethod
    def normalize_endpoint(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("edge endpoint must not be empty")

        return value

    @field_validator("protocol")
    @classmethod
    def normalize_protocol(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        value = value.strip().lower()

        return value or None

    @field_validator("evidence")
    @classmethod
    def normalize_evidence(
        cls,
        value: list[EvidenceRecord],
    ) -> list[EvidenceRecord]:
        """
        Deduplicates evidence without assigning to self from inside
        a model-level validator.

        Using a field validator avoids recursive assignment validation.
        """

        return deduplicate_evidence(value)

    @property
    def identity(
        self,
    ) -> tuple[str, str, RelationType, str | None]:
        return (
            self.source,
            self.target,
            self.relation,
            self.protocol,
        )

    @property
    def networkx_key(self) -> str:
        protocol = self.protocol or "-"

        return f"{self.relation.value}:{protocol}"

    def merge_with(
        self,
        other: ArchitectureEdge,
    ) -> ArchitectureEdge:
        """
        Merges two observations of the same architectural relation.

        Evidence provenance is combined and duplicate evidence is removed.
        """

        if self.identity != other.identity:
            raise ValueError(
                "Only architecture edges with identical identities can be merged."
            )

        merged_attributes = dict(self.attributes)

        for key, value in other.attributes.items():
            if (
                key in merged_attributes
                and merged_attributes[key] != value
            ):
                raise ValueError(
                    f"Conflicting canonical edge attribute '{key}' "
                    f"for edge {self.identity}."
                )

            merged_attributes[key] = value

        return ArchitectureEdge(
            source=self.source,
            target=self.target,
            relation=self.relation,
            protocol=self.protocol,
            evidence=deduplicate_evidence(
                [
                    *self.evidence,
                    *other.evidence,
                ]
            ),
            attributes=merged_attributes,
        )


class ArchitectureGraph(BaseModel):
    """
    Canonical directed typed architecture graph.

    Duplicate relations are normalized according to:

        (source, target, relation, protocol)

    Provenance from multiple observations of the same relation is merged.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    schema_version: Literal["1.0"] = "1.0"

    metadata: GraphMetadata

    nodes: list[ArchitectureNode] = Field(default_factory=list)

    edges: list[ArchitectureEdge] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_and_normalize_graph(
        self,
    ) -> ArchitectureGraph:
        self._validate_unique_nodes()
        self._validate_edge_endpoints()
        self._normalize_edges()
        self._sort_graph()

        return self

    def _validate_unique_nodes(self) -> None:
        seen: set[str] = set()

        for node in self.nodes:
            if node.id in seen:
                raise ValueError(
                    f"Duplicate architecture node id: '{node.id}'"
                )

            seen.add(node.id)

    def _validate_edge_endpoints(self) -> None:
        node_ids = {
            node.id
            for node in self.nodes
        }

        for edge in self.edges:
            if edge.source not in node_ids:
                raise ValueError(
                    f"Edge source '{edge.source}' does not exist "
                    "in the architecture graph."
                )

            if edge.target not in node_ids:
                raise ValueError(
                    f"Edge target '{edge.target}' does not exist "
                    "in the architecture graph."
                )

    def _normalize_edges(self) -> None:
        merged: dict[
            tuple[str, str, RelationType, str | None],
            ArchitectureEdge,
        ] = {}

        for edge in self.edges:
            identity = edge.identity

            if identity not in merged:
                merged[identity] = edge.model_copy(deep=True)
                continue

            merged[identity] = merged[identity].merge_with(edge)

        # IMPORTANT:
        # Do not use:
        #
        #     self.edges = ...
        #
        # inside a model validator when validate_assignment=True.
        # That would trigger model validation recursively.
        object.__setattr__(
            self,
            "edges",
            list(merged.values()),
        )

    def _sort_graph(self) -> None:
        self.nodes.sort(
            key=lambda node: node.id
        )

        self.edges.sort(
            key=lambda edge: (
                edge.source,
                edge.target,
                edge.relation.value,
                edge.protocol or "",
            )
        )

    def add_node(
        self,
        node: ArchitectureNode,
    ) -> None:
        existing = self.get_node(node.id)

        if existing is not None:
            if existing != node:
                raise ValueError(
                    f"Node '{node.id}' already exists "
                    "with different attributes."
                )

            return

        self.nodes.append(node)

        self._sort_graph()

    def get_node(
        self,
        node_id: str,
    ) -> ArchitectureNode | None:
        for node in self.nodes:
            if node.id == node_id:
                return node

        return None

    def add_edge(
        self,
        edge: ArchitectureEdge,
    ) -> None:
        node_ids = {
            node.id
            for node in self.nodes
        }

        if edge.source not in node_ids:
            raise ValueError(
                f"Edge source '{edge.source}' does not exist."
            )

        if edge.target not in node_ids:
            raise ValueError(
                f"Edge target '{edge.target}' does not exist."
            )

        for index, existing in enumerate(self.edges):
            if existing.identity == edge.identity:
                self.edges[index] = existing.merge_with(edge)
                self._sort_graph()
                return

        self.edges.append(edge)

        self._sort_graph()

    def find_edges(
        self,
        *,
        source: str | None = None,
        target: str | None = None,
        relation: RelationType | None = None,
        protocol: str | None = None,
    ) -> list[ArchitectureEdge]:
        normalized_protocol = (
            protocol.strip().lower()
            if protocol is not None
            else None
        )

        matches: list[ArchitectureEdge] = []

        for edge in self.edges:
            if (
                source is not None
                and edge.source != source
            ):
                continue

            if (
                target is not None
                and edge.target != target
            ):
                continue

            if (
                relation is not None
                and edge.relation != relation
            ):
                continue

            if (
                protocol is not None
                and edge.protocol != normalized_protocol
            ):
                continue

            matches.append(edge)

        return matches

    def has_edge(
        self,
        *,
        source: str,
        target: str,
        relation: RelationType,
        protocol: str | None = None,
    ) -> bool:
        return bool(
            self.find_edges(
                source=source,
                target=target,
                relation=relation,
                protocol=protocol,
            )
        )

    def remove_edges(
        self,
        *,
        source: str,
        target: str,
        relation: RelationType,
        protocol: str | None = None,
    ) -> int:
        """
        Removes matching architectural relations.

        If protocol is None, every matching protocol is removed.
        """

        normalized_protocol = (
            protocol.strip().lower()
            if protocol is not None
            else None
        )

        remaining: list[ArchitectureEdge] = []

        removed = 0

        for edge in self.edges:
            matches = (
                edge.source == source
                and edge.target == target
                and edge.relation == relation
                and (
                    protocol is None
                    or edge.protocol == normalized_protocol
                )
            )

            if matches:
                removed += 1
                continue

            remaining.append(edge)

        # Internal controlled mutation:
        # bypass validate_assignment to avoid unnecessary model recursion.
        object.__setattr__(
            self,
            "edges",
            remaining,
        )

        self._sort_graph()

        return removed

    def to_networkx(
        self,
    ) -> nx.MultiDiGraph[str]:
        """
        Converts the canonical model into a NetworkX MultiDiGraph.

        Node identifiers are always strings.
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
            node_data = node.model_dump(
                mode="json",
                exclude={"id"},
                exclude_none=True,
            )

            graph.add_node(
                node.id,
                **node_data,
            )

        for edge in self.edges:
            edge_data = edge.model_dump(
                mode="json",
                exclude={
                    "source",
                    "target",
                    "relation",
                },
                exclude_none=True,
            )

            edge_data["relation"] = edge.relation.value
            edge_data["evidence_count"] = len(edge.evidence)

            graph.add_edge(
                edge.source,
                edge.target,
                key=edge.networkx_key,
                **edge_data,
            )

        return graph

    def to_yaml(
        self,
        path: str | Path,
    ) -> None:
        target = Path(path)

        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = self.model_dump(
            mode="json",
            exclude_none=True,
        )

        with target.open(
            "w",
            encoding="utf-8",
        ) as file:
            yaml.safe_dump(
                payload,
                file,
                sort_keys=False,
                allow_unicode=True,
            )

    @classmethod
    def from_yaml(
        cls,
        path: str | Path,
    ) -> ArchitectureGraph:
        source = Path(path)

        with source.open(
            "r",
            encoding="utf-8",
        ) as file:
            payload = yaml.safe_load(file)

        if not isinstance(payload, dict):
            raise ValueError(
                f"Architecture graph YAML '{source}' "
                "must contain a mapping at the root level."
            )

        return cls.model_validate(payload)

    def to_json(
        self,
        path: str | Path,
    ) -> None:
        target = Path(path)

        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        target.write_text(
            self.model_dump_json(
                indent=2,
                exclude_none=True,
            ),
            encoding="utf-8",
        )

    @classmethod
    def from_json(
        cls,
        path: str | Path,
    ) -> ArchitectureGraph:
        source = Path(path)

        return cls.model_validate_json(
            source.read_text(
                encoding="utf-8"
            )
        )