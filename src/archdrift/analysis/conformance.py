from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from archdrift.model.contract import (
    ArchitectureContract,
    ArchitectureContractDocument,
    CommunicationModeContract,
    ContractType,
    ExposureContract,
    ForbiddenRelationContract,
    MediationContract,
    RequiredRelationContract,
    ResourceOwnershipContract,
)
from archdrift.model.graph import (
    ArchitectureGraph,
    ArchitectureRelation,
    GraphMetadata,
    RelationType,
)

# =============================================================================
# Exceptions
# =============================================================================


class ConformanceError(ValueError):
    """Base exception for architecture conformance evaluation."""


class ConformanceEvaluationError(ConformanceError):
    """Raised when a graph and contract document cannot be evaluated together."""


# =============================================================================
# Result Vocabulary
# =============================================================================


class ConformanceStatus(StrEnum):
    """
    Result of evaluating one architecture contract.

    NOT_EVALUABLE is distinct from SATISFIED.

    A contract cannot be considered satisfied when referenced architectural
    elements are missing from the reconstructed graph.
    """

    SATISFIED = "SATISFIED"
    VIOLATED = "VIOLATED"
    NOT_EVALUABLE = "NOT_EVALUABLE"


# =============================================================================
# Contract Evaluation Result
# =============================================================================


class ContractEvaluation(BaseModel):
    """
    Immutable result of evaluating one architecture contract.

    observed_relations:
        Relevant canonical relations found in the evaluated graph.

    violating_relations:
        Observed relations directly responsible for a violation.

    missing_required_relations:
        Exact canonical relations that were required but absent.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    contract_id: str

    contract_type: ContractType

    status: ConformanceStatus

    message: str

    observed_relations: tuple[ArchitectureRelation, ...] = ()

    violating_relations: tuple[ArchitectureRelation, ...] = ()

    missing_required_relations: tuple[ArchitectureRelation, ...] = ()

    missing_nodes: tuple[str, ...] = ()

    @field_validator(
        "observed_relations",
        "violating_relations",
        "missing_required_relations",
    )
    @classmethod
    def normalize_relations(
        cls,
        value: tuple[ArchitectureRelation, ...],
    ) -> tuple[ArchitectureRelation, ...]:
        identities = tuple(
            relation.identity
            for relation in value
        )

        if len(identities) != len(set(identities)):
            raise ValueError(
                "Conformance evaluation contains duplicate relations."
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

    @field_validator("missing_nodes")
    @classmethod
    def normalize_missing_nodes(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError(
                "Missing nodes must not contain duplicates."
            )

        return tuple(sorted(value))

    @model_validator(mode="after")
    def validate_relation_sets(
        self,
    ) -> Self:
        observed = {
            relation.identity
            for relation in self.observed_relations
        }

        violating = {
            relation.identity
            for relation in self.violating_relations
        }

        missing = {
            relation.identity
            for relation in self.missing_required_relations
        }

        if not violating.issubset(observed):
            raise ValueError(
                "Violating relations must also be present in "
                "observed_relations."
            )

        if observed & missing:
            raise ValueError(
                "A relation cannot be both observed and missing."
            )

        return self


# =============================================================================
# Conformance Report
# =============================================================================


class ConformanceReport(BaseModel):
    """
    Immutable conformance report for one canonical architecture graph.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    graph: GraphMetadata

    contract_system_id: str

    evaluations: tuple[ContractEvaluation, ...]

    @field_validator("evaluations")
    @classmethod
    def normalize_evaluations(
        cls,
        value: tuple[ContractEvaluation, ...],
    ) -> tuple[ContractEvaluation, ...]:
        contract_ids = tuple(
            evaluation.contract_id
            for evaluation in value
        )

        if len(contract_ids) != len(set(contract_ids)):
            raise ValueError(
                "Conformance report contains duplicate contract evaluations."
            )

        return tuple(
            sorted(
                value,
                key=lambda evaluation: evaluation.contract_id,
            )
        )

    @property
    def satisfied_contract_ids(self) -> frozenset[str]:
        return frozenset(
            evaluation.contract_id
            for evaluation in self.evaluations
            if evaluation.status is ConformanceStatus.SATISFIED
        )

    @property
    def violated_contract_ids(self) -> frozenset[str]:
        return frozenset(
            evaluation.contract_id
            for evaluation in self.evaluations
            if evaluation.status is ConformanceStatus.VIOLATED
        )

    @property
    def not_evaluable_contract_ids(self) -> frozenset[str]:
        return frozenset(
            evaluation.contract_id
            for evaluation in self.evaluations
            if evaluation.status is ConformanceStatus.NOT_EVALUABLE
        )

    @property
    def has_violations(self) -> bool:
        return bool(
            self.violated_contract_ids
        )

    @property
    def is_fully_evaluable(self) -> bool:
        return not self.not_evaluable_contract_ids

    @property
    def is_conformant(self) -> bool:
        """
        A graph is conformant only when every contract is evaluable
        and none is violated.
        """

        return (
            self.is_fully_evaluable
            and not self.has_violations
        )


# =============================================================================
# Internal Helpers
# =============================================================================


def _missing_nodes(
    graph: ArchitectureGraph,
    *node_ids: str,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            node_id
            for node_id in set(node_ids)
            if node_id not in graph.node_ids
        )
    )


def _not_evaluable(
    contract: ArchitectureContract,
    missing_nodes: tuple[str, ...],
) -> ContractEvaluation:
    return ContractEvaluation(
        contract_id=contract.id,
        contract_type=contract.type,
        status=ConformanceStatus.NOT_EVALUABLE,
        message=(
            "Contract cannot be evaluated because referenced "
            "architecture node(s) are missing: "
            + ", ".join(missing_nodes)
        ),
        missing_nodes=missing_nodes,
    )


# =============================================================================
# FORBIDDEN_RELATION
# =============================================================================


def _evaluate_forbidden_relation(
    graph: ArchitectureGraph,
    contract: ForbiddenRelationContract,
) -> ContractEvaluation:
    missing = _missing_nodes(
        graph,
        contract.source,
        contract.target,
    )

    if missing:
        return _not_evaluable(
            contract,
            missing,
        )

    observed = graph.get_relation(
        source=contract.source,
        relation=contract.relation,
        target=contract.target,
    )

    if observed is not None:
        return ContractEvaluation(
            contract_id=contract.id,
            contract_type=contract.type,
            status=ConformanceStatus.VIOLATED,
            message=(
                "Forbidden architecture relation exists."
            ),
            observed_relations=(
                observed,
            ),
            violating_relations=(
                observed,
            ),
        )

    return ContractEvaluation(
        contract_id=contract.id,
        contract_type=contract.type,
        status=ConformanceStatus.SATISFIED,
        message=(
            "Forbidden architecture relation is absent."
        ),
    )


# =============================================================================
# REQUIRED_RELATION
# =============================================================================


def _evaluate_required_relation(
    graph: ArchitectureGraph,
    contract: RequiredRelationContract,
) -> ContractEvaluation:
    missing = _missing_nodes(
        graph,
        contract.source,
        contract.target,
    )

    if missing:
        return _not_evaluable(
            contract,
            missing,
        )

    observed = graph.get_relation(
        source=contract.source,
        relation=contract.relation,
        target=contract.target,
    )

    if observed is not None:
        return ContractEvaluation(
            contract_id=contract.id,
            contract_type=contract.type,
            status=ConformanceStatus.SATISFIED,
            message=(
                "Required architecture relation exists."
            ),
            observed_relations=(
                observed,
            ),
        )

    expected = ArchitectureRelation(
        source=contract.source,
        relation=contract.relation,
        target=contract.target,
    )

    return ContractEvaluation(
        contract_id=contract.id,
        contract_type=contract.type,
        status=ConformanceStatus.VIOLATED,
        message=(
            "Required architecture relation is missing."
        ),
        missing_required_relations=(
            expected,
        ),
    )


# =============================================================================
# RESOURCE_OWNERSHIP
# =============================================================================


def _evaluate_resource_ownership(
    graph: ArchitectureGraph,
    contract: ResourceOwnershipContract,
) -> ContractEvaluation:
    missing = _missing_nodes(
        graph,
        contract.owner,
        contract.resource,
    )

    if missing:
        return _not_evaluable(
            contract,
            missing,
        )

    observed = tuple(
        relation
        for relation in graph.find_relations(
            target=contract.resource
        )
        if relation.relation in contract.relations
    )

    violating = tuple(
        relation
        for relation in observed
        if relation.source != contract.owner
    )

    if violating:
        return ContractEvaluation(
            contract_id=contract.id,
            contract_type=contract.type,
            status=ConformanceStatus.VIOLATED,
            message=(
                "Resource is accessed by a non-owner architecture node."
            ),
            observed_relations=observed,
            violating_relations=violating,
        )

    return ContractEvaluation(
        contract_id=contract.id,
        contract_type=contract.type,
        status=ConformanceStatus.SATISFIED,
        message=(
            "No non-owner resource access was observed."
        ),
        observed_relations=observed,
    )


# =============================================================================
# EXPOSURE
# =============================================================================


def _evaluate_exposure(
    graph: ArchitectureGraph,
    contract: ExposureContract,
) -> ContractEvaluation:
    missing = _missing_nodes(
        graph,
        contract.subject,
        *contract.allowed_targets,
    )

    if missing:
        return _not_evaluable(
            contract,
            missing,
        )

    observed = graph.find_relations(
        source=contract.subject,
        relation=RelationType.EXPOSES_TO,
    )

    allowed_targets = set(
        contract.allowed_targets
    )

    violating = tuple(
        relation
        for relation in observed
        if relation.target not in allowed_targets
    )

    allowed_observed = tuple(
        relation
        for relation in observed
        if relation.target in allowed_targets
    )

    if violating:
        return ContractEvaluation(
            contract_id=contract.id,
            contract_type=contract.type,
            status=ConformanceStatus.VIOLATED,
            message=(
                "Architecture node is exposed to a disallowed target."
            ),
            observed_relations=observed,
            violating_relations=violating,
        )

    if (
        contract.require_exposure
        and not allowed_observed
    ):
        return ContractEvaluation(
            contract_id=contract.id,
            contract_type=contract.type,
            status=ConformanceStatus.VIOLATED,
            message=(
                "Required allowed exposure was not observed."
            ),
            observed_relations=observed,
        )

    return ContractEvaluation(
        contract_id=contract.id,
        contract_type=contract.type,
        status=ConformanceStatus.SATISFIED,
        message=(
            "Observed exposures satisfy the architecture contract."
        ),
        observed_relations=observed,
    )


# =============================================================================
# MEDIATION
# =============================================================================


def _evaluate_mediation(
    graph: ArchitectureGraph,
    contract: MediationContract,
) -> ContractEvaluation:
    missing = _missing_nodes(
        graph,
        contract.source,
        contract.mediator,
        contract.target,
    )

    if missing:
        return _not_evaluable(
            contract,
            missing,
        )

    source_to_mediator = graph.get_relation(
        source=contract.source,
        relation=contract.source_to_mediator_relation,
        target=contract.mediator,
    )

    mediator_to_target = graph.get_relation(
        source=contract.mediator,
        relation=contract.mediator_to_target_relation,
        target=contract.target,
    )

    observed = tuple(
        relation
        for relation in (
            source_to_mediator,
            mediator_to_target,
        )
        if relation is not None
    )

    missing_required: list[
        ArchitectureRelation
    ] = []

    if source_to_mediator is None:
        missing_required.append(
            ArchitectureRelation(
                source=contract.source,
                relation=contract.source_to_mediator_relation,
                target=contract.mediator,
            )
        )

    if mediator_to_target is None:
        missing_required.append(
            ArchitectureRelation(
                source=contract.mediator,
                relation=contract.mediator_to_target_relation,
                target=contract.target,
            )
        )

    violating: tuple[
        ArchitectureRelation,
        ...,
    ] = ()

    direct_relation = None

    if (
        contract.forbid_direct
        and contract.direct_relation is not None
    ):
        direct_relation = graph.get_relation(
            source=contract.source,
            relation=contract.direct_relation,
            target=contract.target,
        )

        if direct_relation is not None:
            violating = (
                direct_relation,
            )

            observed = (
                *observed,
                direct_relation,
            )

    if violating or missing_required:
        return ContractEvaluation(
            contract_id=contract.id,
            contract_type=contract.type,
            status=ConformanceStatus.VIOLATED,
            message=(
                "Required mediation semantics are not satisfied."
            ),
            observed_relations=observed,
            violating_relations=violating,
            missing_required_relations=tuple(
                missing_required
            ),
        )

    return ContractEvaluation(
        contract_id=contract.id,
        contract_type=contract.type,
        status=ConformanceStatus.SATISFIED,
        message=(
            "Communication is mediated as required."
        ),
        observed_relations=observed,
    )


# =============================================================================
# COMMUNICATION_MODE
# =============================================================================


def _evaluate_communication_mode(
    graph: ArchitectureGraph,
    contract: CommunicationModeContract,
) -> ContractEvaluation:
    missing = _missing_nodes(
        graph,
        contract.source,
        contract.target,
    )

    if missing:
        return _not_evaluable(
            contract,
            missing,
        )

    observed = graph.find_relations(
        source=contract.source,
        target=contract.target,
    )

    allowed = set(
        contract.allowed_relations
    )

    violating = tuple(
        relation
        for relation in observed
        if relation.relation not in allowed
    )

    if violating:
        return ContractEvaluation(
            contract_id=contract.id,
            contract_type=contract.type,
            status=ConformanceStatus.VIOLATED,
            message=(
                "Disallowed communication mode was observed."
            ),
            observed_relations=observed,
            violating_relations=violating,
        )

    return ContractEvaluation(
        contract_id=contract.id,
        contract_type=contract.type,
        status=ConformanceStatus.SATISFIED,
        message=(
            "Observed communication modes are allowed."
        ),
        observed_relations=observed,
    )


# =============================================================================
# Public Evaluation API
# =============================================================================


def evaluate_contract(
    graph: ArchitectureGraph,
    contract: ArchitectureContract,
) -> ContractEvaluation:
    """
    Evaluate one architecture contract against one canonical graph.
    """

    if isinstance(
        contract,
        ForbiddenRelationContract,
    ):
        return _evaluate_forbidden_relation(
            graph,
            contract,
        )

    if isinstance(
        contract,
        RequiredRelationContract,
    ):
        return _evaluate_required_relation(
            graph,
            contract,
        )

    if isinstance(
        contract,
        ResourceOwnershipContract,
    ):
        return _evaluate_resource_ownership(
            graph,
            contract,
        )

    if isinstance(
        contract,
        ExposureContract,
    ):
        return _evaluate_exposure(
            graph,
            contract,
        )

    if isinstance(
        contract,
        MediationContract,
    ):
        return _evaluate_mediation(
            graph,
            contract,
        )

    if isinstance(
        contract,
        CommunicationModeContract,
    ):
        return _evaluate_communication_mode(
            graph,
            contract,
        )

    raise TypeError(
        f"Unsupported architecture contract: {type(contract)!r}"
    )


def evaluate_contract_document(
    graph: ArchitectureGraph,
    document: ArchitectureContractDocument,
) -> ConformanceReport:
    """
    Evaluate every contract in one architecture contract document.
    """

    if (
        graph.metadata.system_id
        != document.system_id
    ):
        raise ConformanceEvaluationError(
            "Architecture graph and contract document belong "
            "to different systems: "
            f"{graph.metadata.system_id!r} != "
            f"{document.system_id!r}"
        )

    evaluations = tuple(
        evaluate_contract(
            graph,
            contract,
        )
        for contract in document.contracts
    )

    return ConformanceReport(
        graph=graph.metadata,
        contract_system_id=document.system_id,
        evaluations=evaluations,
    )