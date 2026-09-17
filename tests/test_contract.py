from pathlib import Path

import pytest
from pydantic import ValidationError

from archdrift.model import (
    ArchitectureContractDocument,
    CommunicationModeContract,
    ContractType,
    ExposureContract,
    ForbiddenRelationContract,
    MediationContract,
    RelationType,
    RequiredRelationContract,
    ResourceOwnershipContract,
    load_contract_document,
)

# =============================================================================
# Contract Type Vocabulary
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

    assert contract.type == ContractType.FORBIDDEN_RELATION

    assert contract.source == "checkout"

    assert contract.relation == RelationType.CALLS

    assert contract.target == "recommendation"


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

    assert contract.type == ContractType.REQUIRED_RELATION

    assert contract.relation == RelationType.CALLS


# =============================================================================
# Resource Ownership
# =============================================================================


def test_resource_ownership_contract_can_be_created() -> None:
    contract = ResourceOwnershipContract(
        id="TEST-C002",
        owner="order-service",
        resource="order-db",
    )

    assert contract.owner == "order-service"

    assert contract.resource == "order-db"

    assert contract.relations == (
        RelationType.READS_FROM,
        RelationType.WRITES_TO,
    )


def test_resource_ownership_rejects_invalid_relation() -> None:
    with pytest.raises(
        ValidationError,
        match="RESOURCE_OWNERSHIP",
    ):
        ResourceOwnershipContract(
            id="TEST-C002",
            owner="order-service",
            resource="order-db",
            relations=(
                RelationType.CALLS,
            ),
        )


# =============================================================================
# Exposure
# =============================================================================


def test_exposure_contract_can_be_created() -> None:
    contract = ExposureContract(
        id="TEST-C003",
        subject="checkout",
        allowed_targets=(
            "frontend-proxy",
        ),
    )

    assert contract.type == ContractType.EXPOSURE

    assert contract.subject == "checkout"

    assert contract.allowed_targets == (
        "frontend-proxy",
    )


def test_exposure_contract_rejects_empty_targets() -> None:
    with pytest.raises(
        ValidationError,
        match="At least one identifier",
    ):
        ExposureContract(
            id="TEST-C003",
            subject="checkout",
            allowed_targets=(),
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
    )

    assert contract.type == ContractType.MEDIATION

    assert contract.source == "frontend"

    assert contract.target == "checkout"

    assert contract.mediator == "gateway"

    assert contract.forbid_direct is True


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
        )


# =============================================================================
# Communication Mode
# =============================================================================


def test_communication_mode_contract_can_be_created() -> None:
    contract = CommunicationModeContract(
        id="TEST-C005",
        source="checkout",
        target="payment",
        allowed_relations=(
            RelationType.CALLS,
        ),
    )

    assert contract.type == ContractType.COMMUNICATION_MODE

    assert contract.allowed_relations == (
        RelationType.CALLS,
    )


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


# =============================================================================
# Discriminated Union
# =============================================================================


def test_document_resolves_forbidden_relation_contract() -> None:
    document = ArchitectureContractDocument.model_validate(
        {
            "schema_version": "1.0",
            "system_id": "astronomy-shop",
            "contracts": [
                {
                    "id": "AS-C001",
                    "type": "FORBIDDEN_RELATION",
                    "source": "checkout",
                    "relation": "CALLS",
                    "target": "recommendation",
                }
            ],
        }
    )

    assert len(document.contracts) == 1

    contract = document.contracts[0]

    assert isinstance(
        contract,
        ForbiddenRelationContract,
    )

    assert contract.type == ContractType.FORBIDDEN_RELATION


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
                    "allowed_targets": [
                        "external"
                    ],
                },
                {
                    "id": "C005",
                    "type": "MEDIATION",
                    "source": "a",
                    "target": "b",
                    "mediator": "gateway",
                    "source_to_mediator_relation": "CALLS",
                    "mediator_to_target_relation": "ROUTES_TO",
                },
                {
                    "id": "C006",
                    "type": "COMMUNICATION_MODE",
                    "source": "a",
                    "target": "b",
                    "allowed_relations": [
                        "CALLS"
                    ],
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
# Document Validation
# =============================================================================


def test_document_rejects_duplicate_contract_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="duplicate contract identifiers",
    ):
        ArchitectureContractDocument.model_validate(
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
                        "id": "C001",
                        "type": "REQUIRED_RELATION",
                        "source": "b",
                        "relation": "CALLS",
                        "target": "c",
                    },
                ],
            }
        )


def test_document_can_get_contract_by_id() -> None:
    document = ArchitectureContractDocument(
        system_id="astronomy-shop",
        contracts=[
            ForbiddenRelationContract(
                id="AS-C001",
                source="checkout",
                relation=RelationType.CALLS,
                target="recommendation",
            )
        ],
    )

    contract = document.get_contract(
        "AS-C001"
    )

    assert contract.id == "AS-C001"


def test_document_rejects_unknown_contract_lookup() -> None:
    document = ArchitectureContractDocument(
        system_id="astronomy-shop",
    )

    with pytest.raises(KeyError):
        document.get_contract(
            "UNKNOWN"
        )


# =============================================================================
# YAML Loading
# =============================================================================


def test_load_astronomy_shop_contract_file() -> None:
    project_root = Path(__file__).resolve().parents[1]

    contract_path = (
        project_root
        / "contracts"
        / "astronomy-shop.yaml"
    )

    document = load_contract_document(
        contract_path
    )

    assert document.system_id == "astronomy-shop"

    assert len(document.contracts) == 1

    contract = document.get_contract(
        "AS-C001"
    )

    assert isinstance(
        contract,
        ForbiddenRelationContract,
    )

    assert contract.source == "checkout"

    assert contract.target == "recommendation"

    assert contract.relation == RelationType.CALLS


def test_loader_rejects_missing_file() -> None:
    with pytest.raises(
        FileNotFoundError
    ):
        load_contract_document(
            "does-not-exist.yaml"
        )