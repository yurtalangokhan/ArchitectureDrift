from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

WORKSPACE = (
    PROJECT_ROOT
    / "workspaces"
    / "authoring"
    / "eshop"
    / "ES-M04"
)

PAYMENT_HANDLER_FILE = (
    WORKSPACE
    / "src"
    / "PaymentProcessor"
    / "IntegrationEvents"
    / "EventHandling"
    / "OrderStatusChangedToStockConfirmedIntegrationEventHandler.cs"
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
    if not PAYMENT_HANDLER_FILE.is_file():
        raise FileNotFoundError(
            f"Payment handler not found: {PAYMENT_HANDLER_FILE}"
        )

    content = PAYMENT_HANDLER_FILE.read_text(
        encoding="utf-8-sig",
    )

    content = replace_once(
        content,
        """{
    public async Task Handle(OrderStatusChangedToStockConfirmedIntegrationEvent @event)
    {""",
        """{
    private const string ESM04IdentityAddress =
        "http://identity-api";

    private static readonly HttpClient ESM04IdentityClient =
        new()
        {
            BaseAddress = new Uri(
                ESM04IdentityAddress)
        };

    private static bool IsESM04Enabled()
    {
        return string.Equals(
            Environment.GetEnvironmentVariable(
                "ARCHDRIFT_ES_M04_TRIGGER"),
            "true",
            StringComparison.OrdinalIgnoreCase);
    }

    private async Task InvokeESM04IdentityAsync()
    {
        try
        {
            using var response =
                await ESM04IdentityClient.GetAsync(
                    "/alive");

            logger.LogInformation(
                "ES-M04 Identity mutation call completed "
                + "with status {StatusCode}",
                response.StatusCode);
        }
        catch (Exception exception)
        {
            logger.LogWarning(
                exception,
                "ES-M04 Identity mutation call failed");
        }
    }

    public async Task Handle(OrderStatusChangedToStockConfirmedIntegrationEvent @event)
    {""",
        name="ES-M04 dormant Identity API dependency",
        already_applied_marker="ESM04IdentityAddress",
    )

    content = replace_once(
        content,
        """        logger.LogInformation("Handling integration event: {IntegrationEventId} - ({@IntegrationEvent})", @event.Id, @event);

        IntegrationEvent orderPaymentIntegrationEvent;""",
        """        logger.LogInformation("Handling integration event: {IntegrationEventId} - ({@IntegrationEvent})", @event.Id, @event);

        if (IsESM04Enabled())
        {
            await InvokeESM04IdentityAsync();
        }

        IntegrationEvent orderPaymentIntegrationEvent;""",
        name="ES-M04 guarded Identity invocation",
        already_applied_marker=(
            "if (IsESM04Enabled())"
        ),
    )

    PAYMENT_HANDLER_FILE.write_text(
        content,
        encoding="utf-8-sig",
    )

    print()
    print(f"Updated: {PAYMENT_HANDLER_FILE}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())