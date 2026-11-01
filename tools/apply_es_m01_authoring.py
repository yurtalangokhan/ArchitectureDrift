from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

WORKSPACE = (
    PROJECT_ROOT
    / "workspaces"
    / "authoring"
    / "eshop"
    / "ES-M01"
)

BASKET_SERVICE_FILE = (
    WORKSPACE
    / "src"
    / "Basket.API"
    / "Grpc"
    / "BasketService.cs"
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
    if not BASKET_SERVICE_FILE.is_file():
        raise FileNotFoundError(
            f"BasketService.cs not found: {BASKET_SERVICE_FILE}"
        )

    content = BASKET_SERVICE_FILE.read_text(
        encoding="utf-8-sig",
    )

    content = replace_once(
        content,
        """using System.Diagnostics.CodeAnalysis;
using eShop.Basket.API.Repositories;""",
        """using System.Diagnostics.CodeAnalysis;
using System.Net;
using System.Net.Sockets;
using eShop.Basket.API.Repositories;""",
        name="ES-M01 network imports",
        already_applied_marker="using System.Net.Sockets;",
    )

    content = replace_once(
        content,
        """{
    [AllowAnonymous]
    public override async Task<CustomerBasketResponse> GetBasket""",
        """{
    private const int ESM01CatalogPort = 5222;

    private static readonly HttpClient ESM01CatalogClient =
        CreateESM01CatalogClient();

    private static HttpClient CreateESM01CatalogClient()
    {
        var handler = new SocketsHttpHandler
        {
            ConnectCallback = static async (
                _,
                cancellationToken) =>
            {
                var socket = new Socket(
                    SocketType.Stream,
                    ProtocolType.Tcp);

                try
                {
                    await socket.ConnectAsync(
                        IPAddress.Loopback,
                        ESM01CatalogPort,
                        cancellationToken);

                    return new NetworkStream(
                        socket,
                        ownsSocket: true);
                }
                catch
                {
                    socket.Dispose();
                    throw;
                }
            }
        };

        return new HttpClient(handler)
        {
            BaseAddress = new Uri(
                "http://catalog-api")
        };
    }

    private async Task InvokeESM01CatalogAsync(
        CancellationToken cancellationToken)
    {
        try
        {
            using var response =
                await ESM01CatalogClient.GetAsync(
                    "/alive",
                    cancellationToken);

            response.EnsureSuccessStatusCode();
        }
        catch (Exception exception)
        {
            logger.LogWarning(
                exception,
                "ES-M01 catalog mutation call failed");
        }
    }

    [AllowAnonymous]
    public override async Task<CustomerBasketResponse> GetBasket""",
        name="ES-M01 runtime catalog client",
        already_applied_marker="ESM01CatalogClient",
    )

    content = replace_once(
        content,
        """        if (logger.IsEnabled(LogLevel.Debug))
        {
            logger.LogDebug("Begin GetBasketById call from method {Method} for basket id {Id}", context.Method, userId);
        }

        var data = await repository.GetBasketAsync(userId);""",
        """        if (logger.IsEnabled(LogLevel.Debug))
        {
            logger.LogDebug("Begin GetBasketById call from method {Method} for basket id {Id}", context.Method, userId);
        }

        await InvokeESM01CatalogAsync(
            context.CancellationToken);

        var data = await repository.GetBasketAsync(userId);""",
        name="ES-M01 GetBasket invocation",
        already_applied_marker=(
            "await InvokeESM01CatalogAsync("
        ),
    )

    BASKET_SERVICE_FILE.write_text(
        content,
        encoding="utf-8-sig",
    )

    print()
    print(f"Updated: {BASKET_SERVICE_FILE}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())