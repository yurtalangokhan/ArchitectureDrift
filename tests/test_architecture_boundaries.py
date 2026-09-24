from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "archdrift"


FORBIDDEN_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "model": (
        "archdrift.adapters",
        "archdrift.analysis",
        "archdrift.experiments",
        "archdrift.cli",
    ),
    "adapters": (
        "archdrift.analysis",
        "archdrift.experiments",
        "archdrift.cli",
    ),
    "analysis": (
        "archdrift.adapters",
        "archdrift.experiments",
        "archdrift.cli",
    ),
}


def _python_files(package_name: str) -> tuple[Path, ...]:
    package_path = SOURCE_ROOT / package_name

    return tuple(
        sorted(
            package_path.rglob("*.py")
        )
    )


def _imported_modules(
    file_path: Path,
) -> tuple[str, ...]:
    tree = ast.parse(
        file_path.read_text(
            encoding="utf-8"
        ),
        filename=str(file_path),
    )

    imports: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(
                alias.name
                for alias in node.names
            )

        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:
                imports.append(
                    node.module
                )

    return tuple(imports)


def _matches_forbidden_dependency(
    imported_module: str,
    forbidden_prefix: str,
) -> bool:
    return (
        imported_module == forbidden_prefix
        or imported_module.startswith(
            f"{forbidden_prefix}."
        )
    )


def test_package_dependency_boundaries() -> None:
    violations: list[str] = []

    for package_name, forbidden_dependencies in (
        FORBIDDEN_DEPENDENCIES.items()
    ):
        for file_path in _python_files(
            package_name
        ):
            imported_modules = _imported_modules(
                file_path
            )

            for imported_module in imported_modules:
                for forbidden_dependency in (
                    forbidden_dependencies
                ):
                    if not _matches_forbidden_dependency(
                        imported_module,
                        forbidden_dependency,
                    ):
                        continue

                    relative_path = file_path.relative_to(
                        PROJECT_ROOT
                    )

                    violations.append(
                        f"{relative_path}: "
                        f"{imported_module}"
                    )

    assert not violations, (
        "Architecture package dependency "
        "violations detected:\n"
        + "\n".join(
            f"  - {violation}"
            for violation in violations
        )
    )