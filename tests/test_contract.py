from pathlib import Path

import pytest
from pydantic import ValidationError

from archdrift.model import (
    ArchitectureContractDocument,
    CommunicationModeContract,
    ContractDocumentLoadError,
    ContractDocumentMetadata,
    ContractType,
    ExposureContract,
    ForbiddenRelationContract,
    MediationContract,
    RelationType,
    RequiredRelationContract,
    ResourceOwnershipContract,
    UnknownContractError,
    load_contract_document,
)

# =============================================================================
# Vocabulary
# =============================================================================


def test_contract_types_match_research_scope() -> None:
    assert set(ContractType) == {
        ContractType.FORBIDDEN_RELATION,
        ContractType.REQUIRED_RELATION,
        ContractType.RESOURCE_OWNERSHIP,
        ContractType.EXPOSURE,
        ContractType.MEDIATION,
        ContractType.COMMUNICATION_MODE,
    }


# =============================================================================
# Forbidden Relation
# =============================================================================


def test_forbidden_relation_contract_can_be_created() -> None:
    contract = ForbiddenRelationContract(
        id="AS-C001",
        source="checkout",
        relation=RelationType.CALLS,
        target="recommendation",
    )

    assert contract.type is ContractType.FORBIDDEN_RELATION

    assert contract.relation_identity == (
        "checkout",
        RelationType.CALLS,
        "recommendation",
    )


def test_contract_identifier_is_normalized() -> None:
    contract = ForbiddenRelationContract(
        id="  AS-C001  ",
        source="checkout",
        relation=RelationType.CALLS,
        target="recommendation",
    )

    assert contract.id == "AS-C001"


def test_contract_optional_text_is_normalized() -> None:
    contract = ForbiddenRelationContract(
        id="AS-C001",
        description="  Direct communication is forbidden.  ",
        rationale="   ",
        source="checkout",
        relation=RelationType.CALLS,
        target="recommendation",
    )

    assert contract.description == ("Direct communication is forbidden.")

    assert contract.rationale is None


# =============================================================================
# Required Relation
# =============================================================================


def test_required_relation_contract_can_be_created() -> None:
    contract = RequiredRelationContract(
        id="TEST-C001",
        source="frontend",
        relation=RelationType.CALLS,
        target="checkout",
    )

    assert contract.type is ContractType.REQUIRED_RELATION

    assert contract.relation_identity == (
        "frontend",
        RelationType.CALLS,
        "checkout",
    )


# =============================================================================
# Resource Ownership
# =============================================================================


def test_resource_ownership_defaults_to_read_write() -> None:
    contract = ResourceOwnershipContract(
        id="TEST-C002",
        owner="order-service",
        resource="order-db",
    )

    assert contract.relations == (
        RelationType.READS_FROM,
        RelationType.WRITES_TO,
    )


def test_resource_ownership_rejects_invalid_relation() -> None:
    with pytest.raises(
        ValidationError,
        match="RESOURCE_OWNERSHIP supports only",
    ):
        ResourceOwnershipContract(
            id="TEST-C002",
            owner="order-service",
            resource="order-db",
            relations=(RelationType.CALLS,),
        )


def test_resource_ownership_rejects_duplicate_relations() -> None:
    with pytest.raises(
        ValidationError,
        match="must not contain duplicates",
    ):
        ResourceOwnershipContract(
            id="TEST-C002",
            owner="order-service",
            resource="order-db",
            relations=(
                RelationType.READS_FROM,
                RelationType.READS_FROM,
            ),
        )


def test_resource_ownership_requires_distinct_nodes() -> None:
    with pytest.raises(
        ValidationError,
        match="distinct owner and resource",
    ):
        ResourceOwnershipContract(
            id="TEST-C002",
            owner="order-service",
            resource="order-service",
        )


# =============================================================================
# Exposure
# =============================================================================


def test_exposure_contract_can_be_created() -> None:
    contract = ExposureContract(
        id="TEST-C003",
        subject="checkout",
        allowed_targets=(
            "external-client",
            "frontend-proxy",
        ),
    )

    assert contract.allowed_targets == (
        "external-client",
        "frontend-proxy",
    )


def test_exposure_targets_are_deterministic() -> None:
    contract = ExposureContract(
        id="TEST-C003",
        subject="checkout",
        allowed_targets=(
            "frontend-proxy",
            "external-client",
        ),
    )

    assert contract.allowed_targets == (
        "external-client",
        "frontend-proxy",
    )


def test_exposure_requires_at_least_one_target() -> None:
    with pytest.raises(
        ValidationError,
        match="At least one identifier",
    ):
        ExposureContract(
            id="TEST-C003",
            subject="checkout",
            allowed_targets=(),
        )


def test_exposure_rejects_duplicate_targets() -> None:
    with pytest.raises(
        ValidationError,
        match="must not contain duplicates",
    ):
        ExposureContract(
            id="TEST-C003",
            subject="checkout",
            allowed_targets=(
                "frontend",
                "frontend",
            ),
        )


def test_exposure_rejects_subject_as_target() -> None:
    with pytest.raises(
        ValidationError,
        match="must not also appear",
    ):
        ExposureContract(
            id="TEST-C003",
            subject="checkout",
            allowed_targets=("checkout",),
        )


# =============================================================================
# Mediation
# =============================================================================


def test_mediation_contract_can_be_created() -> None:
    contract = MediationContract(
        id="TEST-C004",
        source="frontend",
        target="checkout",
        mediator="gateway",
        source_to_mediator_relation=RelationType.CALLS,
        mediator_to_target_relation=RelationType.ROUTES_TO,
        forbid_direct=True,
        direct_relation=RelationType.CALLS,
    )

    assert contract.source == "frontend"
    assert contract.mediator == "gateway"
    assert contract.target == "checkout"

    assert contract.source_to_mediator_relation is RelationType.CALLS

    assert contract.mediator_to_target_relation is RelationType.ROUTES_TO

    assert contract.direct_relation is RelationType.CALLS


def test_mediation_requires_distinct_nodes() -> None:
    with pytest.raises(
        ValidationError,
        match="distinct source, target",
    ):
        MediationContract(
            id="TEST-C004",
            source="frontend",
            target="checkout",
            mediator="frontend",
            source_to_mediator_relation=RelationType.CALLS,
            mediator_to_target_relation=RelationType.ROUTES_TO,
            direct_relation=RelationType.CALLS,
        )


def test_mediation_requires_direct_relation_when_forbidden() -> None:
    with pytest.raises(
        ValidationError,
        match="requires direct_relation",
    ):
        MediationContract(
            id="TEST-C004",
            source="frontend",
            target="checkout",
            mediator="gateway",
            source_to_mediator_relation=RelationType.CALLS,
            mediator_to_target_relation=RelationType.ROUTES_TO,
            forbid_direct=True,
        )


def test_mediation_rejects_unused_direct_relation() -> None:
    with pytest.raises(
        ValidationError,
        match="must be omitted",
    ):
        MediationContract(
            id="TEST-C004",
            source="frontend",
            target="checkout",
            mediator="gateway",
            source_to_mediator_relation=RelationType.CALLS,
            mediator_to_target_relation=RelationType.ROUTES_TO,
            forbid_direct=False,
            direct_relation=RelationType.CALLS,
        )


def test_mediation_can_allow_direct_relation() -> None:
    contract = MediationContract(
        id="TEST-C004",
        source="frontend",
        target="checkout",
        mediator="gateway",
        source_to_mediator_relation=RelationType.CALLS,
        mediator_to_target_relation=RelationType.ROUTES_TO,
        forbid_direct=False,
    )

    assert contract.direct_relation is None
    assert contract.forbid_direct is False


# =============================================================================
# Communication Mode
# =============================================================================


def test_communication_mode_contract_can_be_created() -> None:
    contract = CommunicationModeContract(
        id="TEST-C005",
        source="checkout",
        target="payment",
        allowed_relations=(RelationType.CALLS,),
    )

    assert contract.allowed_relations == (RelationType.CALLS,)


def test_communication_mode_requires_relation() -> None:
    with pytest.raises(
        ValidationError,
        match="At least one relation",
    ):
        CommunicationModeContract(
            id="TEST-C005",
            source="checkout",
            target="payment",
            allowed_relations=(),
        )


def test_communication_mode_rejects_duplicate_relations() -> None:
    with pytest.raises(
        ValidationError,
        match="must not contain duplicates",
    ):
        CommunicationModeContract(
            id="TEST-C005",
            source="checkout",
            target="payment",
            allowed_relations=(
                RelationType.CALLS,
                RelationType.CALLS,
            ),
        )


def test_communication_mode_requires_distinct_nodes() -> None:
    with pytest.raises(
        ValidationError,
        match="distinct source and target",
    ):
        CommunicationModeContract(
            id="TEST-C005",
            source="checkout",
            target="checkout",
            allowed_relations=(RelationType.CALLS,),
        )


# =============================================================================
# Discriminated Union
# =============================================================================


def test_document_resolves_all_contract_types() -> None:
    document = ArchitectureContractDocument.model_validate(
        {
            "schema_version": "1.0",
            "system_id": "test-system",
            "contracts": [
                {
                    "id": "C001",
                    "type": "FORBIDDEN_RELATION",
                    "source": "a",
                    "relation": "CALLS",
                    "target": "b",
                },
                {
                    "id": "C002",
                    "type": "REQUIRED_RELATION",
                    "source": "b",
                    "relation": "CALLS",
                    "target": "c",
                },
                {
                    "id": "C003",
                    "type": "RESOURCE_OWNERSHIP",
                    "owner": "a",
                    "resource": "db",
                },
                {
                    "id": "C004",
                    "type": "EXPOSURE",
                    "subject": "a",
                    "allowed_targets": ["external"],
                },
                {
                    "id": "C005",
                    "type": "MEDIATION",
                    "source": "a",
                    "target": "b",
                    "mediator": "gateway",
                    "source_to_mediator_relation": "CALLS",
                    "mediator_to_target_relation": "ROUTES_TO",
                    "forbid_direct": True,
                    "direct_relation": "CALLS",
                },
                {
                    "id": "C006",
                    "type": "COMMUNICATION_MODE",
                    "source": "a",
                    "target": "b",
                    "allowed_relations": ["CALLS"],
                },
            ],
        }
    )

    assert len(document.contracts) == 6

    assert isinstance(
        document.contracts[0],
        ForbiddenRelationContract,
    )

    assert isinstance(
        document.contracts[1],
        RequiredRelationContract,
    )

    assert isinstance(
        document.contracts[2],
        ResourceOwnershipContract,
    )

    assert isinstance(
        document.contracts[3],
        ExposureContract,
    )

    assert isinstance(
        document.contracts[4],
        MediationContract,
    )

    assert isinstance(
        document.contracts[5],
        CommunicationModeContract,
    )


# =============================================================================
# Contract Document
# =============================================================================


def test_document_rejects_duplicate_contract_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="duplicate contract identifiers",
    ):
        ArchitectureContractDocument.model_validate(
            {
                "system_id": "test-system",
                "contracts": [
                    {
                        "id": "C001",
                        "type": "FORBIDDEN_RELATION",
                        "source": "a",
                        "relation": "CALLS",
                        "target": "b",
                    },
                    {
                        "id": "C001",
                        "type": "REQUIRED_RELATION",
                        "source": "b",
                        "relation": "CALLS",
                        "target": "c",
                    },
                ],
            }
        )


def test_document_orders_contracts_deterministically() -> None:
    document = ArchitectureContractDocument(
        system_id="test-system",
        contracts=(
            RequiredRelationContract(
                id="C002",
                source="b",
                relation=RelationType.CALLS,
                target="c",
            ),
            ForbiddenRelationContract(
                id="C001",
                source="a",
                relation=RelationType.CALLS,
                target="b",
            ),
        ),
    )

    assert tuple(contract.id for contract in document.contracts) == (
        "C001",
        "C002",
    )


def test_document_can_get_contract_by_id() -> None:
    document = ArchitectureContractDocument(
        system_id="astronomy-shop",
        contracts=(
            ForbiddenRelationContract(
                id="AS-C001",
                source="checkout",
                relation=RelationType.CALLS,
                target="recommendation",
            ),
        ),
    )

    contract = document.get_contract("AS-C001")

    assert contract.id == "AS-C001"


def test_unknown_contract_lookup_raises_domain_error() -> None:
    document = ArchitectureContractDocument(system_id="astronomy-shop")

    with pytest.raises(UnknownContractError):
        document.get_contract("UNKNOWN")


def test_document_filters_contracts_by_type() -> None:
    document = ArchitectureContractDocument(
        system_id="test-system",
        contracts=(
            RequiredRelationContract(
                id="C002",
                source="b",
                relation=RelationType.CALLS,
                target="c",
            ),
            ForbiddenRelationContract(
                id="C001",
                source="a",
                relation=RelationType.CALLS,
                target="b",
            ),
        ),
    )

    result = document.contracts_of_type(ContractType.FORBIDDEN_RELATION)

    assert len(result) == 1
    assert result[0].id == "C001"


# =============================================================================
# Repository YAML
# =============================================================================


def test_load_astronomy_shop_contract_file() -> None:
    project_root = Path(__file__).resolve().parents[1]

    document = load_contract_document(
        project_root / "contracts" / "astronomy-shop.yaml"
    )

    assert document.system_id == "astronomy-shop"

    assert len(document.contracts) == 6

    assert document.contract_ids == frozenset(
        {
            "AS-C001",
            "AS-C002",
            "AS-C003",
            "AS-C004",
            "AS-C005",
            "AS-C006",
        }
    )

    assert document.get_contract("AS-C001").type is ContractType.FORBIDDEN_RELATION

    assert document.get_contract("AS-C002").type is ContractType.FORBIDDEN_RELATION

    assert document.get_contract("AS-C003").type is ContractType.FORBIDDEN_RELATION

    assert document.get_contract("AS-C004").type is ContractType.FORBIDDEN_RELATION

    assert document.get_contract("AS-C005").type is ContractType.FORBIDDEN_RELATION

    assert document.get_contract("AS-C006").type is ContractType.COMMUNICATION_MODE


# =============================================================================
# YAML Boundary
# =============================================================================


def test_loader_rejects_missing_file(
    tmp_path: Path,
) -> None:
    with pytest.raises(FileNotFoundError):
        load_contract_document(tmp_path / "missing.yaml")


def test_loader_rejects_empty_document(
    tmp_path: Path,
) -> None:
    contract_file = tmp_path / "empty.yaml"

    contract_file.write_text(
        "",
        encoding="utf-8",
    )

    with pytest.raises(
        ContractDocumentLoadError,
        match="empty",
    ):
        load_contract_document(contract_file)


def test_loader_rejects_non_mapping_root(
    tmp_path: Path,
) -> None:
    contract_file = tmp_path / "invalid-root.yaml"

    contract_file.write_text(
        "- item-one\n- item-two\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ContractDocumentLoadError,
        match="root must be a mapping",
    ):
        load_contract_document(contract_file)


def test_loader_rejects_invalid_yaml(
    tmp_path: Path,
) -> None:
    contract_file = tmp_path / "invalid.yaml"

    contract_file.write_text(
        "contracts: [\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ContractDocumentLoadError,
        match="Invalid YAML",
    ):
        load_contract_document(contract_file)


def test_contract_document_metadata_is_typed() -> None:
    document = ArchitectureContractDocument(
        system_id="astronomy-shop",
        metadata=ContractDocumentMetadata(
            case_system="OpenTelemetry Astronomy Shop",
            purpose="Controlled experiment",
            revision="abc123",
        ),
    )

    assert document.metadata.case_system == "OpenTelemetry Astronomy Shop"

    assert document.metadata.purpose == "Controlled experiment"

    assert document.metadata.revision == "abc123"


def test_contract_document_metadata_can_be_loaded_from_mapping() -> None:
    document = ArchitectureContractDocument.model_validate(
        {
            "system_id": "astronomy-shop",
            "metadata": {
                "case_system": "OpenTelemetry Astronomy Shop",
                "purpose": "Controlled experiment",
            },
        }
    )

    assert isinstance(
        document.metadata,
        ContractDocumentMetadata,
    )


def test_contract_ids_are_exposed_as_frozen_set() -> None:
    document = ArchitectureContractDocument(
        system_id="test-system",
        contracts=(
            ForbiddenRelationContract(
                id="C001",
                source="a",
                relation=RelationType.CALLS,
                target="b",
            ),
            RequiredRelationContract(
                id="C002",
                source="b",
                relation=RelationType.CALLS,
                target="c",
            ),
        ),
    )

    assert document.contract_ids == frozenset(
        {
            "C001",
            "C002",
        }
    )


def test_contract_document_json_round_trip() -> None:
    document = ArchitectureContractDocument(
        system_id="astronomy-shop",
        metadata=ContractDocumentMetadata(
            case_system="OpenTelemetry Astronomy Shop",
            purpose="Controlled experiment",
        ),
        contracts=(
            ForbiddenRelationContract(
                id="AS-C001",
                source="checkout",
                relation=RelationType.CALLS,
                target="recommendation",
            ),
        ),
    )

    serialized = document.model_dump_json()

    restored = ArchitectureContractDocument.model_validate_json(serialized)

    assert restored == document


def test_contract_document_is_deterministic() -> None:
    document = ArchitectureContractDocument(
        system_id="test-system",
        contracts=(
            RequiredRelationContract(
                id="C002",
                source="b",
                relation=RelationType.CALLS,
                target="c",
            ),
            ForbiddenRelationContract(
                id="C001",
                source="a",
                relation=RelationType.CALLS,
                target="b",
            ),
        ),
    )

    assert tuple(contract.id for contract in document.contracts) == (
        "C001",
        "C002",
    )


def test_repository_astronomy_contract_metadata() -> None:
    project_root = Path(__file__).resolve().parents[1]

    document = load_contract_document(
        project_root / "contracts" / "astronomy-shop.yaml"
    )

    assert document.metadata.case_system == "OpenTelemetry Astronomy Shop"

    assert (
        document.metadata.purpose
        == "Controlled multi-evidence architecture-conformance experiment"
    )

    assert document.metadata.revision == "AS-CONTRACTS-02"

    assert document.contract_ids == frozenset(
        {
            "AS-C001",
            "AS-C002",
            "AS-C003",
            "AS-C004",
            "AS-C005",
            "AS-C006",
        }
    )
