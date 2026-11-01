from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

WORKSPACE = (
    PROJECT_ROOT
    / "workspaces"
    / "authoring"
    / "astronomy-shop"
    / "AS-M05"
)

KAFKA_SERVICE_FILE = (
    WORKSPACE
    / "src"
    / "frontend"
    / "services"
    / "ASMutationKafka.service.ts"
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


def create_kafka_service() -> None:
    if KAFKA_SERVICE_FILE.exists():
        content = KAFKA_SERVICE_FILE.read_text(
            encoding="utf-8",
        )

        if "publishASMutationKafka" in content:
            print(
                "[SKIP] ASMutationKafka.service.ts: "
                "already created"
            )
            return

        raise RuntimeError(
            f"Unexpected existing file: {KAFKA_SERVICE_FILE}"
        )

    content = """// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import {
  SpanKind,
  SpanStatusCode,
  trace,
} from '@opentelemetry/api';
import {
  Kafka,
  logLevel,
  Producer,
} from 'kafkajs';

const AS_M05_BROKER = 'kafka:9092';
const AS_M05_TOPIC = 'orders';

const kafka = new Kafka({
  clientId: 'frontend-as-m05',
  brokers: [AS_M05_BROKER],
  logLevel: logLevel.NOTHING,
});

const producer: Producer = kafka.producer();

let connectPromise: Promise<void> | undefined;

async function ensureConnected(): Promise<void> {
  if (!connectPromise) {
    connectPromise = producer.connect();
  }

  try {
    await connectPromise;
  } catch (error) {
    connectPromise = undefined;
    throw error;
  }
}

export interface ASMutationKafkaEvent {
  orderId: string;
  userId: string;
}

export async function publishASMutationKafka(
  event: ASMutationKafkaEvent
): Promise<void> {
  const tracer = trace.getTracer('frontend-as-m05');

  await tracer.startActiveSpan(
    'AS-M05 kafka publish',
    {
      kind: SpanKind.PRODUCER,
    },
    async span => {
      try {
        await ensureConnected();

        await producer.send({
          topic: AS_M05_TOPIC,
          messages: [
            {
              value: JSON.stringify(event),
            },
          ],
        });

        // These attributes are added only after the real Kafka send
        // succeeds. Failed connection/send attempts therefore cannot
        // become false-positive PUBLISHES_TO observations.
        span.setAttributes({
          'messaging.system': 'kafka',
          'messaging.operation.type': 'send',
          'messaging.operation.name': 'send',
          'messaging.destination.name': AS_M05_TOPIC,
          'server.address': 'kafka',
          'server.port': 9092,
        });
      } catch (error) {
        span.setStatus({
          code: SpanStatusCode.ERROR,
        });

        if (error instanceof Error) {
          span.recordException(error);
        }

        throw error;
      } finally {
        span.end();
      }
    }
  );
}
"""

    KAFKA_SERVICE_FILE.write_text(
        content,
        encoding="utf-8",
    )

    print(
        "[APPLY] AS-M05 Kafka producer service"
    )


def update_checkout_api() -> None:
    content = CHECKOUT_API_FILE.read_text(
        encoding="utf-8",
    )

    content = replace_once(
        content,
        """import ProductCatalogService from '../../services/ProductCatalog.service';""",
        """import ProductCatalogService from '../../services/ProductCatalog.service';
import { publishASMutationKafka } from '../../services/ASMutationKafka.service';""",
        name="AS-M05 Kafka service import",
        already_applied_marker=(
            "publishASMutationKafka"
        ),
    )

    content = replace_once(
        content,
        """      const { order: { items = [], ...order } = {} } = placeOrderResponse;

      const productList: IProductCheckoutItem[] = await Promise.all(""",
        """      try {
        await publishASMutationKafka({
          orderId: placeOrderResponse.order?.orderId ?? '',
          userId: orderData.userId,
        });
      } catch (error) {
        logger.warn(
          { err: error },
          'AS-M05 Kafka mutation publish failed'
        );
      }

      const { order: { items = [], ...order } = {} } = placeOrderResponse;

      const productList: IProductCheckoutItem[] = await Promise.all(""",
        name="AS-M05 checkout publish invocation",
        already_applied_marker=(
            "AS-M05 Kafka mutation publish failed"
        ),
    )

    CHECKOUT_API_FILE.write_text(
        content,
        encoding="utf-8",
    )


def main() -> int:
    if not CHECKOUT_API_FILE.is_file():
        raise FileNotFoundError(
            f"Checkout API not found: {CHECKOUT_API_FILE}"
        )

    create_kafka_service()
    update_checkout_api()

    print()
    print(f"Created: {KAFKA_SERVICE_FILE}")
    print(f"Updated: {CHECKOUT_API_FILE}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())