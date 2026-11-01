from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

WORKSPACE = (
    PROJECT_ROOT
    / "workspaces"
    / "authoring"
    / "eshop"
    / "ES-M03"
)

APPHOST_FILE = (
    WORKSPACE
    / "src"
    / "eShop.AppHost"
    / "Program.cs"
)

ORDERING_EXTENSIONS_FILE = (
    WORKSPACE
    / "src"
    / "Ordering.API"
    / "Extensions"
    / "Extensions.cs"
)

ORDER_SERVICES_FILE = (
    WORKSPACE
    / "src"
    / "Ordering.API"
    / "Apis"
    / "OrderServices.cs"
)

ORDERS_API_FILE = (
    WORKSPACE
    / "src"
    / "Ordering.API"
    / "Apis"
    / "OrdersApi.cs"
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


def update_apphost() -> None:
    content = APPHOST_FILE.read_text(
        encoding="utf-8-sig",
    )

    content = replace_once(
        content,
        """var orderingApi = builder.AddProject<Projects.Ordering_API>("ordering-api")
    .WithReference(rabbitMq).WaitFor(rabbitMq)
    .WithReference(orderDb).WaitFor(orderDb)
    .WithHttpHealthCheck("/health")""",
        """var orderingApi = builder.AddProject<Projects.Ordering_API>("ordering-api")
    .WithReference(rabbitMq).WaitFor(rabbitMq)
    .WithReference(orderDb).WaitFor(orderDb)
    .WithReference(catalogApi)
    .WithHttpHealthCheck("/health")""",
        name="ES-M03 Aspire catalog reference",
        already_applied_marker=(
            ".WithReference(orderDb).WaitFor(orderDb)\n"
            "    .WithReference(catalogApi)\n"
            '    .WithHttpHealthCheck("/health")'
        ),
    )

    APPHOST_FILE.write_text(
        content,
        encoding="utf-8-sig",
    )


def update_ordering_extensions() -> None:
    content = ORDERING_EXTENSIONS_FILE.read_text(
        encoding="utf-8-sig",
    )

    content = replace_once(
        content,
        """        services.AddHttpContextAccessor();
        services.AddTransient<IIdentityService, IdentityService>();

        // Configure mediatR""",
        """        services.AddHttpContextAccessor();
        services.AddTransient<IIdentityService, IdentityService>();

        services.AddHttpClient(
            "ESM03Catalog",
            client =>
            {
                client.BaseAddress = new Uri(
                    "https+http://catalog-api");
            });

        // Configure mediatR""",
        name="ES-M03 Catalog HttpClient registration",
        already_applied_marker='"ESM03Catalog"',
    )

    ORDERING_EXTENSIONS_FILE.write_text(
        content,
        encoding="utf-8-sig",
    )


def update_order_services() -> None:
    content = ORDER_SERVICES_FILE.read_text(
        encoding="utf-8-sig",
    )

    content = replace_once(
        content,
        """public class OrderServices(
    IMediator mediator,
    IOrderQueries queries,
    IIdentityService identityService,
    ILogger<OrderServices> logger)""",
        """public class OrderServices(
    IMediator mediator,
    IOrderQueries queries,
    IIdentityService identityService,
    IHttpClientFactory httpClientFactory,
    ILogger<OrderServices> logger)""",
        name="ES-M03 IHttpClientFactory injection",
        already_applied_marker="IHttpClientFactory httpClientFactory",
    )

    content = replace_once(
        content,
        """    public IOrderQueries Queries { get; } = queries;
    public IIdentityService IdentityService { get; } = identityService;
}""",
        """    public IOrderQueries Queries { get; } = queries;
    public IIdentityService IdentityService { get; } = identityService;
    public IHttpClientFactory HttpClientFactory { get; } =
        httpClientFactory;
}""",
        name="ES-M03 HttpClientFactory property",
        already_applied_marker=(
            "public IHttpClientFactory HttpClientFactory"
        ),
    )

    ORDER_SERVICES_FILE.write_text(
        content,
        encoding="utf-8-sig",
    )


def update_orders_api() -> None:
    content = ORDERS_API_FILE.read_text(
        encoding="utf-8-sig",
    )

    old = """        if (requestId == Guid.Empty)
        {
            services.Logger.LogWarning("Invalid IntegrationEvent - RequestId is missing - {@IntegrationEvent}", request);
            return TypedResults.BadRequest("RequestId is missing.");
        }

        using (services.Logger.BeginScope"""

    new = """        if (requestId == Guid.Empty)
        {
            services.Logger.LogWarning("Invalid IntegrationEvent - RequestId is missing - {@IntegrationEvent}", request);
            return TypedResults.BadRequest("RequestId is missing.");
        }

        try
        {
            var catalogClient =
                services.HttpClientFactory.CreateClient(
                    "ESM03Catalog");

            using var catalogResponse =
                await catalogClient.GetAsync(
                    "/api/catalog/items/1?api-version=2.0");

            services.Logger.LogInformation(
                "ES-M03 Catalog mutation call completed "
                + "with status {StatusCode}",
                catalogResponse.StatusCode);
        }
        catch (Exception exception)
        {
            services.Logger.LogWarning(
                exception,
                "ES-M03 Catalog mutation call failed");
        }

        using (services.Logger.BeginScope"""

    content = replace_once(
        content,
        old,
        new,
        name="ES-M03 runtime Catalog invocation",
        already_applied_marker=(
            "ES-M03 Catalog mutation call completed"
        ),
    )

    ORDERS_API_FILE.write_text(
        content,
        encoding="utf-8-sig",
    )


def main() -> int:
    required_files = (
        APPHOST_FILE,
        ORDERING_EXTENSIONS_FILE,
        ORDER_SERVICES_FILE,
        ORDERS_API_FILE,
    )

    for path in required_files:
        if not path.is_file():
            raise FileNotFoundError(
                f"Required file not found: {path}"
            )

    update_apphost()
    update_ordering_extensions()
    update_order_services()
    update_orders_api()

    print()
    print("ES-M03 authoring completed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())