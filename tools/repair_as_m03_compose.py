from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

COMPOSE_FILE = (
    PROJECT_ROOT
    / "workspaces"
    / "authoring"
    / "astronomy-shop"
    / "AS-M03"
    / "compose.yaml"
)


def main() -> int:
    if not COMPOSE_FILE.is_file():
        raise FileNotFoundError(
            f"Compose file not found: {COMPOSE_FILE}"
        )

    content = COMPOSE_FILE.read_text(
        encoding="utf-8",
    )

    old = """      - AD_ADDR
      - CART_ADDR
      - CHECKOUT_ADDR
      - CURRENCY_ADDR
      - PRODUCT_CATALOG_ADDR
      - RECOMMENDATION_ADDR
      - SHIPPING_ADDR"""

    new = """      - AD_ADDR
      - CART_ADDR
      - CHECKOUT_ADDR
      - PAYMENT_ADDR
      - CURRENCY_ADDR
      - PRODUCT_CATALOG_ADDR
      - RECOMMENDATION_ADDR
      - SHIPPING_ADDR"""

    # Check only the exact frontend environment block.
    if new in content:
        print(
            "[SKIP] frontend PAYMENT_ADDR already present"
        )
        return 0

    count = content.count(old)

    if count != 1:
        raise RuntimeError(
            "Expected exactly one frontend environment block, "
            f"found {count}"
        )

    content = content.replace(
        old,
        new,
        1,
    )

    COMPOSE_FILE.write_text(
        content,
        encoding="utf-8",
    )

    print(
        "[APPLY] frontend PAYMENT_ADDR"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())