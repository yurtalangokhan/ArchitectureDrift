from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from archdrift.model.observation import (
    InteractionType,
)
from archdrift.model.source_static import (
    SourceStaticFinding,
)


class SemgrepAdapterError(RuntimeError):
    """Base exception for Semgrep integration."""


class SemgrepExecutionError(SemgrepAdapterError):
    """Raised when the Semgrep CLI cannot execute successfully."""


class SemgrepResultError(SemgrepAdapterError):
    """Raised when Semgrep JSON violates the expected result contract."""


_RULE_ID_PREFIX = "archdrift."


def _canonical_rule_id(
    raw_rule_id: str,
) -> str:
    index = raw_rule_id.rfind(_RULE_ID_PREFIX)

    if index < 0:
        raise SemgrepResultError(
            "Semgrep result is not an ArchitectureDrift rule: " f"{raw_rule_id!r}"
        )

    rule_id = raw_rule_id[index:]

    if not rule_id:
        raise SemgrepResultError("ArchitectureDrift Semgrep rule id is empty.")

    return rule_id


class _SemgrepPosition(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        frozen=True,
    )

    line: int = Field(
        ge=1,
    )


class _SemgrepMetavariable(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        frozen=True,
    )

    abstract_content: str


class _ArchDriftRuleMetadata(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    interaction: InteractionType
    protocol: str | None = None


class _SemgrepRuleMetadata(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        frozen=True,
    )

    archdrift: _ArchDriftRuleMetadata


class _SemgrepExtra(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        frozen=True,
    )

    message: str
    metadata: _SemgrepRuleMetadata


class _SemgrepResult(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        frozen=True,
    )

    check_id: str

    path: str

    start: _SemgrepPosition

    extra: _SemgrepExtra


class _SemgrepDocument(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        frozen=True,
    )

    results: tuple[
        _SemgrepResult,
        ...,
    ] = ()


class SemgrepResultAdapter:
    """
    Convert Semgrep JSON output into ArchitectureDrift static findings.

    Only explicitly registered ArchitectureDrift rule ids are accepted.
    This makes rule semantics versioned and deterministic.
    """

    def collect(
        self,
        result_file: Path,
    ) -> tuple[
        SourceStaticFinding,
        ...,
    ]:
        path = result_file.resolve()

        if not path.is_file():
            raise FileNotFoundError(f"Semgrep result file not found: {path}")

        try:
            document = json.loads(
                path.read_text(
                    encoding="utf-8",
                )
            )

        except json.JSONDecodeError as exc:
            raise SemgrepResultError(f"Invalid Semgrep JSON: {path}") from exc

        parsed = _SemgrepDocument.model_validate(document)

        findings: list[SourceStaticFinding] = []

        seen: set[
            tuple[
                str,
                str,
                int,
                str,
            ]
        ] = set()

        for result in parsed.results:
            rule_id = _canonical_rule_id(result.check_id)

            semantics = result.extra.metadata.archdrift

            target_expression = _extract_target_expression(result.extra.message)
            normalized_path = Path(result.path).as_posix()

            identity = (
                rule_id,
                normalized_path,
                result.start.line,
                target_expression,
            )

            if identity in seen:
                continue

            seen.add(identity)

            findings.append(
                SourceStaticFinding(
                    rule_id=rule_id,
                    path=normalized_path,
                    line=result.start.line,
                    interaction=(semantics.interaction),
                    target_expression=(target_expression),
                    protocol=(semantics.protocol),
                )
            )

        return tuple(
            sorted(
                findings,
                key=lambda finding: (
                    finding.path,
                    finding.line,
                    finding.rule_id,
                    finding.target_expression,
                ),
            )
        )


_TARGET_MESSAGE_PREFIX = "ARCHDRIFT_TARGET="


def _extract_target_expression(
    message: str,
) -> str:
    """
    Extract the matched endpoint expression emitted by an ArchitectureDrift
    Semgrep rule.

    Semgrep officially supports metavariable interpolation in rule messages.
    The message is therefore used as a stable CE-compatible extraction
    boundary instead of relying on optional JSON metavariable internals.
    """

    normalized = message.strip()

    if not normalized.startswith(_TARGET_MESSAGE_PREFIX):
        raise SemgrepResultError(
            "ArchitectureDrift Semgrep result does not contain "
            "the expected target marker: "
            f"{message!r}"
        )

    target_expression = normalized[len(_TARGET_MESSAGE_PREFIX) :].strip()

    if not target_expression:
        raise SemgrepResultError(
            "ArchitectureDrift Semgrep result contains " "an empty target expression."
        )

    return target_expression


class SemgrepRunner:
    """
    Execute Semgrep Community Edition using local ArchitectureDrift rules.

    The runner does not perform architecture inference.
    """

    def __init__(
        self,
        *,
        executable: str = "semgrep",
    ) -> None:
        self._executable = executable

    def version(
        self,
    ) -> str:
        result = self._run(
            (
                self._executable,
                "--version",
            ),
            cwd=None,
        )

        version = result.stdout.strip()

        if not version:
            raise SemgrepExecutionError("Semgrep returned an empty version string.")

        return version

    def scan(
        self,
        *,
        subject_root: Path,
        rules: Path,
        output: Path,
    ) -> Path:
        root = subject_root.resolve()
        rule_file = rules.resolve()
        destination = output.resolve()

        if not root.is_dir():
            raise SemgrepExecutionError(f"Subject root does not exist: {root}")

        if not rule_file.is_file():
            raise SemgrepExecutionError(
                f"Semgrep rule file does not exist: {rule_file}"
            )

        result = self._run(
            (
                self._executable,
                "scan",
                "--config",
                str(rule_file),
                "--json",
                "--quiet",
                str(root),
            ),
            cwd=root,
        )

        try:
            document: Any = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise SemgrepExecutionError("Semgrep did not return valid JSON.") from exc

        if not isinstance(
            document,
            dict,
        ):
            raise SemgrepExecutionError("Semgrep JSON root must be an object.")

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        destination.write_text(
            json.dumps(
                document,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        return destination

    @staticmethod
    def _run(
        command: tuple[str, ...],
        *,
        cwd: Path | None,
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )

        except FileNotFoundError as exc:
            raise SemgrepExecutionError(
                "Semgrep executable was not found on PATH."
            ) from exc

        if result.returncode != 0:
            error = (
                result.stderr.strip()
                or result.stdout.strip()
                or "Unknown Semgrep error."
            )

            raise SemgrepExecutionError(
                "Semgrep command failed.\n" f"Command: {' '.join(command)}\n" f"{error}"
            )

        return result
