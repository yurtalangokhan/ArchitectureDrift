from __future__ import annotations

import archdrift.model as model


EXPECTED_PUBLIC_API = {
    # Graph
    "ArchitectureGraph",
    "ArchitectureGraphError",
    "ArchitectureNode",
    "ArchitectureRelation",
    "DuplicateNodeError",
    "DuplicateRelationError",
    "GraphMetadata",
    "GraphRole",
    "NodeType",
    "RelationIdentity",
    "RelationType",
    "UnknownNodeError",
    "UnknownRelationError",

    # Evidence
    "EvidenceChannel",
    "EvidenceRecord",
    "EvidenceType",
    "deduplicate_evidence",

    # Contracts
    "ArchitectureContract",
    "ArchitectureContractBase",
    "ArchitectureContractDocument",
    "ArchitectureContractError",
    "CommunicationModeContract",
    "ContractDocumentLoadError",
    "ContractType",
    "ExposureContract",
    "ForbiddenRelationContract",
    "MediationContract",
    "RequiredRelationContract",
    "ResourceOwnershipContract",
    "UnknownContractError",
    "load_contract_document",
}


LEGACY_PUBLIC_API = {
    "ArchitectureEdge",
    "GraphView",
}


def test_model_public_api_is_explicit() -> None:
    assert set(model.__all__) == EXPECTED_PUBLIC_API


def test_public_api_exports_are_available() -> None:
    for name in EXPECTED_PUBLIC_API:
        assert hasattr(
            model,
            name,
        ), f"Missing public model export: {name}"


def test_legacy_graph_api_is_not_exported() -> None:
    for name in LEGACY_PUBLIC_API:
        assert not hasattr(
            model,
            name,
        ), f"Legacy public API must be removed: {name}"