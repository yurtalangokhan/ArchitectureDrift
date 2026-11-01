from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

WORKSPACE = (
    PROJECT_ROOT
    / "workspaces"
    / "authoring"
    / "eshop"
    / "ES-M05"
)

WEBHOOK_CLIENT_CSPROJ = (
    WORKSPACE
    / "src"
    / "WebhookClient"
    / "WebhookClient.csproj"
)

WEBHOOK_CLIENT_EXTENSIONS = (
    WORKSPACE
    / "src"
    / "WebhookClient"
    / "Extensions"
    / "Extensions.cs"
)

WEBHOOK_CLIENT_APPSETTINGS = (
    WORKSPACE
    / "src"
    / "WebhookClient"
    / "appsettings.json"
)

APPHOST_FILE = (
    WORKSPACE
    / "src"
    / "eShop.AppHost"
    / "Program.cs"
)

INTEGRATION_EVENT_FILE = (
    WORKSPACE
    / "src"
    / "WebhookClient"
    / "IntegrationEvents"
    / "ESM05OrderStatusSubscription.cs"
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


def update_project() -> None:
    content = WEBHOOK_CLIENT_CSPROJ.read_text(
        encoding="utf-8-sig",
    )

    content = replace_once(
        content,
        """  <ItemGroup>
    <ProjectReference Include="..\\eShop.ServiceDefaults\\eShop.ServiceDefaults.csproj" />
    <PackageReference Include="Asp.Versioning.Http.Client" />""",
        """  <ItemGroup>
    <ProjectReference Include="..\\eShop.ServiceDefaults\\eShop.ServiceDefaults.csproj" />
    <ProjectReference Include="..\\EventBusRabbitMQ\\EventBusRabbitMQ.csproj" />
    <PackageReference Include="Asp.Versioning.Http.Client" />""",
        name="ES-M05 EventBusRabbitMQ project reference",
        already_applied_marker=(
            "..\\EventBusRabbitMQ\\EventBusRabbitMQ.csproj"
        ),
    )

    WEBHOOK_CLIENT_CSPROJ.write_text(
        content,
        encoding="utf-8-sig",
    )


def update_extensions() -> None:
    content = WEBHOOK_CLIENT_EXTENSIONS.read_text(
        encoding="utf-8-sig",
    )

    content = replace_once(
        content,
        """using Microsoft.AspNetCore.Components.Server;

namespace eShop.WebhookClient.Extensions;""",
        """using Microsoft.AspNetCore.Components.Server;
using eShop.WebhookClient.IntegrationEvents;

namespace eShop.WebhookClient.Extensions;""",
        name="ES-M05 integration-event import",
        already_applied_marker=(
            "using eShop.WebhookClient.IntegrationEvents;"
        ),
    )

    content = replace_once(
        content,
        """    {
        builder.AddAuthenticationServices();

        // Application services""",
        """    {
        builder.AddAuthenticationServices();

        builder.AddRabbitMqEventBus("eventbus")
            .AddSubscription<
                OrderStatusChangedToSubmittedIntegrationEvent,
                ESM05OrderStatusChangedToSubmittedIntegrationEventHandler>();

        // Application services""",
        name="ES-M05 RabbitMQ subscription",
        already_applied_marker=(
            "ESM05OrderStatusChangedToSubmittedIntegrationEventHandler"
        ),
    )

    WEBHOOK_CLIENT_EXTENSIONS.write_text(
        content,
        encoding="utf-8-sig",
    )


def update_appsettings() -> None:
    content = WEBHOOK_CLIENT_APPSETTINGS.read_text(
        encoding="utf-8",
    )

    content = replace_once(
        content,
        '''  "AllowedHosts": "*",
  "WebhookClientOptions": {''',
        '''  "AllowedHosts": "*",
  "EventBus": {
    "SubscriptionClientName": "ArchitectureDrift.WebhookClient.ESM05"
  },
  "WebhookClientOptions": {''',
        name="ES-M05 RabbitMQ queue configuration",
        already_applied_marker=(
            '"ArchitectureDrift.WebhookClient.ESM05"'
        ),
    )

    WEBHOOK_CLIENT_APPSETTINGS.write_text(
        content,
        encoding="utf-8",
    )


def update_apphost() -> None:
    content = APPHOST_FILE.read_text(
        encoding="utf-8-sig",
    )

    content = replace_once(
        content,
        """var webhooksClient = builder.AddProject<Projects.WebhookClient>("webhooksclient", launchProfileName)
    .WithReference(webHooksApi)
    .WithEnvironment("IdentityUrl", identityEndpoint);""",
        """var webhooksClient = builder.AddProject<Projects.WebhookClient>("webhooksclient", launchProfileName)
    .WithReference(webHooksApi)
    .WithReference(rabbitMq).WaitFor(rabbitMq)
    .WithEnvironment("IdentityUrl", identityEndpoint);""",
        name="ES-M05 RabbitMQ connection reference",
        already_applied_marker=(
            ".WithReference(webHooksApi)\n"
            "    .WithReference(rabbitMq).WaitFor(rabbitMq)\n"
            '    .WithEnvironment("IdentityUrl", identityEndpoint);'
        ),
    )

    APPHOST_FILE.write_text(
        content,
        encoding="utf-8-sig",
    )


def create_integration_event() -> None:
    if INTEGRATION_EVENT_FILE.exists():
        print(
            "[SKIP] ES-M05 runtime event handler: "
            "already created"
        )
        return

    INTEGRATION_EVENT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    content = """using System.Diagnostics;
using eShop.EventBus.Abstractions;
using eShop.EventBus.Events;

namespace eShop.WebhookClient.IntegrationEvents;

public sealed record OrderStatusChangedToSubmittedIntegrationEvent
    : IntegrationEvent
{
    public OrderStatusChangedToSubmittedIntegrationEvent()
    {
    }
}

public sealed class ESM05OrderStatusChangedToSubmittedIntegrationEventHandler(
    ILogger<ESM05OrderStatusChangedToSubmittedIntegrationEventHandler> logger)
    : IIntegrationEventHandler<
        OrderStatusChangedToSubmittedIntegrationEvent>
{
    public Task Handle(
        OrderStatusChangedToSubmittedIntegrationEvent @event)
    {
        var activity = Activity.Current;

        if (activity is not null)
        {
            activity.SetTag(
                "messaging.system",
                "rabbitmq");

            activity.SetTag(
                "messaging.operation.type",
                "receive");

            activity.SetTag(
                "messaging.operation.name",
                "receive");

            activity.SetTag(
                "server.address",
                "eventbus");
        }

        logger.LogInformation(
            "ES-M05 observed submitted order event "
            + "{IntegrationEventId}",
            @event.Id);

        return Task.CompletedTask;
    }
}
"""

    INTEGRATION_EVENT_FILE.write_text(
        content,
        encoding="utf-8",
    )

    print(
        "[APPLY] ES-M05 runtime event handler"
    )


def main() -> int:
    required_files = (
        WEBHOOK_CLIENT_CSPROJ,
        WEBHOOK_CLIENT_EXTENSIONS,
        WEBHOOK_CLIENT_APPSETTINGS,
        APPHOST_FILE,
    )

    for path in required_files:
        if not path.is_file():
            raise FileNotFoundError(
                f"Required file not found: {path}"
            )

    update_project()
    update_extensions()
    update_appsettings()
    update_apphost()
    create_integration_event()

    print()
    print("ES-M05 authoring completed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())