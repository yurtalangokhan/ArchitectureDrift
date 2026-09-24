from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, Self

import yaml
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
from archdrift.model.graph import (
    RelationIdentity,
    RelationType,
)

# =============================================================================
# Exceptions
# =============================================================================


class ArchitectureContractError(ValueError):
    """Base exception for architecture contract operations."""


class UnknownContractError(
    ArchitectureContractError,
    LookupError,
):
    """Raised when a contract identifier cannot be found."""


class ContractDocumentLoadError(ArchitectureContractError):
    """Raised when an architecture contract document cannot be loaded."""


# =============================================================================
# Contract Vocabulary
# =============================================================================


class ContractType(StrEnum):
    """
    Supported architecture contract types.

    These values are part of the experiment's stable ground-truth vocabulary.
    """

    FORBIDDEN_RELATION = "FORBIDDEN_RELATION"
    REQUIRED_RELATION = "REQUIRED_RELATION"
    RESOURCE_OWNERSHIP = "RESOURCE_OWNERSHIP"
    EXPOSURE = "EXPOSURE"
    MEDIATION = "MEDIATION"
    COMMUNICATION_MODE = "COMMUNICATION_MODE"


# =============================================================================
# Internal Validation Helpers
# =============================================================================


def _normalize_relation_types(
    relations: tuple[RelationType, ...],
) -> tuple[RelationType, ...]:
    """
    Validate and deterministically order relation types.
    """

    if not relations:
        raise ValueError(
            "At least one relation type must be specified."
        )

    if len(relations) != len(set(relations)):
        raise ValueError(
            "Relation types must not contain duplicates."
        )

    return tuple(
        sorted(
            relations,
            key=lambda relation: relation.value,
        )
    )


def _normalize_identifiers(
    identifiers: tuple[str, ...],
) -> tuple[str, ...]:
    """
    Validate and deterministically order identifier collections.
    """

    if not identifiers:
        raise ValueError(
            "At least one identifier must be specified."
        )

    normalized = tuple(
        normalize_identifier(
            identifier,
            field_name="identifier",
        )
        for identifier in identifiers
    )

    if len(normalized) != len(set(normalized)):
        raise ValueError(
            "Identifiers must not contain duplicates."
        )

    return tuple(sorted(normalized))


# =============================================================================
# Document Metadata
# =============================================================================


class ContractDocumentMetadata(BaseModel):
    """
    Optional immutable metadata associated with one contract document.

    Metadata does not participate in contract semantics or conformance
    evaluation.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    case_system: str | None = None

    purpose: str | None = None

    revision: str | None = None

    @field_validator(
        "case_system",
        "purpose",
        "revision",
    )
    @classmethod
    def normalize_text(
        cls,
        value: str | None,
    ) -> str | None:
        return normalize_optional_text(value)


# =============================================================================
# Base Contract
# =============================================================================


class ArchitectureContractBase(BaseModel):
    """
    Base model shared by all architecture contracts.

    Contracts represent ground-truth architectural expectations and contain
    no evidence-specific information.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    id: str = Field(
        description="Unique contract identifier."
    )

    description: str | None = Field(
        default=None,
        description="Human-readable architectural expectation.",
    )

    rationale: str | None = Field(
        default=None,
        description="Optional architectural rationale.",
    )

    @field_validator("id")
    @classmethod
    def validate_id(
        cls,
        value: str,
    ) -> str:
        return normalize_identifier(
            value,
            field_name="contract id",
        )

    @field_validator(
        "description",
        "rationale",
    )
    @classmethod
    def normalize_text(
        cls,
        value: str | None,
    ) -> str | None:
        return normalize_optional_text(value)


# =============================================================================
# Relation Contract Base
# =============================================================================


class _RelationContractBase(ArchitectureContractBase):
    """
    Internal base model for contracts addressing one canonical relation.
    """

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
    def relation_identity(self) -> RelationIdentity:
        """Return the canonical relation addressed by this contract."""

        return (
            self.source,
            self.relation,
            self.target,
        )


# =============================================================================
# Forbidden Relation
# =============================================================================


class ForbiddenRelationContract(_RelationContractBase):
    """
    Requires a canonical relation to be absent.
    """

    type: Literal[
        ContractType.FORBIDDEN_RELATION
    ] = ContractType.FORBIDDEN_RELATION


# =============================================================================
# Required Relation
# =============================================================================


class RequiredRelationContract(_RelationContractBase):
    """
    Requires a canonical relation to exist.
    """

    type: Literal[
        ContractType.REQUIRED_RELATION
    ] = ContractType.REQUIRED_RELATION


# =============================================================================
# Resource Ownership
# =============================================================================


class ResourceOwnershipContract(ArchitectureContractBase):
    """
    Declares exclusive architectural ownership of a resource.

    Nodes other than ``owner`` accessing ``resource`` through one of the
    configured relations constitute ownership violations.
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

    @field_validator(
        "owner",
        "resource",
    )
    @classmethod
    def validate_endpoint(
        cls,
        value: str,
    ) -> str:
        return normalize_identifier(
            value,
            field_name="resource ownership endpoint",
        )

    @field_validator("relations")
    @classmethod
    def validate_resource_relations(
        cls,
        value: tuple[RelationType, ...],
    ) -> tuple[RelationType, ...]:
        normalized = _normalize_relation_types(value)

        allowed = {
            RelationType.READS_FROM,
            RelationType.WRITES_TO,
        }

        invalid = tuple(
            relation
            for relation in normalized
            if relation not in allowed
        )

        if invalid:
            invalid_values = ", ".join(
                relation.value
                for relation in invalid
            )

            raise ValueError(
                "RESOURCE_OWNERSHIP supports only "
                "READS_FROM and WRITES_TO relations. "
                f"Invalid relations: {invalid_values}"
            )

        return normalized

    @model_validator(mode="after")
    def validate_distinct_owner_and_resource(
        self,
    ) -> Self:
        if self.owner == self.resource:
            raise ValueError(
                "RESOURCE_OWNERSHIP requires distinct "
                "owner and resource nodes."
            )

        return self


# =============================================================================
# Exposure
# =============================================================================


class ExposureContract(ArchitectureContractBase):
    """
    Restricts EXPOSES_TO relations originating from ``subject``.

    When ``require_exposure`` is true, at least one allowed exposure must
    exist.
    """

    type: Literal[
        ContractType.EXPOSURE
    ] = ContractType.EXPOSURE

    subject: str

    allowed_targets: tuple[str, ...]

    require_exposure: bool = False

    @field_validator("subject")
    @classmethod
    def validate_subject(
        cls,
        value: str,
    ) -> str:
        return normalize_identifier(
            value,
            field_name="exposure subject",
        )

    @field_validator("allowed_targets")
    @classmethod
    def validate_allowed_targets(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _normalize_identifiers(value)

    @model_validator(mode="after")
    def validate_subject_not_target(
        self,
    ) -> Self:
        if self.subject in self.allowed_targets:
            raise ValueError(
                "EXPOSURE subject must not also appear "
                "in allowed_targets."
            )

        return self


# =============================================================================
# Mediation
# =============================================================================


class MediationContract(ArchitectureContractBase):
    """
    Requires communication from source to target to traverse a mediator.

    ``direct_relation`` explicitly defines which source-to-target relation is
    forbidden when ``forbid_direct`` is true.
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

    direct_relation: RelationType | None = None

    @field_validator(
        "source",
        "target",
        "mediator",
    )
    @classmethod
    def validate_endpoint(
        cls,
        value: str,
    ) -> str:
        return normalize_identifier(
            value,
            field_name="mediation endpoint",
        )

    @model_validator(mode="after")
    def validate_mediation_semantics(
        self,
    ) -> Self:
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

        if (
            self.forbid_direct
            and self.direct_relation is None
        ):
            raise ValueError(
                "MEDIATION requires direct_relation when "
                "forbid_direct is true."
            )

        if (
            not self.forbid_direct
            and self.direct_relation is not None
        ):
            raise ValueError(
                "MEDIATION direct_relation must be omitted when "
                "forbid_direct is false."
            )

        return self


# =============================================================================
# Communication Mode
# =============================================================================


class CommunicationModeContract(ArchitectureContractBase):
    """
    Restricts canonical relation types permitted from source to target.

    Concrete transport protocols are deliberately excluded.
    """

    type: Literal[
        ContractType.COMMUNICATION_MODE
    ] = ContractType.COMMUNICATION_MODE

    source: str

    target: str

    allowed_relations: tuple[RelationType, ...]

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
            field_name="communication endpoint",
        )

    @field_validator("allowed_relations")
    @classmethod
    def validate_allowed_relations(
        cls,
        value: tuple[RelationType, ...],
    ) -> tuple[RelationType, ...]:
        return _normalize_relation_types(value)

    @model_validator(mode="after")
    def validate_distinct_endpoints(
        self,
    ) -> Self:
        if self.source == self.target:
            raise ValueError(
                "COMMUNICATION_MODE requires distinct "
                "source and target nodes."
            )

        return self


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
# Contract Document
# =============================================================================


class ArchitectureContractDocument(BaseModel):
    """
    Immutable ground-truth contract document for one case system.

    Contract ordering is normalized by contract identifier for deterministic
    serialization and experiment execution.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    schema_version: Literal["1.0"] = "1.0"

    system_id: str

    contracts: tuple[
        ArchitectureContract,
        ...,
    ] = ()

    metadata: ContractDocumentMetadata = Field(
        default_factory=ContractDocumentMetadata,
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

    @field_validator("contracts")
    @classmethod
    def validate_contracts(
        cls,
        value: tuple[
            ArchitectureContract,
            ...,
        ],
    ) -> tuple[
        ArchitectureContract,
        ...,
    ]:
        contract_ids = tuple(
            contract.id
            for contract in value
        )

        if len(contract_ids) != len(set(contract_ids)):
            raise ValueError(
                "Architecture contract document contains "
                "duplicate contract identifiers."
            )

        return tuple(
            sorted(
                value,
                key=lambda contract: contract.id,
            )
        )

    @property
    def contract_ids(self) -> frozenset[str]:
        """
        Return all ground-truth contract identifiers.
        """

        return frozenset(
            contract.id
            for contract in self.contracts
        )

    def get_contract(
        self,
        contract_id: str,
    ) -> ArchitectureContract:
        """
        Return a contract by identifier.
        """

        normalized_id = normalize_identifier(
            contract_id,
            field_name="contract id",
        )

        for contract in self.contracts:
            if contract.id == normalized_id:
                return contract

        raise UnknownContractError(
            f"Unknown architecture contract: {normalized_id!r}"
        )

    def contracts_of_type(
        self,
        contract_type: ContractType,
    ) -> tuple[
        ArchitectureContract,
        ...,
    ]:
        """
        Return contracts matching one contract type.
        """

        return tuple(
            contract
            for contract in self.contracts
            if contract.type is contract_type
        )


# =============================================================================
# YAML Loader
# =============================================================================


def load_contract_document(
    path: str | Path,
) -> ArchitectureContractDocument:
    """
    Load and validate one architecture contract YAML document.

    YAML syntax and root-structure failures are translated into a stable
    domain-level exception.

    Pydantic ValidationError intentionally propagates so callers retain
    detailed schema diagnostics.
    """

    contract_path = Path(path)

    if not contract_path.is_file():
        raise FileNotFoundError(
            f"Architecture contract file not found: {contract_path}"
        )

    try:
        with contract_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            raw_document = yaml.safe_load(file)

    except yaml.YAMLError as exc:
        raise ContractDocumentLoadError(
            "Invalid YAML in architecture contract file: "
            f"{contract_path}"
        ) from exc

    if raw_document is None:
        raise ContractDocumentLoadError(
            f"Architecture contract file is empty: {contract_path}"
        )

    if not isinstance(raw_document, dict):
        raise ContractDocumentLoadError(
            "Architecture contract YAML root must be a mapping."
        )

    return ArchitectureContractDocument.model_validate(
        raw_document
    )