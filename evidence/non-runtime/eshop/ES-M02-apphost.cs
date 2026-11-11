var builder = DistributedApplication.CreateBuilder(args);

var webhooks_api =
    builder.AddProject<Projects.Target>("webhooks-api");

var webapp =
    builder.AddProject<Projects.Source>("webapp")
        .WithReference(webhooks_api);

builder.Build().Run();
