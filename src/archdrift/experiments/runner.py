from __future__ import annotations

from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)

from archdrift.adapters.aspire import AspireAdapter
from archdrift.adapters.base import (
    repository_artifact_id,
    resolve_repository_path,
)
from archdrift.adapters.compose import ComposeAdapter
from archdrift.adapters.otel import OtelAdapter
from archdrift.analysis.conformance import (
    ConformanceReport,
    evaluate_contract_document,
)
from archdrift.analysis.fusion import (
    EvidenceGraphViews,
    build_evidence_graph_views,
)
from archdrift.analysis.graph_delta import (
    GraphDelta,
    compute_baseline_mutant_delta,
    matches_expected_delta,
)
from archdrift.analysis.metrics import (
    ExperimentMetrics,
    compute_experiment_metrics,
)
from archdrift.analysis.normalize import (
    CanonicalCandidate,
    canonicalize_observation,
)
from archdrift.experiments.activation import (
    MutationActivationError,
    apply_mutation,
)
from archdrift.model._validation import (
    normalize_identifier,
)
from archdrift.model.contract import (
    ArchitectureContractDocument,
    load_contract_document,
)
from archdrift.model.graph import (
    ArchitectureGraph,
    GraphRole,
    NodeType,
)
from archdrift.model.mutation import (
    MutationOracle,
    load_mutation_oracle,
)

# =============================================================================
# Exceptions
# =============================================================================


class ExperimentError(ValueError):
    """Base exception for experiment execution."""


class ExperimentConfigurationError(ExperimentError):
    """Raised when an experiment case definition is invalid."""


class ExperimentConsistencyError(ExperimentError):
    """
    Raised when experiment ground-truth artifacts contradict each other.
    """


# =============================================================================
# Case Definition
# =============================================================================


class CaseComponent(BaseModel):
    """Canonical component declaration used for adapter normalization."""

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
            field_name="component id",
        )


class CaseAlias(BaseModel):
    """Map an observed technology-specific name to canonical identity."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    observed: str
    canonical: str

    @field_validator(
        "observed",
        "canonical",
    )
    @classmethod
    def validate_identifier(
        cls,
        value: str,
    ) -> str:
        return normalize_identifier(
            value,
            field_name="alias identifier",
        )


class NonRuntimeEvidenceConfig(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    compose_files: tuple[str, ...] = ()

    aspire_files: tuple[str, ...] = ()


class RuntimeEvidenceConfig(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    otlp_files: tuple[str, ...] = ()


class CaseDefinition(BaseModel):
    """
    Immutable executable experiment case definition.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    schema_version: Literal["1.0"] = "1.0"

    case_id: str

    system_id: str

    variant: str

    baseline_graph: str

    contract_document: str

    mutation_oracle: str

    components: tuple[
        CaseComponent,
        ...,
    ]

    aliases: tuple[
        CaseAlias,
        ...,
    ] = ()

    non_runtime: NonRuntimeEvidenceConfig

    runtime: RuntimeEvidenceConfig

    @field_validator(
        "case_id",
        "system_id",
        "variant",
    )
    @classmethod
    def validate_identifier(
        cls,
        value: str,
    ) -> str:
        return normalize_identifier(
            value,
            field_name="case identifier",
        )

    @field_validator(
        "baseline_graph",
        "contract_document",
        "mutation_oracle",
    )
    @classmethod
    def validate_relative_path(
        cls,
        value: str,
    ) -> str:
        return _validate_relative_path(value)

    @field_validator(
        "components",
    )
    @classmethod
    def validate_components(
        cls,
        value: tuple[
            CaseComponent,
            ...,
        ],
    ) -> tuple[
        CaseComponent,
        ...,
    ]:
        if not value:
            raise ValueError("Experiment case requires at least one component.")

        ids = tuple(component.id for component in value)

        if len(ids) != len(set(ids)):
            raise ValueError("Experiment components must have unique identifiers.")

        return tuple(
            sorted(
                value,
                key=lambda component: component.id,
            )
        )

    @field_validator("aliases")
    @classmethod
    def validate_aliases(
        cls,
        value: tuple[
            CaseAlias,
            ...,
        ],
    ) -> tuple[
        CaseAlias,
        ...,
    ]:
        observed = tuple(alias.observed for alias in value)

        if len(observed) != len(set(observed)):
            raise ValueError("Observed aliases must be unique.")

        return tuple(
            sorted(
                value,
                key=lambda alias: alias.observed,
            )
        )

    @model_validator(mode="after")
    def validate_alias_targets(
        self,
    ) -> Self:
        component_ids = {component.id for component in self.components}

        invalid = tuple(
            alias.canonical
            for alias in self.aliases
            if alias.canonical not in component_ids
        )

        if invalid:
            raise ValueError(
                "Alias targets must reference declared components: "
                + ", ".join(sorted(invalid))
            )

        return self

    @property
    def node_types(
        self,
    ) -> dict[str, NodeType]:
        return {component.id: component.type for component in self.components}

    @property
    def alias_map(
        self,
    ) -> dict[str, str]:
        return {alias.observed: alias.canonical for alias in self.aliases}


# =============================================================================
# Experiment Result
# =============================================================================


class ExperimentResult(BaseModel):
    """
    Complete result of one executable controlled-mutation experiment.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    case_id: str

    mutation_id: str

    baseline: ArchitectureGraph

    mutant: ArchitectureGraph

    mutation_delta: GraphDelta

    expected_violated_contracts: tuple[
        str,
        ...,
    ]

    views: EvidenceGraphViews

    baseline_conformance: ConformanceReport

    mutant_conformance: ConformanceReport

    non_runtime_conformance: ConformanceReport

    runtime_conformance: ConformanceReport

    fused_conformance: ConformanceReport
    metrics: ExperimentMetrics

    @property
    def non_runtime_detected_expected_violation(
        self,
    ) -> bool:
        return bool(
            self.non_runtime_conformance.violated_contract_ids
            & set(self.expected_violated_contracts)
        )

    @property
    def runtime_detected_expected_violation(
        self,
    ) -> bool:
        return bool(
            self.runtime_conformance.violated_contract_ids
            & set(self.expected_violated_contracts)
        )

    @property
    def fused_detected_expected_violation(
        self,
    ) -> bool:
        return bool(
            self.fused_conformance.violated_contract_ids
            & set(self.expected_violated_contracts)
        )


# =============================================================================
# Loading
# =============================================================================


def _validate_relative_path(
    value: str,
) -> str:
    path = Path(value)

    if path.is_absolute():
        raise ValueError("Experiment paths must be repository-relative.")

    if ".." in path.parts:
        raise ValueError("Experiment paths must not contain '..'.")

    normalized = path.as_posix()

    if not normalized:
        raise ValueError("Experiment path must not be empty.")

    return normalized


def load_case_definition(
    path: str | Path,
) -> CaseDefinition:
    case_path = Path(path)

    if not case_path.is_file():
        raise FileNotFoundError(f"Experiment case file not found: {case_path}")

    try:
        with case_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            document = yaml.safe_load(file)

    except yaml.YAMLError as exc:
        raise ExperimentConfigurationError(f"Invalid case YAML: {case_path}") from exc

    if not isinstance(
        document,
        dict,
    ):
        raise ExperimentConfigurationError(
            "Experiment case YAML root must be a mapping."
        )

    return CaseDefinition.model_validate(document)


def _load_architecture_graph(
    path: Path,
) -> ArchitectureGraph:
    if not path.is_file():
        raise FileNotFoundError(f"Architecture graph file not found: {path}")

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            document = yaml.safe_load(file)

    except yaml.YAMLError as exc:
        raise ExperimentConfigurationError(
            f"Invalid architecture graph YAML: {path}"
        ) from exc

    if not isinstance(
        document,
        dict,
    ):
        raise ExperimentConfigurationError(
            "Architecture graph YAML root must be a mapping."
        )

    return ArchitectureGraph.model_validate(document)


# =============================================================================
# Evidence Collection
# =============================================================================


def _collect_non_runtime_candidates(
    *,
    root: Path,
    case: CaseDefinition,
) -> tuple[CanonicalCandidate, ...]:
    candidates: list[
        CanonicalCandidate
    ] = []

    # -------------------------------------------------------------------------
    # Docker Compose
    # -------------------------------------------------------------------------

    for compose_file in case.non_runtime.compose_files:
        observations = ComposeAdapter(
            root,
            compose_file,
            node_types=case.node_types,
        ).collect()

        candidates.extend(
            canonicalize_observation(
                observation
            )
            for observation in observations
        )

    # -------------------------------------------------------------------------
    # .NET Aspire AppHost
    # -------------------------------------------------------------------------

    for aspire_file in case.non_runtime.aspire_files:
        observations = AspireAdapter(
            root,
            aspire_file,
        ).collect()

        candidates.extend(
            canonicalize_observation(
                observation
            )
            for observation in observations
        )

    return tuple(
        candidates
    )


def _collect_runtime_candidates(
    *,
    root: Path,
    case: CaseDefinition,
) -> tuple[CanonicalCandidate, ...]:
    candidates: list[CanonicalCandidate] = []

    for otlp_file in case.runtime.otlp_files:
        trace_path = resolve_repository_path(
            root,
            otlp_file,
        )

        observations = OtelAdapter(
            trace_path,
            artifact_id=repository_artifact_id(
                root,
                trace_path,
            ),
            aliases=case.alias_map,
            node_types=case.node_types,
        ).collect()

        candidates.extend(
            canonicalize_observation(observation) for observation in observations
        )

    return tuple(candidates)


# =============================================================================
# Ground-Truth Validation
# =============================================================================


def _validate_ground_truth(
    *,
    case: CaseDefinition,
    baseline: ArchitectureGraph,
    contracts: ArchitectureContractDocument,
    oracle: MutationOracle,
) -> None:
    system_ids = {
        case.system_id,
        baseline.metadata.system_id,
        contracts.system_id,
        oracle.system_id,
    }

    if len(system_ids) != 1:
        raise ExperimentConsistencyError(
            "Case, baseline, contract document, and mutation oracle "
            "must use the same system_id."
        )

    if baseline.metadata.role is not GraphRole.BASELINE:
        raise ExperimentConsistencyError(
            "Configured baseline graph must have role BASELINE."
        )

    if case.variant != oracle.mutation_id:
        raise ExperimentConsistencyError(
            "Case variant does not match mutation oracle: "
            f"{case.variant!r} != {oracle.mutation_id!r}"
        )


# =============================================================================
# Runner
# =============================================================================


def run_case(
    *,
    project_root: str | Path,
    case_file: str | Path,
) -> ExperimentResult:
    """
    Execute one complete controlled architecture-conformance experiment.
    """

    root = Path(project_root).resolve()

    if not root.is_dir():
        raise ExperimentConfigurationError(f"Project root does not exist: {root}")

    case_path = resolve_repository_path(
        root,
        case_file,
    )

    case = load_case_definition(case_path)

    baseline = _load_architecture_graph(
        resolve_repository_path(
            root,
            case.baseline_graph,
        )
    )

    contracts = load_contract_document(
        resolve_repository_path(
            root,
            case.contract_document,
        )
    )

    oracle = load_mutation_oracle(
        resolve_repository_path(
            root,
            case.mutation_oracle,
        )
    )

    _validate_ground_truth(
        case=case,
        baseline=baseline,
        contracts=contracts,
        oracle=oracle,
    )

    # -------------------------------------------------------------------------
    # Controlled mutation
    # -------------------------------------------------------------------------

    try:
        mutant = apply_mutation(
            baseline,
            oracle,
        )

    except MutationActivationError as exc:
        raise ExperimentConsistencyError(f"Mutation activation failed: {exc}") from exc

    mutation_delta = compute_baseline_mutant_delta(
        baseline,
        mutant,
    )

    if not matches_expected_delta(
        mutation_delta,
        oracle.expected_delta,
    ):
        raise ExperimentConsistencyError(
            "Computed Baseline -> Mutant graph delta does not match "
            "the mutation oracle."
        )

    # -------------------------------------------------------------------------
    # Validate mutation -> contract ground truth
    # -------------------------------------------------------------------------

    baseline_conformance = evaluate_contract_document(
        baseline,
        contracts,
    )

    mutant_conformance = evaluate_contract_document(
        mutant,
        contracts,
    )

    expected_violations = frozenset(oracle.expected_violated_contracts)

    if mutant_conformance.violated_contract_ids != expected_violations:
        raise ExperimentConsistencyError(
            "Mutation oracle expected contract violations do not match "
            "conformance evaluation of the mutant graph."
        )

    # -------------------------------------------------------------------------
    # Evidence acquisition + normalization
    # -------------------------------------------------------------------------

    non_runtime_candidates = _collect_non_runtime_candidates(
        root=root,
        case=case,
    )

    runtime_candidates = _collect_runtime_candidates(
        root=root,
        case=case,
    )

    all_candidates = (
        *non_runtime_candidates,
        *runtime_candidates,
    )

    # -------------------------------------------------------------------------
    # Reconstruction / Fusion
    # -------------------------------------------------------------------------

    views = build_evidence_graph_views(
        system_id=case.system_id,
        candidates=all_candidates,
        variant=case.variant,
        revision=baseline.metadata.revision,
    )

    # -------------------------------------------------------------------------
    # Conformance detection
    # -------------------------------------------------------------------------

    non_runtime_conformance = evaluate_contract_document(
        views.non_runtime.graph,
        contracts,
    )

    runtime_conformance = evaluate_contract_document(
        views.runtime.graph,
        contracts,
    )

    fused_conformance = evaluate_contract_document(
        views.fused.graph,
        contracts,
    )

    metrics = compute_experiment_metrics(
        baseline=baseline,
        views=views,
        non_runtime_report=non_runtime_conformance,
        runtime_report=runtime_conformance,
        fused_report=fused_conformance,
        oracle=oracle,
    )

    return ExperimentResult(
        case_id=case.case_id,
        mutation_id=oracle.mutation_id,
        baseline=baseline,
        mutant=mutant,
        mutation_delta=mutation_delta,
        expected_violated_contracts=tuple(sorted(expected_violations)),
        views=views,
        baseline_conformance=baseline_conformance,
        mutant_conformance=mutant_conformance,
        non_runtime_conformance=non_runtime_conformance,
        runtime_conformance=runtime_conformance,
        fused_conformance=fused_conformance,
        metrics=metrics,
    )
