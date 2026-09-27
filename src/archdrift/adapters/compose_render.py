from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ComposeRenderError(RuntimeError):
    """Raised when Docker Compose cannot produce a resolved model."""


@dataclass(frozen=True, slots=True)
class RenderedComposeConfig:
    subject_root: Path
    source_files: tuple[Path, ...]
    document: dict[str, Any]

    def write_json(
        self,
        destination: Path,
    ) -> None:
        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        serialized = json.dumps(
            self.document,
            indent=2,
            sort_keys=True,
        )

        destination.write_text(
            serialized + "\n",
            encoding="utf-8",
        )


class DockerComposeRenderer:
    """
    Render a Docker Compose application through the official Compose CLI.

    ArchitectureDrift deliberately delegates interpolation, `.env`
    resolution, overlay merging, and Compose model semantics to Docker
    Compose instead of partially reimplementing the Compose specification.
    """

    def __init__(
        self,
        *,
        docker_executable: str = "docker",
    ) -> None:
        self._docker_executable = docker_executable

    def render(
        self,
        *,
        subject_root: Path,
        compose_files: tuple[Path, ...],
        project_directory: Path | None = None,
    ) -> RenderedComposeConfig:
        root = subject_root.resolve()

        if not root.is_dir():
            raise ComposeRenderError(
                f"Subject root does not exist: {root}"
            )

        if not compose_files:
            raise ComposeRenderError(
                "At least one Compose file is required."
            )

        resolved_files = tuple(
            self._resolve_compose_file(
                subject_root=root,
                compose_file=compose_file,
            )
            for compose_file in compose_files
        )

        resolved_project_directory = (
            root
            if project_directory is None
            else self._resolve_project_directory(
                subject_root=root,
                project_directory=project_directory,
            )
        )

        command = self._build_command(
            subject_root=root,
            compose_files=resolved_files,
            project_directory=resolved_project_directory,
        )

        result = self._run(
            command,
            cwd=root,
        )

        try:
            document = json.loads(
                result.stdout
            )
        except json.JSONDecodeError as exc:
            raise ComposeRenderError(
                "Docker Compose returned invalid JSON."
            ) from exc

        if not isinstance(
            document,
            dict,
        ):
            raise ComposeRenderError(
                "Resolved Compose model must be a JSON object."
            )

        services = document.get(
            "services"
        )

        if not isinstance(
            services,
            dict,
        ):
            raise ComposeRenderError(
                "Resolved Compose model does not contain "
                "a services mapping."
            )

        return RenderedComposeConfig(
            subject_root=root,
            source_files=resolved_files,
            document=document,
        )

    def _build_command(
        self,
        *,
        subject_root: Path,
        compose_files: tuple[Path, ...],
        project_directory: Path,
    ) -> tuple[str, ...]:
        arguments: list[str] = [
            self._docker_executable,
            "compose",
            "--project-directory",
            str(project_directory),
        ]

        for compose_file in compose_files:
            arguments.extend(
                (
                    "-f",
                    str(compose_file),
                )
            )

        arguments.extend(
            (
                "config",
                "--format",
                "json",
            )
        )

        return tuple(
            arguments
        )

    def _run(
        self,
        command: tuple[str, ...],
        *,
        cwd: Path,
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
            raise ComposeRenderError(
                "Docker executable was not found on PATH."
            ) from exc

        if result.returncode != 0:
            error = (
                result.stderr.strip()
                or result.stdout.strip()
                or "Unknown Docker Compose error."
            )

            raise ComposeRenderError(
                "Docker Compose rendering failed.\n"
                f"Command: {' '.join(command)}\n"
                f"{error}"
            )

        return result

    @staticmethod
    def _resolve_compose_file(
        *,
        subject_root: Path,
        compose_file: Path,
    ) -> Path:
        candidate = (
            subject_root
            / compose_file
        ).resolve()

        try:
            candidate.relative_to(
                subject_root
            )
        except ValueError as exc:
            raise ComposeRenderError(
                f"Compose file escapes subject root: {compose_file}"
            ) from exc

        if not candidate.is_file():
            raise ComposeRenderError(
                f"Compose file does not exist: {candidate}"
            )

        return candidate

    @staticmethod
    def _resolve_project_directory(
        *,
        subject_root: Path,
        project_directory: Path,
    ) -> Path:
        candidate = (
            subject_root
            / project_directory
        ).resolve()

        try:
            candidate.relative_to(
                subject_root
            )
        except ValueError as exc:
            raise ComposeRenderError(
                "Compose project directory escapes subject root: "
                f"{project_directory}"
            ) from exc

        if not candidate.is_dir():
            raise ComposeRenderError(
                "Compose project directory does not exist: "
                f"{candidate}"
            )

        return candidate