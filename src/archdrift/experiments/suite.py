from __future__ import annotations

import hashlib
import subprocess
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
)

from archdrift.adapters.base import (
    resolve_repository_path,
)
from archdrift.analysis.conformance import (
    ConformanceReport,
)
from archdrift.analysis.metrics import (
    ContractViolationMetrics,
    EvidenceViewMetrics,
    SetDetectionMetrics,
)
from archdrift.experiments.runner import (
    CaseDefinition,
    ExperimentResult,
    load_case_definition,
    run_case,
)
from archdrift.model.graph import (
    ReconstructionMode,
)


class SuiteError(ValueError):
    """Base exception for experiment-suite execution."""


class SuiteConfigurationError(SuiteError):
    """Raised when an experiment-suite definition is invalid."""


class SuiteMetadata(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    purpose: str | None = None
    revision: str | None = None


def _validate_relative_path(
    value: str,
) -> str:
    normalized = value.strip()

    if not normalized:
        raise ValueError(
            "Suite case path must not be empty."
        )

    path = Path(
        normalized
    )

    if path.is_absolute():
        raise ValueError(
            "Suite case paths must be repository-relative."
        )

    if ".." in path.parts:
        raise ValueError(
            "Suite case paths must not contain '..'."
        )

    return path.as_posix()


class ExperimentSuiteDefinition(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    schema_version: Literal["1.0"] = "1.0"

    suite_id: str

    metadata: SuiteMetadata = SuiteMetadata()

    cases: tuple[
        str,
        ...,
    ]

    @field_validator("suite_id")
    @classmethod
    def validate_suite_id(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "suite_id must not be empty."
            )

        return normalized

    @field_validator("cases")
    @classmethod
    def validate_cases(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if not value:
            raise ValueError(
                "Experiment suite requires at least one case."
            )

        normalized = tuple(
            _validate_relative_path(
                case
            )
            for case in value
        )

        if len(normalized) != len(
            set(normalized)
        ):
            raise ValueError(
                "Experiment suite contains duplicate case paths."
            )

        return normalized


class InputArtifactDigest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    path: str
    sha256: str
    size_bytes: int


class CaseInputManifest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    case_file: str

    fingerprint: str

    artifacts: tuple[
        InputArtifactDigest,
        ...,
    ]


class SuiteCaseResult(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    case_file: str

    system_id: str

    mutation_id: str

    input_manifest: CaseInputManifest

    result: ExperimentResult


class EvidenceModeAggregate(BaseModel):
    """
    Micro-aggregated metrics across a group of mutation cases.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    case_count: int

    fully_detected_case_count: int

    structural: SetDetectionMetrics

    contract_violations: ContractViolationMetrics

    @property
    def full_detection_rate(
        self,
    ) -> float | None:
        if self.case_count == 0:
            return None

        return (
            self.fully_detected_case_count
            / self.case_count
        )


class ScopeAggregate(BaseModel):
    """
    Aggregated metrics for one system or the overall experiment suite.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    scope_id: str

    case_count: int

    non_runtime: EvidenceModeAggregate

    runtime: EvidenceModeAggregate

    fused: EvidenceModeAggregate


class ExperimentSuiteResult(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    suite_id: str

    suite_file: str

    git_commit: str | None

    implementation_fingerprint: str

    suite_fingerprint: str

    cases: tuple[
        SuiteCaseResult,
        ...,
    ]

    systems: tuple[
        ScopeAggregate,
        ...,
    ]

    overall: ScopeAggregate


def load_suite_definition(
    path: str | Path,
) -> ExperimentSuiteDefinition:
    suite_path = Path(
        path
    )

    if not suite_path.is_file():
        raise FileNotFoundError(
            f"Experiment suite file not found: {suite_path}"
        )

    try:
        with suite_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            document = yaml.safe_load(
                file
            )

    except yaml.YAMLError as exc:
        raise SuiteConfigurationError(
            f"Invalid suite YAML: {suite_path}"
        ) from exc

    if not isinstance(
        document,
        dict,
    ):
        raise SuiteConfigurationError(
            "Experiment suite YAML root must be a mapping."
        )

    return ExperimentSuiteDefinition.model_validate(
        document
    )


def _sha256_bytes(
    content: bytes,
) -> str:
    return hashlib.sha256(
        content
    ).hexdigest()


def _digest_file(
    *,
    root: Path,
    path: Path,
) -> InputArtifactDigest:
    resolved = path.resolve()

    try:
        relative = resolved.relative_to(
            root
        )
    except ValueError as exc:
        raise SuiteConfigurationError(
            f"Input artifact escapes project root: {path}"
        ) from exc

    if not resolved.is_file():
        raise FileNotFoundError(
            f"Experiment input artifact not found: {resolved}"
        )

    content = resolved.read_bytes()

    return InputArtifactDigest(
        path=relative.as_posix(),
        sha256=_sha256_bytes(
            content
        ),
        size_bytes=len(
            content
        ),
    )


def _fingerprint_artifacts(
    artifacts: Iterable[
        InputArtifactDigest
    ],
) -> str:
    lines = tuple(
        (
            f"{artifact.path}\0"
            f"{artifact.sha256}\0"
            f"{artifact.size_bytes}"
        )
        for artifact in sorted(
            artifacts,
            key=lambda item: item.path,
        )
    )

    payload = "\n".join(
        lines
    ).encode(
        "utf-8"
    )

    return _sha256_bytes(
        payload
    )


def _case_input_paths(
    *,
    root: Path,
    case_file: str,
    case: CaseDefinition,
) -> tuple[Path, ...]:
    relative_paths = {
        case_file,
        case.baseline_graph,
        case.contract_document,
        case.mutation_oracle,
        *case.non_runtime.compose_files,
        *case.non_runtime.aspire_files,
        *case.runtime.otlp_files,
    }

    return tuple(
        resolve_repository_path(
            root,
            relative_path,
        )
        for relative_path in sorted(
            relative_paths
        )
    )


def build_case_input_manifest(
    *,
    root: Path,
    case_file: str,
) -> CaseInputManifest:
    case_path = resolve_repository_path(
        root,
        case_file,
    )

    case = load_case_definition(
        case_path
    )

    artifacts = tuple(
        _digest_file(
            root=root,
            path=path,
        )
        for path in _case_input_paths(
            root=root,
            case_file=case_file,
            case=case,
        )
    )

    return CaseInputManifest(
        case_file=case_file,
        artifacts=artifacts,
        fingerprint=_fingerprint_artifacts(
            artifacts
        ),
    )


def _implementation_fingerprint(
    root: Path,
) -> str:
    files = tuple(
        sorted(
            (
                path
                for path in (
                    root
                    / "src"
                    / "archdrift"
                ).rglob("*.py")
                if path.is_file()
            ),
            key=lambda path: path.as_posix(),
        )
    )

    optional_files = (
        root / "pyproject.toml",
    )

    all_files = (
        *files,
        *(
            path
            for path in optional_files
            if path.is_file()
        ),
    )

    artifacts = tuple(
        _digest_file(
            root=root,
            path=path,
        )
        for path in all_files
    )

    return _fingerprint_artifacts(
        artifacts
    )


def _git_commit(
    root: Path,
) -> str | None:
    try:
        process = subprocess.run(
            [
                "git",
                "rev-parse",
                "HEAD",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )

    except OSError:
        return None

    if process.returncode != 0:
        return None

    commit = process.stdout.strip()

    return (
        commit
        if commit
        else None
    )


def _view_for_mode(
    result: ExperimentResult,
    mode: ReconstructionMode,
) -> tuple[
    EvidenceViewMetrics,
    ConformanceReport,
]:
    if (
        mode
        is ReconstructionMode.NON_RUNTIME
    ):
        return (
            result.metrics.non_runtime,
            result.non_runtime_conformance,
        )

    if (
        mode
        is ReconstructionMode.RUNTIME
    ):
        return (
            result.metrics.runtime,
            result.runtime_conformance,
        )

    if (
        mode
        is ReconstructionMode.FUSED
    ):
        return (
            result.metrics.fused,
            result.fused_conformance,
        )

    raise SuiteError(
        f"Unsupported reconstruction mode: {mode!r}"
    )


def _aggregate_mode(
    cases: tuple[
        SuiteCaseResult,
        ...,
    ],
    mode: ReconstructionMode,
) -> EvidenceModeAggregate:
    structural_tp = 0
    structural_fp = 0
    structural_fn = 0

    contract_tp = 0
    contract_fp = 0
    contract_fn = 0
    contract_tn = 0

    not_evaluable_positive = 0
    not_evaluable_negative = 0

    fully_detected = 0

    for case in cases:
        metrics, _ = _view_for_mode(
            case.result,
            mode,
        )

        structural = (
            metrics.structural.overall
        )

        structural_tp += (
            structural.true_positive
        )

        structural_fp += (
            structural.false_positive
        )

        structural_fn += (
            structural.false_negative
        )

        contract = (
            metrics.contract_violations
        )

        contract_tp += (
            contract.true_positive
        )

        contract_fp += (
            contract.false_positive
        )

        contract_fn += (
            contract.false_negative
        )

        contract_tn += (
            contract.true_negative
        )

        not_evaluable_positive += (
            contract.not_evaluable_positive
        )

        not_evaluable_negative += (
            contract.not_evaluable_negative
        )

        expected_positive_count = (
            contract.true_positive
            + contract.false_negative
        )

        if (
            expected_positive_count > 0
            and contract.false_negative == 0
        ):
            fully_detected += 1

    return EvidenceModeAggregate(
        case_count=len(
            cases
        ),
        fully_detected_case_count=(
            fully_detected
        ),
        structural=SetDetectionMetrics(
            true_positive=structural_tp,
            false_positive=structural_fp,
            false_negative=structural_fn,
        ),
        contract_violations=(
            ContractViolationMetrics(
                true_positive=contract_tp,
                false_positive=contract_fp,
                false_negative=contract_fn,
                true_negative=contract_tn,
                not_evaluable_positive=(
                    not_evaluable_positive
                ),
                not_evaluable_negative=(
                    not_evaluable_negative
                ),
            )
        ),
    )


def _aggregate_scope(
    *,
    scope_id: str,
    cases: tuple[
        SuiteCaseResult,
        ...,
    ],
) -> ScopeAggregate:
    return ScopeAggregate(
        scope_id=scope_id,
        case_count=len(
            cases
        ),
        non_runtime=_aggregate_mode(
            cases,
            ReconstructionMode.NON_RUNTIME,
        ),
        runtime=_aggregate_mode(
            cases,
            ReconstructionMode.RUNTIME,
        ),
        fused=_aggregate_mode(
            cases,
            ReconstructionMode.FUSED,
        ),
    )


def _suite_fingerprint(
    *,
    suite_artifact: InputArtifactDigest,
    case_results: tuple[
        SuiteCaseResult,
        ...,
    ],
    implementation_fingerprint: str,
) -> str:
    payload = "\n".join(
        (
            f"suite={suite_artifact.sha256}",
            (
                "implementation="
                f"{implementation_fingerprint}"
            ),
            *(
                (
                    f"{case.case_file}="
                    f"{case.input_manifest.fingerprint}"
                )
                for case in case_results
            ),
        )
    )

    return _sha256_bytes(
        payload.encode(
            "utf-8"
        )
    )


def run_suite(
    *,
    project_root: str | Path,
    suite_file: str | Path,
) -> ExperimentSuiteResult:
    root = Path(
        project_root
    ).resolve()

    if not root.is_dir():
        raise SuiteConfigurationError(
            f"Project root does not exist: {root}"
        )

    suite_path = resolve_repository_path(
        root,
        suite_file,
    )

    suite_definition = (
        load_suite_definition(
            suite_path
        )
    )

    case_results: list[
        SuiteCaseResult
    ] = []

    for case_file in (
        suite_definition.cases
    ):
        manifest = (
            build_case_input_manifest(
                root=root,
                case_file=case_file,
            )
        )

        experiment = run_case(
            project_root=root,
            case_file=case_file,
        )

        case_results.append(
            SuiteCaseResult(
                case_file=case_file,
                system_id=(
                    experiment
                    .baseline
                    .metadata
                    .system_id
                ),
                mutation_id=(
                    experiment.mutation_id
                ),
                input_manifest=manifest,
                result=experiment,
            )
        )

    frozen_cases = tuple(
        case_results
    )

    grouped: dict[
        str,
        list[SuiteCaseResult],
    ] = defaultdict(
        list
    )

    for case in frozen_cases:
        grouped[
            case.system_id
        ].append(
            case
        )

    systems = tuple(
        _aggregate_scope(
            scope_id=system_id,
            cases=tuple(
                grouped[
                    system_id
                ]
            ),
        )
        for system_id in sorted(
            grouped
        )
    )

    implementation_fingerprint = (
        _implementation_fingerprint(
            root
        )
    )

    suite_artifact = _digest_file(
        root=root,
        path=suite_path,
    )

    return ExperimentSuiteResult(
        suite_id=(
            suite_definition.suite_id
        ),
        suite_file=(
            suite_path
            .relative_to(root)
            .as_posix()
        ),
        git_commit=_git_commit(
            root
        ),
        implementation_fingerprint=(
            implementation_fingerprint
        ),
        suite_fingerprint=(
            _suite_fingerprint(
                suite_artifact=(
                    suite_artifact
                ),
                case_results=frozen_cases,
                implementation_fingerprint=(
                    implementation_fingerprint
                ),
            )
        ),
        cases=frozen_cases,
        systems=systems,
        overall=_aggregate_scope(
            scope_id="overall",
            cases=frozen_cases,
        ),
    )