from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

WORKSPACE = (
    PROJECT_ROOT
    / "workspaces"
    / "authoring"
    / "astronomy-shop"
    / "AS-M02"
)

COMPOSE_FILE = (
    WORKSPACE
    / "compose.yaml"
)

PAYMENT_FILE = (
    WORKSPACE
    / "src"
    / "payment"
    / "index.js"
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


def update_compose() -> None:
    content = COMPOSE_FILE.read_text(
        encoding="utf-8",
    )

    old = """      - PAYMENT_PORT
      - FLAGD_HOST"""

    new = """      - PAYMENT_PORT
      - SHIPPING_ADDR=${SHIPPING_ADDR}
      - FLAGD_HOST"""

    content = replace_once(
        content,
        old,
        new,
        name="payment SHIPPING_ADDR deployment binding",
        already_applied_marker=(
            "      - SHIPPING_ADDR=${SHIPPING_ADDR}"
        ),
    )

    COMPOSE_FILE.write_text(
        content,
        encoding="utf-8",
    )


def update_payment() -> None:
    content = PAYMENT_FILE.read_text(
        encoding="utf-8",
    )

    old = """async function chargeServiceHandler(call, callback) {
  const span = opentelemetry.trace.getActiveSpan();

  try {"""

    new = """async function invokeASMutationShipping(call) {
  const metadata = call.metadata.get('x-archdrift-as-m02')

  if (metadata.length === 0 || metadata[0] !== 'true') {
    return
  }

  const shippingAddress = process.env.SHIPPING_ADDR

  if (!shippingAddress) {
    throw new Error('AS-M02 requires SHIPPING_ADDR')
  }

  await fetch(`http://${shippingAddress}/get-quote`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json'
    },
    body: JSON.stringify({
      address: {},
      items: []
    })
  })
}

async function chargeServiceHandler(call, callback) {
  const span = opentelemetry.trace.getActiveSpan();

  try {
    await invokeASMutationShipping(call)"""

    content = replace_once(
        content,
        old,
        new,
        name="payment to shipping dormant call",
        already_applied_marker=(
            "async function invokeASMutationShipping(call)"
        ),
    )

    PAYMENT_FILE.write_text(
        content,
        encoding="utf-8",
    )


def main() -> int:
    if not COMPOSE_FILE.is_file():
        raise FileNotFoundError(
            f"Compose file not found: {COMPOSE_FILE}"
        )

    if not PAYMENT_FILE.is_file():
        raise FileNotFoundError(
            f"Payment source not found: {PAYMENT_FILE}"
        )

    update_compose()
    update_payment()

    print()
    print(f"Updated: {COMPOSE_FILE}")
    print(f"Updated: {PAYMENT_FILE}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())