from __future__ import annotations

from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
)

from archdrift.adapters.aspire import (
    AspireAdapter,
)
from archdrift.adapters.compose import (
    ComposeAdapter,
)
from archdrift.adapters.compose_bindings import (
    ComposeEndpointBindingAdapter,
)
from archdrift.adapters.compose_render import (
    DockerComposeRenderer,
)
from archdrift.analysis.non_runtime import (
    NonRuntimeEvidenceViews,
    reconstruct_non_runtime_views,
)
from archdrift.analysis.scope import (
    EvidenceScope,
)
from archdrift.analysis.static_observation import (
    static_interactions_to_observations,
)
from archdrift.analysis.static_resolution import (
    StaticTargetResolver,
)
from archdrift.experiments.static_runner import (
    StaticEvidenceRunner,
)
from archdrift.model.observation import (
    NormalizedObservation,
)
from archdrift.model.source_static import (
    EndpointBinding,
    SourcePathRule,
    SourceStaticFinding,
    StaticResolutionSet,
)
from archdrift.model.static_profile import (
    NonRuntimeEvidenceProfile,
)


class NonRuntimeEvidenceRun(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        arbitrary_types_allowed=True,
    )

    subject_id: str

    deployment_observations: tuple[
        NormalizedObservation,
        ...,
    ]

    source_static_findings: tuple[
        SourceStaticFinding,
        ...,
    ]

    static_resolution: StaticResolutionSet

    source_static_observations: tuple[
        NormalizedObservation,
        ...,
    ]

    views: NonRuntimeEvidenceViews

    resolved_compose_file: str | None = None


class NonRuntimeEvidenceRunner:
    def __init__(
        self,
        *,
        static_runner: StaticEvidenceRunner | None = None,
    ) -> None:
        self._static_runner = static_runner or StaticEvidenceRunner()

    def run(
        self,
        *,
        project_root: Path,
        profile: NonRuntimeEvidenceProfile,
        rule_pack_root: Path,
    ) -> NonRuntimeEvidenceRun:
        root = project_root.resolve()

        subject_root = (root / profile.subject_root).resolve()

        if not subject_root.is_dir():
            raise FileNotFoundError("Subject root does not exist: " f"{subject_root}")

        (
            deployment_observations,
            resolved_compose,
        ) = self._collect_deployment(
            project_root=root,
            subject_root=subject_root,
            profile=profile,
        )

        static_scan = self._static_runner.run(
            profile=profile,
            subject_root=(subject_root),
            rule_pack_root=(rule_pack_root),
            output_root=(
                root
                / "evidence"
                / "real"
                / "non-runtime"
                / profile.subject_id
                / "source-static"
                / "raw"
            ),
        )

        bindings: tuple[
            EndpointBinding,
            ...,
        ] = ()

        if resolved_compose is not None:
            bindings = ComposeEndpointBindingAdapter().collect(
                result_file=(resolved_compose),
                node_types=(profile.node_types),
            )

        source_rules = tuple(
            SourcePathRule(
                path_prefix=(source.path),
                service_id=(source.service_id),
                service_type=(profile.node_types[source.service_id]),
            )
            for source in (profile.source_roots)
        )

        resolution = StaticTargetResolver().resolve(
            findings=(static_scan.findings),
            source_rules=(source_rules),
            bindings=bindings,
            node_types=(profile.node_types),
        )

        static_observations = static_interactions_to_observations(resolution.resolved)

        scope = EvidenceScope(node_ids=frozenset(profile.node_types))

        views = reconstruct_non_runtime_views(
            system_id=(profile.subject_id),
            deployment_observations=(deployment_observations),
            source_static_observations=(static_observations),
            scope=scope,
        )

        return NonRuntimeEvidenceRun(
            subject_id=(profile.subject_id),
            deployment_observations=(deployment_observations),
            source_static_findings=(static_scan.findings),
            static_resolution=(resolution),
            source_static_observations=(static_observations),
            views=views,
            resolved_compose_file=(
                str(resolved_compose) if resolved_compose is not None else None
            ),
        )

    def _collect_deployment(
        self,
        *,
        project_root: Path,
        subject_root: Path,
        profile: NonRuntimeEvidenceProfile,
    ) -> tuple[
        tuple[
            NormalizedObservation,
            ...,
        ],
        Path | None,
    ]:
        if profile.compose is not None:
            return self._collect_compose(
                project_root=(project_root),
                subject_root=(subject_root),
                profile=profile,
            )

        if profile.aspire is not None:
            return (
                self._collect_aspire(
                    subject_root=(subject_root),
                    profile=profile,
                ),
                None,
            )

        raise ValueError("Non-runtime profile has no " "deployment evidence source.")

    @staticmethod
    def _collect_compose(
        *,
        project_root: Path,
        subject_root: Path,
        profile: NonRuntimeEvidenceProfile,
    ) -> tuple[
        tuple[
            NormalizedObservation,
            ...,
        ],
        Path,
    ]:
        compose = profile.compose

        assert compose is not None

        rendered = DockerComposeRenderer().render(
            subject_root=(subject_root),
            compose_files=tuple(Path(path) for path in (compose.files)),
            project_directory=(Path(compose.project_directory)),
        )

        output_file = (
            project_root
            / "evidence"
            / "real"
            / "non-runtime"
            / profile.subject_id
            / "compose.resolved.json"
        )

        rendered.write_json(output_file)

        adapter = ComposeAdapter(
            project_root,
            output_file.relative_to(project_root),
            node_types=(profile.node_types),
        )

        return (
            adapter.collect(),
            output_file,
        )

    @staticmethod
    def _collect_aspire(
        *,
        subject_root: Path,
        profile: NonRuntimeEvidenceProfile,
    ) -> tuple[
        NormalizedObservation,
        ...,
    ]:
        aspire = profile.aspire

        assert aspire is not None

        observations: list[NormalizedObservation] = []

        for apphost_file in aspire.files:
            observations.extend(
                AspireAdapter(
                    subject_root,
                    apphost_file,
                ).collect()
            )

        return tuple(observations)
