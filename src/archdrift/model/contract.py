from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal, Self

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from archdrift.model.graph import RelationType

# =============================================================================
# Contract Vocabulary
# =============================================================================


class ContractType(StrEnum):
    """
    Supported architecture contract types.

    Contract types intentionally describe architectural expectations rather
    than implementation-specific evidence.
    """

    FORBIDDEN_RELATION = "FORBIDDEN_RELATION"
    REQUIRED_RELATION = "REQUIRED_RELATION"
    RESOURCE_OWNERSHIP = "RESOURCE_OWNERSHIP"
    EXPOSURE = "EXPOSURE"
    MEDIATION = "MEDIATION"
    COMMUNICATION_MODE = "COMMUNICATION_MODE"


# =============================================================================
# Validation Helpers
# =============================================================================


def _validate_identifier(value: str) -> str:
    """
    Validate canonical identifiers used by architecture contracts.
    """

    normalized = value.strip()

    if not normalized:
        raise ValueError("Identifier must not be empty.")

    if any(character.isspace() for character in normalized):
        raise ValueError(
            f"Identifier must not contain whitespace: {value!r}"
        )

    return normalized


def _validate_unique_relation_types(
    relations: tuple[RelationType, ...],
) -> tuple[RelationType, ...]:
    """
    Ensure a relation collection is non-empty and contains no duplicates.
    """

    if not relations:
        raise ValueError(
            "At least one relation type must be specified."
        )

    if len(relations) != len(set(relations)):
        raise ValueError(
            "Relation types must not contain duplicates."
        )

    return relations


def _validate_unique_identifiers(
    identifiers: tuple[str, ...],
) -> tuple[str, ...]:
    """
    Ensure an identifier collection is non-empty and unique.
    """

    if not identifiers:
        raise ValueError(
            "At least one identifier must be specified."
        )

    normalized = tuple(
        _validate_identifier(identifier)
        for identifier in identifiers
    )

    if len(normalized) != len(set(normalized)):
        raise ValueError(
            "Identifiers must not contain duplicates."
        )

    return normalized


# =============================================================================
# Base Contract
# =============================================================================


class ArchitectureContractBase(BaseModel):
    """
    Base model shared by all architecture contracts.

    Contract identity is represented by ``id``.

    Contracts describe expected architecture behavior. They do not contain
    runtime/static evidence information.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    id: str = Field(
        description="Unique identifier of the architecture contract."
    )

    description: str | None = Field(
        default=None,
        description="Human-readable explanation of the contract.",
    )

    rationale: str | None = Field(
        default=None,
        description="Optional architectural rationale.",
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return _validate_identifier(value)


# =============================================================================
# Relation Contracts
# =============================================================================


class ForbiddenRelationContract(ArchitectureContractBase):
    """
    Declares that a canonical architecture relation must not exist.

    Example:

        checkout --CALLS--> recommendation

    can be explicitly forbidden.
    """

    type: Literal[
        ContractType.FORBIDDEN_RELATION
    ] = ContractType.FORBIDDEN_RELATION

    source: str
    relation: RelationType
    target: str

    @field_validator("source", "target")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        return _validate_identifier(value)


class RequiredRelationContract(ArchitectureContractBase):
    """
    Declares that a canonical architecture relation must exist.
    """

    type: Literal[
        ContractType.REQUIRED_RELATION
    ] = ContractType.REQUIRED_RELATION

    source: str
    relation: RelationType
    target: str

    @field_validator("source", "target")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        return _validate_identifier(value)


# =============================================================================
# Resource Ownership Contract
# =============================================================================


class ResourceOwnershipContract(ArchitectureContractBase):
    """
    Declares architectural ownership of a resource.

    The owner identifies the service permitted to access the resource using
    the configured relations.

    Example:

        owner: order-service
        resource: order-db
        relations:
            - READS_FROM
            - WRITES_TO

    A later conformance evaluator can detect access from non-owner services.
    """

    type: Literal[
        ContractType.RESOURCE_OWNERSHIP
    ] = ContractType.RESOURCE_OWNERSHIP

    owner: str

    resource: str

    relations: tuple[RelationType, ...] = (
        RelationType.READS_FROM,
        RelationType.WRITES_TO,
    )

    @field_validator("owner", "resource")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        return _validate_identifier(value)

    @field_validator("relations")
    @classmethod
    def validate_resource_relations(
        cls,
        value: tuple[RelationType, ...],
    ) -> tuple[RelationType, ...]:
        value = _validate_unique_relation_types(value)

        allowed = {
            RelationType.READS_FROM,
            RelationType.WRITES_TO,
        }

        invalid = [
            relation
            for relation in value
            if relation not in allowed
        ]

        if invalid:
            invalid_values = ", ".join(
                relation.value
                for relation in invalid
            )

            raise ValueError(
                "RESOURCE_OWNERSHIP only supports "
                "READS_FROM and WRITES_TO relations. "
                f"Invalid relations: {invalid_values}"
            )

        return value


# =============================================================================
# Exposure Contract
# =============================================================================


class ExposureContract(ArchitectureContractBase):
    """
    Restricts where an architectural element may be exposed.

    Example:

        subject: checkout
        allowed_targets:
            - frontend-proxy

    The evaluator will inspect EXPOSES_TO relations originating from
    ``subject``.

    ``require_exposure`` determines whether at least one allowed exposure
    must exist.
    """

    type: Literal[
        ContractType.EXPOSURE
    ] = ContractType.EXPOSURE

    subject: str

    allowed_targets: tuple[str, ...]

    require_exposure: bool = False

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, value: str) -> str:
        return _validate_identifier(value)

    @field_validator("allowed_targets")
    @classmethod
    def validate_allowed_targets(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _validate_unique_identifiers(value)


# =============================================================================
# Mediation Contract
# =============================================================================


class MediationContract(ArchitectureContractBase):
    """
    Requires communication between two nodes to pass through a mediator.

    Example:

        service-a
            |
            CALLS
            v
        api-gateway
            |
            ROUTES_TO
            v
        service-b

    If ``forbid_direct`` is true, the direct source-to-target relation is
    explicitly prohibited.
    """

    type: Literal[
        ContractType.MEDIATION
    ] = ContractType.MEDIATION

    source: str

    target: str

    mediator: str

    source_to_mediator_relation: RelationType

    mediator_to_target_relation: RelationType

    forbid_direct: bool = True

    @field_validator(
        "source",
        "target",
        "mediator",
    )
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        return _validate_identifier(value)

    @model_validator(mode="after")
    def validate_distinct_nodes(self) -> Self:
        nodes = {
            self.source,
            self.target,
            self.mediator,
        }

        if len(nodes) != 3:
            raise ValueError(
                "MEDIATION requires distinct source, target, "
                "and mediator nodes."
            )

        return self


# =============================================================================
# Communication Mode Contract
# =============================================================================


class CommunicationModeContract(ArchitectureContractBase):
    """
    Restricts the relation types permitted between two architectural nodes.

    This contract captures architectural communication style without binding
    the contract to a concrete protocol.

    Example:

        source: checkout
        target: payment

        allowed_relations:
            - CALLS

    Another example for asynchronous interaction may allow:

        PUBLISHES_TO
        SUBSCRIBES_TO
    """

    type: Literal[
        ContractType.COMMUNICATION_MODE
    ] = ContractType.COMMUNICATION_MODE

    source: str

    target: str

    allowed_relations: tuple[RelationType, ...]

    @field_validator("source", "target")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        return _validate_identifier(value)

    @field_validator("allowed_relations")
    @classmethod
    def validate_allowed_relations(
        cls,
        value: tuple[RelationType, ...],
    ) -> tuple[RelationType, ...]:
        return _validate_unique_relation_types(value)


# =============================================================================
# Discriminated Contract Union
# =============================================================================


ArchitectureContract = Annotated[
    ForbiddenRelationContract
    | RequiredRelationContract
    | ResourceOwnershipContract
    | ExposureContract
    | MediationContract
    | CommunicationModeContract,
    Field(discriminator="type"),
]


# =============================================================================
# Architecture Contract Document
# =============================================================================


class ArchitectureContractDocument(BaseModel):
    """
    Ground-truth architecture contract document for one case system.

    A single document contains the set of architectural expectations used
    during conformance evaluation.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    schema_version: Literal["1.0"] = "1.0"

    system_id: str

    contracts: list[ArchitectureContract] = Field(
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
    def validate_contract_ids(self) -> Self:
        contract_ids = [
            contract.id
            for contract in self.contracts
        ]

        if len(contract_ids) != len(set(contract_ids)):
            raise ValueError(
                "Architecture contract document contains "
                "duplicate contract identifiers."
            )

        return self

    def get_contract(
        self,
        contract_id: str,
    ) -> ArchitectureContract:
        """
        Retrieve a contract by identifier.

        Raises:
            KeyError:
                If the contract does not exist.
        """

        for contract in self.contracts:
            if contract.id == contract_id:
                return contract

        raise KeyError(
            f"Unknown architecture contract: {contract_id!r}"
        )


# =============================================================================
# YAML Loader
# =============================================================================


def load_contract_document(
    path: str | Path,
) -> ArchitectureContractDocument:
    """
    Load and validate an architecture contract YAML document.

    Args:
        path:
            Path to the architecture contract YAML file.

    Returns:
        Validated ArchitectureContractDocument.

    Raises:
        FileNotFoundError:
            If the YAML file does not exist.

        ValueError:
            If the YAML root structure is invalid.

        pydantic.ValidationError:
            If contract contents violate the schema.
    """

    contract_path = Path(path)

    if not contract_path.is_file():
        raise FileNotFoundError(
            f"Architecture contract file not found: {contract_path}"
        )

    with contract_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        raw_document = yaml.safe_load(file)

    if raw_document is None:
        raise ValueError(
            f"Architecture contract file is empty: {contract_path}"
        )

    if not isinstance(raw_document, dict):
        raise ValueError(
            "Architecture contract YAML root must be a mapping."
        )

    return ArchitectureContractDocument.model_validate(
        raw_document
    )