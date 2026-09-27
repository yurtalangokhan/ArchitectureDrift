from __future__ import annotations

import argparse
from pathlib import Path

from archdrift.adapters.compose_render import (
    DockerComposeRenderer,
)


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "subject",
        choices=(
            "astronomy-shop",
            "teastore",
        ),
    )

    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
    )

    args = parser.parse_args()

    root = args.project_root.resolve()

    renderer = DockerComposeRenderer()

    if args.subject == "astronomy-shop":
        subject_root = (
            root
            / "subjects"
            / "astronomy-shop"
        )

        compose_files = (
            Path("compose.yaml"),
            Path("compose.full.yaml"),
        )

        compose_project_directory = Path(".")

    else:
        subject_root = (
            root
            / "subjects"
            / "teastore"
        )

        compose_files = (
            Path(
                "examples/docker/"
                "docker-compose_default.yaml"
            ),
        )

        compose_project_directory = Path(
            "examples/docker"
        )

    rendered = renderer.render(
        subject_root=subject_root,
        compose_files=compose_files,
        project_directory=compose_project_directory,
    )

    output = (
        root
        / "evidence"
        / "real"
        / "non-runtime"
        / args.subject
        / "compose.resolved.json"
    )

    rendered.write_json(
        output
    )

    print(
        f"Subject: {args.subject}"
    )

    print(
        f"Services: "
        f"{len(rendered.document['services'])}"
    )

    print(
        f"Output: {output}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )