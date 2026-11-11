from __future__ import annotations

import subprocess
import sys
from pathlib import Path

MUTATIONS = (
    "AS-M01",
    "AS-M02",
    "AS-M03",
    "AS-M04",
    "AS-M05",
    "AS-M06",
)


def run_execution(
    *,
    project_root: Path,
    mutation_id: str,
    variant: str,
) -> None:
    command = [
        sys.executable,
        "tools/run_astronomy_runtime.py",
        "--mutation",
        mutation_id,
        "--variant",
        variant,
    ]

    if variant == "mutant":
        command.append("--replace-mutant")

    print()
    print("=" * 80)
    print(f"[SUITE] {mutation_id} / {variant}")
    print("=" * 80)

    process = subprocess.run(
        command,
        cwd=project_root,
        check=False,
    )

    if process.returncode != 0:
        raise SystemExit(f"Runtime suite failed: " f"{mutation_id}/{variant}")


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]

    for mutation_id in MUTATIONS:
        run_execution(
            project_root=project_root,
            mutation_id=mutation_id,
            variant="baseline",
        )

        run_execution(
            project_root=project_root,
            mutation_id=mutation_id,
            variant="mutant",
        )

    print()
    print("[OK] Astronomy runtime suite completed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
