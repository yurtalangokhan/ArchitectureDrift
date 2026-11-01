from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

WORKSPACE = (
    PROJECT_ROOT
    / "workspaces"
    / "authoring"
    / "eshop"
    / "ES-M02"
)

APPHOST_FILE = (
    WORKSPACE
    / "src"
    / "eShop.AppHost"
    / "Program.cs"
)


def replace_once(
    content: str,
    old: str,
    new: str,
    *,
    name: str,
    already_applied_marker: str,
) -> str:
    if already_applied_marker in content:
        print(f"[SKIP] {name}: already applied")
        return content

    count = content.count(old)

    if count != 1:
        raise RuntimeError(
            f"{name}: expected exactly one replacement target, "
            f"found {count}"
        )

    print(f"[APPLY] {name}")

    return content.replace(
        old,
        new,
        1,
    )


def main() -> int:
    if not APPHOST_FILE.is_file():
        raise FileNotFoundError(
            f"AppHost file not found: {APPHOST_FILE}"
        )

    content = APPHOST_FILE.read_text(
        encoding="utf-8-sig",
    )

    content = replace_once(
        content,
        """    .WithReference(basketApi)
    .WithReference(catalogApi)
    .WithReference(orderingApi)
    .WithReference(rabbitMq).WaitFor(rabbitMq)""",
        """    .WithReference(basketApi)
    .WithReference(catalogApi)
    .WithReference(orderingApi)
    .WithReference(webHooksApi)
    .WithReference(rabbitMq).WaitFor(rabbitMq)""",
        name="ES-M02 WebApp to Webhooks API reference",
        already_applied_marker=(
            ".WithReference(orderingApi)\n"
            "    .WithReference(webHooksApi)\n"
            "    .WithReference(rabbitMq)"
        ),
    )

    APPHOST_FILE.write_text(
        content,
        encoding="utf-8-sig",
    )

    print()
    print(f"Updated: {APPHOST_FILE}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())