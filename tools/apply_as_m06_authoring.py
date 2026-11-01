from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

WORKSPACE = (
    PROJECT_ROOT
    / "workspaces"
    / "authoring"
    / "astronomy-shop"
    / "AS-M06"
)

CHECKOUT_FILE = (
    WORKSPACE
    / "src"
    / "checkout"
    / "main.go"
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
    if not CHECKOUT_FILE.is_file():
        raise FileNotFoundError(
            f"Checkout main.go not found: {CHECKOUT_FILE}"
        )

    content = CHECKOUT_FILE.read_text(
        encoding="utf-8",
    )

    # ------------------------------------------------------------------
    # A. Add real Kafka consumer implementation.
    #
    # The consumer uses an isolated consumer group so it does not steal
    # messages from Accounting or Fraud Detection.
    #
    # The CONSUMER span is emitted only after Sarama actually delivers a
    # Kafka message to ConsumeClaim.
    # ------------------------------------------------------------------

    consumer_implementation = r'''
type asM06ConsumerGroupHandler struct {
	tracer     trace.Tracer
	brokerHost string
}

func (h *asM06ConsumerGroupHandler) Setup(
	sarama.ConsumerGroupSession,
) error {
	return nil
}

func (h *asM06ConsumerGroupHandler) Cleanup(
	sarama.ConsumerGroupSession,
) error {
	return nil
}

func (h *asM06ConsumerGroupHandler) ConsumeClaim(
	session sarama.ConsumerGroupSession,
	claim sarama.ConsumerGroupClaim,
) error {
	for {
		select {
		case <-session.Context().Done():
			return nil

		case message, ok := <-claim.Messages():
			if !ok {
				return nil
			}

			_, span := h.tracer.Start(
				session.Context(),
				"AS-M06 kafka receive",
				trace.WithSpanKind(
					trace.SpanKindConsumer,
				),
			)

			span.SetAttributes(
				attribute.String(
					"messaging.system",
					"kafka",
				),
				attribute.String(
					"messaging.operation.type",
					"receive",
				),
				attribute.String(
					"messaging.operation.name",
					"receive",
				),
				attribute.String(
					"messaging.destination.name",
					message.Topic,
				),
				attribute.String(
					"server.address",
					h.brokerHost,
				),
			)

			span.End()

			session.MarkMessage(
				message,
				"AS-M06 architecture mutation observation",
			)
		}
	}
}

func asM06BrokerHost(
	brokerAddress string,
) string {
	host, _, err := net.SplitHostPort(
		brokerAddress,
	)

	if err == nil && host != "" {
		return host
	}

	return brokerAddress
}

func startASMutationKafkaConsumer(
	ctx context.Context,
	brokerAddress string,
	topic string,
	logger *slog.Logger,
	tracer trace.Tracer,
) (func() error, error) {
	config := sarama.NewConfig()

	config.Version = sarama.V3_0_0_0
	config.Consumer.Offsets.Initial = sarama.OffsetNewest

	group, err := sarama.NewConsumerGroup(
		[]string{
			brokerAddress,
		},
		"checkout-as-m06",
		config,
	)
	if err != nil {
		return nil, err
	}

	handler := &asM06ConsumerGroupHandler{
		tracer: tracer,
		brokerHost: asM06BrokerHost(
			brokerAddress,
		),
	}

	go func() {
		for ctx.Err() == nil {
			err := group.Consume(
				ctx,
				[]string{
					topic,
				},
				handler,
			)

			if ctx.Err() != nil {
				return
			}

			if err != nil {
				logger.Warn(
					"AS-M06 Kafka consumer session failed",
					slog.Any(
						"error",
						err,
					),
				)

				timer := time.NewTimer(
					time.Second,
				)

				select {
				case <-ctx.Done():
					if !timer.Stop() {
						<-timer.C
					}

					return

				case <-timer.C:
				}
			}
		}
	}()

	return group.Close, nil
}

'''

    content = replace_once(
        content,
        "func main() {",
        consumer_implementation + "func main() {",
        name="AS-M06 Kafka consumer implementation",
        already_applied_marker=(
            "type asM06ConsumerGroupHandler struct"
        ),
    )

    # ------------------------------------------------------------------
    # B. Start consumer using the existing KAFKA_ADDR/KAFKA_TOPIC.
    #
    # No Compose mutation is required. The deployment already supplies
    # these values to checkout.
    # ------------------------------------------------------------------

    old = """\tctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
\tdefer cancel()

\tgo func() {"""

    new = """\tctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
\tdefer cancel()

\tif svc.kafkaBrokerSvcAddr != "" {
\t\tstopASMutationKafkaConsumer, consumerErr := startASMutationKafkaConsumer(
\t\t\tctx,
\t\t\tsvc.kafkaBrokerSvcAddr,
\t\t\tkafka.Topic,
\t\t\tlogger,
\t\t\ttracer,
\t\t)

\t\tif consumerErr != nil {
\t\t\tlogger.Error(
\t\t\t\t"Failed to start AS-M06 Kafka consumer",
\t\t\t\tslog.Any(
\t\t\t\t\t"error",
\t\t\t\t\tconsumerErr,
\t\t\t\t),
\t\t\t)
\t\t} else {
\t\t\tdefer func() {
\t\t\t\tif closeErr := stopASMutationKafkaConsumer(); closeErr != nil {
\t\t\t\t\tlogger.Warn(
\t\t\t\t\t\t"Failed to stop AS-M06 Kafka consumer",
\t\t\t\t\t\tslog.Any(
\t\t\t\t\t\t\t"error",
\t\t\t\t\t\t\tcloseErr,
\t\t\t\t\t\t),
\t\t\t\t\t)
\t\t\t\t}
\t\t\t}()
\t\t}
\t}

\tgo func() {"""

    content = replace_once(
        content,
        old,
        new,
        name="AS-M06 consumer startup",
        already_applied_marker=(
            "stopASMutationKafkaConsumer"
        ),
    )

    CHECKOUT_FILE.write_text(
        content,
        encoding="utf-8",
    )

    print()
    print(f"Updated: {CHECKOUT_FILE}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())