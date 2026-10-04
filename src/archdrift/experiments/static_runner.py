from __future__ import annotations

from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
)

from archdrift.adapters.semgrep import (
    SemgrepResultAdapter,
    SemgrepRunner,
)
from archdrift.model.source_static import (
    SourceStaticFinding,
)
from archdrift.model.static_profile import (
    StaticEvidenceProfile,
)


class StaticScanResult(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    subject_id: str

    findings: tuple[SourceStaticFinding, ...]


def _normalize_finding_path(
    finding: SourceStaticFinding,
    *,
    subject_root: Path,
) -> SourceStaticFinding:
    candidate = Path(finding.path)

    try:
        relative = candidate.resolve().relative_to(subject_root.resolve())

        normalized = relative.as_posix()

    except ValueError:
        normalized = finding.path.replace(
            "\\",
            "/",
        )

    return finding.model_copy(
        update={
            "path": normalized,
        }
    )


class StaticEvidenceRunner:
    def __init__(
        self,
        *,
        semgrep: SemgrepRunner | None = None,
    ) -> None:
        self._semgrep = semgrep or SemgrepRunner()

    def run(
        self,
        *,
        profile: StaticEvidenceProfile,
        subject_root: Path,
        rule_pack_root: Path,
        output_root: Path,
    ) -> StaticScanResult:
        findings: list[SourceStaticFinding] = []

        seen: set[
            tuple[
                str,
                str,
                int,
                str,
            ]
        ] = set()

        for source in profile.source_roots:
            target = subject_root / source.path

            if not target.exists():
                raise FileNotFoundError("Static source root not found: " f"{target}")

            for pack in source.rule_packs:
                config = rule_pack_root / f"{pack}.yaml"

                if not config.is_file():
                    raise FileNotFoundError("Semgrep rule pack not found: " f"{config}")

                output_file = output_root / source.service_id / f"{pack}.json"

                output_file.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                self._semgrep.scan(
                    subject_root=target,
                    rules=config,
                    output=output_file,
                )

                pack_findings = SemgrepResultAdapter().collect(output_file)

                for raw_finding in pack_findings:
                    finding = _normalize_finding_path(
                        raw_finding,
                        subject_root=(subject_root),
                    )

                    identity = (
                        finding.rule_id,
                        finding.path,
                        finding.line,
                        finding.target_expression,
                    )

                    if identity in seen:
                        continue

                    seen.add(identity)

                    findings.append(finding)

        return StaticScanResult(
            subject_id=(profile.subject_id),
            findings=tuple(
                sorted(
                    findings,
                    key=lambda finding: (
                        finding.path,
                        finding.line,
                        finding.rule_id,
                        finding.target_expression,
                    ),
                )
            ),
        )
