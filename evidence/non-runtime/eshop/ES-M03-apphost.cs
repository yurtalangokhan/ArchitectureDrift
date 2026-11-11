var builder = DistributedApplication.CreateBuilder(args);

var catalog_api =
    builder.AddProject<Projects.Target>("catalog-api");

var ordering_api =
    builder.AddProject<Projects.Source>("ordering-api")
        .WithReference(catalog_api);

builder.Build().Run();
