from pathlib import Path

import pytest

from archdrift.analysis import (
    ConformanceEvaluationError,
    ConformanceStatus,
    evaluate_contract,
    evaluate_contract_document,
)
from archdrift.model import (
    ArchitectureContractDocument,
    ArchitectureGraph,
    ArchitectureNode,
    ArchitectureRelation,
    CommunicationModeContract,
    ExposureContract,
    ForbiddenRelationContract,
    GraphMetadata,
    GraphRole,
    MediationContract,
    NodeType,
    RelationType,
    RequiredRelationContract,
    ResourceOwnershipContract,
    load_contract_document,
    load_mutation_oracle,
)


def build_graph(
    *,
    role: GraphRole = GraphRole.BASELINE,
    variant: str | None = None,
    relations: tuple[ArchitectureRelation, ...] = (),
) -> ArchitectureGraph:
    return ArchitectureGraph(
        metadata=GraphMetadata(
            system_id="astronomy-shop",
            role=role,
            variant=variant,
        ),
        nodes=(
            ArchitectureNode(
                id="checkout",
                type=NodeType.SERVICE,
            ),
            ArchitectureNode(
                id="recommendation",
                type=NodeType.SERVICE,
            ),
            ArchitectureNode(
                id="payment",
                type=NodeType.SERVICE,
            ),
            ArchitectureNode(
                id="gateway",
                type=NodeType.GATEWAY,
            ),
            ArchitectureNode(
                id="order-db",
                type=NodeType.DATASTORE,
            ),
            ArchitectureNode(
                id="external",
                type=NodeType.EXTERNAL,
            ),
        ),
        relations=relations,
    )


# =============================================================================
# FORBIDDEN_RELATION
# =============================================================================


def test_forbidden_relation_is_satisfied_when_absent() -> None:
    graph = build_graph()

    contract = ForbiddenRelationContract(
        id="C001",
        source="checkout",
        relation=RelationType.CALLS,
        target="recommendation",
    )

    result = evaluate_contract(
        graph,
        contract,
    )

    assert result.status is ConformanceStatus.SATISFIED


def test_forbidden_relation_is_violated_when_present() -> None:
    relation = ArchitectureRelation(
        source="checkout",
        relation=RelationType.CALLS,
        target="recommendation",
    )

    graph = build_graph(
        relations=(
            relation,
        )
    )

    contract = ForbiddenRelationContract(
        id="C001",
        source="checkout",
        relation=RelationType.CALLS,
        target="recommendation",
    )

    result = evaluate_contract(
        graph,
        contract,
    )

    assert result.status is ConformanceStatus.VIOLATED
    assert result.violating_relations == (relation,)


# =============================================================================
# REQUIRED_RELATION
# =============================================================================


def test_required_relation_is_violated_when_missing() -> None:
    graph = build_graph()

    contract = RequiredRelationContract(
        id="C002",
        source="checkout",
        relation=RelationType.CALLS,
        target="payment",
    )

    result = evaluate_contract(
        graph,
        contract,
    )

    assert result.status is ConformanceStatus.VIOLATED

    assert result.missing_required_relations == (
        ArchitectureRelation(
            source="checkout",
            relation=RelationType.CALLS,
            target="payment",
        ),
    )


# =============================================================================
# NOT_EVALUABLE
# =============================================================================


def test_missing_referenced_node_is_not_evaluable() -> None:
    graph = build_graph()

    contract = ForbiddenRelationContract(
        id="C003",
        source="checkout",
        relation=RelationType.CALLS,
        target="missing-service",
    )

    result = evaluate_contract(
        graph,
        contract,
    )

    assert (
        result.status
        is ConformanceStatus.NOT_EVALUABLE
    )

    assert result.missing_nodes == (
        "missing-service",
    )


# =============================================================================
# RESOURCE_OWNERSHIP
# =============================================================================


def test_resource_ownership_detects_non_owner_access() -> None:
    graph = build_graph(
        relations=(
            ArchitectureRelation(
                source="payment",
                relation=RelationType.READS_FROM,
                target="order-db",
            ),
        )
    )

    contract = ResourceOwnershipContract(
        id="C004",
        owner="checkout",
        resource="order-db",
    )

    result = evaluate_contract(
        graph,
        contract,
    )

    assert result.status is ConformanceStatus.VIOLATED

    assert len(result.violating_relations) == 1


def test_resource_ownership_allows_owner_access() -> None:
    graph = build_graph(
        relations=(
            ArchitectureRelation(
                source="checkout",
                relation=RelationType.WRITES_TO,
                target="order-db",
            ),
        )
    )

    contract = ResourceOwnershipContract(
        id="C004",
        owner="checkout",
        resource="order-db",
    )

    result = evaluate_contract(
        graph,
        contract,
    )

    assert result.status is ConformanceStatus.SATISFIED


# =============================================================================
# EXPOSURE
# =============================================================================


def test_exposure_detects_disallowed_target() -> None:
    graph = build_graph(
        relations=(
            ArchitectureRelation(
                source="checkout",
                relation=RelationType.EXPOSES_TO,
                target="payment",
            ),
        )
    )

    contract = ExposureContract(
        id="C005",
        subject="checkout",
        allowed_targets=(
            "external",
        ),
    )

    result = evaluate_contract(
        graph,
        contract,
    )

    assert result.status is ConformanceStatus.VIOLATED


def test_required_exposure_is_violated_when_absent() -> None:
    graph = build_graph()

    contract = ExposureContract(
        id="C005",
        subject="checkout",
        allowed_targets=(
            "external",
        ),
        require_exposure=True,
    )

    result = evaluate_contract(
        graph,
        contract,
    )

    assert result.status is ConformanceStatus.VIOLATED


# =============================================================================
# MEDIATION
# =============================================================================


def test_mediation_is_satisfied() -> None:
    graph = build_graph(
        relations=(
            ArchitectureRelation(
                source="checkout",
                relation=RelationType.CALLS,
                target="gateway",
            ),
            ArchitectureRelation(
                source="gateway",
                relation=RelationType.ROUTES_TO,
                target="payment",
            ),
        )
    )

    contract = MediationContract(
        id="C006",
        source="checkout",
        target="payment",
        mediator="gateway",
        source_to_mediator_relation=RelationType.CALLS,
        mediator_to_target_relation=RelationType.ROUTES_TO,
        forbid_direct=True,
        direct_relation=RelationType.CALLS,
    )

    result = evaluate_contract(
        graph,
        contract,
    )

    assert result.status is ConformanceStatus.SATISFIED


def test_mediation_detects_direct_bypass() -> None:
    direct = ArchitectureRelation(
        source="checkout",
        relation=RelationType.CALLS,
        target="payment",
    )

    graph = build_graph(
        relations=(
            ArchitectureRelation(
                source="checkout",
                relation=RelationType.CALLS,
                target="gateway",
            ),
            ArchitectureRelation(
                source="gateway",
                relation=RelationType.ROUTES_TO,
                target="payment",
            ),
            direct,
        )
    )

    contract = MediationContract(
        id="C006",
        source="checkout",
        target="payment",
        mediator="gateway",
        source_to_mediator_relation=RelationType.CALLS,
        mediator_to_target_relation=RelationType.ROUTES_TO,
        forbid_direct=True,
        direct_relation=RelationType.CALLS,
    )

    result = evaluate_contract(
        graph,
        contract,
    )

    assert result.status is ConformanceStatus.VIOLATED
    assert direct in result.violating_relations


# =============================================================================
# COMMUNICATION_MODE
# =============================================================================


def test_communication_mode_detects_disallowed_relation() -> None:
    graph = build_graph(
        relations=(
            ArchitectureRelation(
                source="checkout",
                relation=RelationType.PUBLISHES_TO,
                target="payment",
            ),
        )
    )

    contract = CommunicationModeContract(
        id="C007",
        source="checkout",
        target="payment",
        allowed_relations=(
            RelationType.CALLS,
        ),
    )

    result = evaluate_contract(
        graph,
        contract,
    )

    assert result.status is ConformanceStatus.VIOLATED


# =============================================================================
# Document Evaluation
# =============================================================================


def test_contract_document_requires_same_system() -> None:
    graph = build_graph()

    document = ArchitectureContractDocument(
        system_id="eshop",
    )

    with pytest.raises(
        ConformanceEvaluationError,
        match="different systems",
    ):
        evaluate_contract_document(
            graph,
            document,
        )


# =============================================================================
# AS-M01 Vertical Slice
# =============================================================================


def test_as_m01_violates_repository_contract() -> None:
    project_root = Path(__file__).resolve().parents[1]

    document = load_contract_document(
        project_root
        / "contracts"
        / "astronomy-shop.yaml"
    )

    oracle = load_mutation_oracle(
        project_root
        / "mutations"
        / "astronomy-shop"
        / "AS-M01.yaml"
    )

    mutant = build_graph(
        role=GraphRole.MUTANT,
        variant="AS-M01",
        relations=(
            ArchitectureRelation(
                source="checkout",
                relation=RelationType.CALLS,
                target="recommendation",
            ),
        ),
    )

    report = evaluate_contract_document(
        mutant,
        document,
    )

    assert report.violated_contract_ids == frozenset(
        oracle.expected_violated_contracts
    )

    assert report.is_conformant is False


def test_as_m01_baseline_satisfies_repository_contract() -> None:
    project_root = Path(__file__).resolve().parents[1]

    document = load_contract_document(
        project_root
        / "contracts"
        / "astronomy-shop.yaml"
    )

    baseline = build_graph()

    report = evaluate_contract_document(
        baseline,
        document,
    )

    assert report.violated_contract_ids == frozenset()
    assert report.not_evaluable_contract_ids == frozenset()
    assert report.is_conformant is True