var builder = DistributedApplication.CreateBuilder(args);

var redis = builder.AddRedis("redis");
var eventbus = builder.AddRabbitMQ("eventbus");
var postgres = builder.AddPostgres("postgres");

var identityApi =
    builder.AddProject<Projects.Identity_API>("identity-api");

var basketApi =
    builder.AddProject<Projects.Basket_API>("basket-api")
        .WithReference(redis)
        .WithReference(eventbus);

var catalogApi =
    builder.AddProject<Projects.Catalog_API>("catalog-api")
        .WithReference(eventbus);

var orderingApi =
    builder.AddProject<Projects.Ordering_API>("ordering-api")
        .WithReference(eventbus);

builder
    .AddProject<Projects.OrderProcessor>("order-processor")
    .WithReference(eventbus);

builder
    .AddProject<Projects.PaymentProcessor>("payment-processor")
    .WithReference(eventbus);

var webhooksApi =
    builder.AddProject<Projects.Webhooks_API>("webhooks-api")
        .WithReference(eventbus);

var webhooksClient =
    builder.AddProject<Projects.WebhookClient>("webhooksclient")
        .WithReference(webhooksApi);

var webapp =
    builder.AddProject<Projects.WebApp>("webapp")
        .WithReference(basketApi)
        .WithReference(catalogApi)
        .WithReference(orderingApi)
        .WithReference(eventbus);

builder.Build().Run();
