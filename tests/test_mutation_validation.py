from pathlib import Path

import pytest

from archdrift.experiments.mutation_validation import (
    extract_patch_touched_files,
)
from archdrift.model import (
    load_mutation_implementation_manifest,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


ESHOP_EXPECTED_PATCH_FILES = {
    "ES-M01": {
        "src/Basket.API/Grpc/BasketService.cs",
    },
    "ES-M02": {
        "src/eShop.AppHost/Program.cs",
    },
    "ES-M03": {
        "src/Ordering.API/Apis/OrderServices.cs",
        "src/Ordering.API/Apis/OrdersApi.cs",
        "src/Ordering.API/Extensions/Extensions.cs",
        "src/eShop.AppHost/Program.cs",
    },
    "ES-M04": {
        (
            "src/PaymentProcessor/IntegrationEvents/"
            "EventHandling/"
            "OrderStatusChangedToStockConfirmedIntegrationEventHandler.cs"
        ),
    },
    "ES-M05": {
        "src/WebhookClient/Extensions/Extensions.cs",
        ("src/WebhookClient/IntegrationEvents/" "ESM05OrderStatusSubscription.cs"),
        "src/WebhookClient/WebhookClient.csproj",
        "src/WebhookClient/appsettings.json",
        "src/eShop.AppHost/Program.cs",
    },
}

ASTRONOMY_EXPECTED_PATCH_FILES = {
    "AS-M01": {
        "src/checkout/main.go",
    },
    "AS-M02": {
        "compose.yaml",
        "src/payment/index.js",
    },
    "AS-M03": {
        "compose.yaml",
        "src/frontend/gateways/rpc/Payment.gateway.ts",
        "src/frontend/pages/api/checkout.ts",
    },
    "AS-M04": {
        "src/cart/src/services/CartService.cs",
    },
    "AS-M05": {
        "src/frontend/package-lock.json",
        "src/frontend/package.json",
        "src/frontend/pages/api/checkout.ts",
        "src/frontend/services/ASMutationKafka.service.ts",
    },
    "AS-M06": {
        "src/checkout/main.go",
    },
}

TEASTORE_EXPECTED_PATCH_FILES = {
    "TS-M01": {
        (
            "services/tools.descartes.teastore.auth/"
            "src/main/java/tools/descartes/teastore/"
            "auth/rest/AuthUserActionsRest.java"
        ),
    },
    "TS-M02": {
        "examples/docker/docker-compose_default.yaml",
        (
            "services/tools.descartes.teastore.auth/"
            "src/main/java/tools/descartes/teastore/"
            "auth/rest/AuthUserActionsRest.java"
        ),
    },
    "TS-M03": {
        "examples/docker/docker-compose_default.yaml",
        (
            "services/tools.descartes.teastore.recommender/"
            "src/main/java/tools/descartes/teastore/"
            "recommender/rest/RecommendEndpoint.java"
        ),
    },
    "TS-M04": {
        (
            "services/tools.descartes.teastore.image/"
            "src/main/java/tools/descartes/teastore/"
            "image/rest/ImageProviderEndpoint.java"
        ),
    },
    "TS-M05": {
        (
            "services/tools.descartes.teastore.persistence/"
            "src/main/java/tools/descartes/teastore/"
            "persistence/rest/UserEndpoint.java"
        ),
    },
}

EXPECTED_PATCH_FILES = {
    **ASTRONOMY_EXPECTED_PATCH_FILES,
    **ESHOP_EXPECTED_PATCH_FILES,
    **TEASTORE_EXPECTED_PATCH_FILES,
}


@pytest.mark.parametrize(
    (
        "mutation_id",
        "expected_files",
    ),
    sorted(EXPECTED_PATCH_FILES.items()),
)
def test_astronomy_real_mutation_patch_scope(
    mutation_id: str,
    expected_files: set[str],
) -> None:
    manifest = load_mutation_implementation_manifest(
        PROJECT_ROOT / "mutations" / "implementation-manifest.yaml"
    )

    implementation = manifest.require(mutation_id)

    patch = PROJECT_ROOT / implementation.patch

    assert patch.is_file()

    assert patch.stat().st_size > 0

    assert set(extract_patch_touched_files(patch)) == expected_files
