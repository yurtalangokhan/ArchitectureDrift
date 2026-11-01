from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

WORKSPACE = (
    PROJECT_ROOT
    / "workspaces"
    / "authoring"
    / "astronomy-shop"
    / "AS-M03"
)

COMPOSE_FILE = WORKSPACE / "compose.yaml"

PAYMENT_GATEWAY_FILE = (
    WORKSPACE
    / "src"
    / "frontend"
    / "gateways"
    / "rpc"
    / "Payment.gateway.ts"
)

CHECKOUT_API_FILE = (
    WORKSPACE
    / "src"
    / "frontend"
    / "pages"
    / "api"
    / "checkout.ts"
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

    content = replace_once(
        content,
        """      - CART_ADDR
      - CHECKOUT_ADDR
      - CURRENCY_ADDR""",
        """      - CART_ADDR
      - CHECKOUT_ADDR
      - PAYMENT_ADDR
      - CURRENCY_ADDR""",
        name="frontend PAYMENT_ADDR deployment binding",
        already_applied_marker="      - PAYMENT_ADDR",
    )

    COMPOSE_FILE.write_text(
        content,
        encoding="utf-8",
    )


def create_payment_gateway() -> None:
    if PAYMENT_GATEWAY_FILE.exists():
        existing = PAYMENT_GATEWAY_FILE.read_text(
            encoding="utf-8",
        )

        if "PaymentServiceClient" in existing:
            print(
                "[SKIP] Payment.gateway.ts: already created"
            )
            return

        raise RuntimeError(
            f"Unexpected existing file: {PAYMENT_GATEWAY_FILE}"
        )

    content = """// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { ChannelCredentials } from '@grpc/grpc-js';
import {
  ChargeRequest,
  ChargeResponse,
  PaymentServiceClient,
} from '../../protos/demo';

const { PAYMENT_ADDR = '' } = process.env;

const client = new PaymentServiceClient(
  PAYMENT_ADDR,
  ChannelCredentials.createInsecure()
);

const PaymentGateway = () => ({
  charge(request: ChargeRequest) {
    return new Promise<ChargeResponse>(
      (resolve, reject) =>
        client.charge(
          request,
          (error, response) =>
            error
              ? reject(error)
              : resolve(response)
        )
    );
  },
});

export default PaymentGateway();
"""

    PAYMENT_GATEWAY_FILE.write_text(
        content,
        encoding="utf-8",
    )

    print(
        "[APPLY] frontend Payment gateway"
    )


def update_checkout_api() -> None:
    content = CHECKOUT_API_FILE.read_text(
        encoding="utf-8",
    )

    content = replace_once(
        content,
        """import CheckoutGateway from '../../gateways/rpc/Checkout.gateway';
import { Empty, PlaceOrderRequest, PlaceOrderResponse } from '../../protos/demo';""",
        """import CheckoutGateway from '../../gateways/rpc/Checkout.gateway';
import PaymentGateway from '../../gateways/rpc/Payment.gateway';
import { Empty, PlaceOrderRequest, PlaceOrderResponse } from '../../protos/demo';""",
        name="Payment gateway import",
        already_applied_marker=(
            "import PaymentGateway from "
            "'../../gateways/rpc/Payment.gateway';"
        ),
    )

    content = replace_once(
        content,
        """      const { order: { items = [], ...order } = {} } = placeOrderResponse;

      const productList: IProductCheckoutItem[] = await Promise.all(""",
        """      try {
        await PaymentGateway.charge({
          amount: {
            currencyCode: 'USD',
            units: 0,
            nanos: 0,
          },
          creditCard: {
            creditCardNumber: '4111111111111111',
            creditCardCvv: 111,
            creditCardExpirationYear: 2099,
            creditCardExpirationMonth: 12,
          },
        });
      } catch (error) {
        logger.warn(
          { err: error },
          'AS-M03 payment mutation call failed'
        );
      }

      const { order: { items = [], ...order } = {} } = placeOrderResponse;

      const productList: IProductCheckoutItem[] = await Promise.all(""",
        name="runtime frontend to payment invocation",
        already_applied_marker=(
            "AS-M03 payment mutation call failed"
        ),
    )

    CHECKOUT_API_FILE.write_text(
        content,
        encoding="utf-8",
    )


def main() -> int:
    if not COMPOSE_FILE.is_file():
        raise FileNotFoundError(
            f"Compose file not found: {COMPOSE_FILE}"
        )

    if not CHECKOUT_API_FILE.is_file():
        raise FileNotFoundError(
            f"Checkout API file not found: {CHECKOUT_API_FILE}"
        )

    update_compose()
    create_payment_gateway()
    update_checkout_api()

    print()
    print(f"Updated: {COMPOSE_FILE}")
    print(f"Created: {PAYMENT_GATEWAY_FILE}")
    print(f"Updated: {CHECKOUT_API_FILE}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())