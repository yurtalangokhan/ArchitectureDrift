from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

WORKSPACE = (
    PROJECT_ROOT
    / "workspaces"
    / "authoring"
    / "astronomy-shop"
    / "AS-M04"
)

CART_SERVICE_FILE = (
    WORKSPACE
    / "src"
    / "cart"
    / "src"
    / "services"
    / "CartService.cs"
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
    if not CART_SERVICE_FILE.is_file():
        raise FileNotFoundError(
            f"CartService.cs not found: {CART_SERVICE_FILE}"
        )

    content = CART_SERVICE_FILE.read_text(
        encoding="utf-8",
    )

    # --------------------------------------------------------------
    # A. gRPC client dependency
    # --------------------------------------------------------------

    content = replace_once(
        content,
        """using Grpc.Core;
using cart.cartstore;""",
        """using Grpc.Core;
using Grpc.Net.Client;
using cart.cartstore;""",
        name="Grpc.Net.Client import",
        already_applied_marker="using Grpc.Net.Client;",
    )

    # --------------------------------------------------------------
    # B. Hard-coded dormant architecture dependency
    # --------------------------------------------------------------

    content = replace_once(
        content,
        """    private static readonly Empty Empty = new();
    private readonly ICartStore _badCartStore;""",
        """    private static readonly Empty Empty = new();

    private const string ASMutationRecommendationAddress =
        "http://recommendation:9001";

    private static readonly GrpcChannel ASMutationRecommendationChannel =
        GrpcChannel.ForAddress(ASMutationRecommendationAddress);

    private static readonly RecommendationService.RecommendationServiceClient
        ASMutationRecommendationClient =
            new(ASMutationRecommendationChannel);

    private readonly ICartStore _badCartStore;""",
        name="AS-M04 recommendation dependency",
        already_applied_marker=(
            "ASMutationRecommendationAddress"
        ),
    )

    # --------------------------------------------------------------
    # C. Dormant invocation implementation
    # --------------------------------------------------------------

    content = replace_once(
        content,
        """    public override async Task<Cart> GetCart(GetCartRequest request, ServerCallContext context)
    {""",
        """    private static bool IsASMutationEnabled(
        ServerCallContext context)
    {
        foreach (var entry in context.RequestHeaders)
        {
            if (
                entry.Key == "x-archdrift-as-m04"
                && string.Equals(
                    entry.Value,
                    "true",
                    StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }

        return false;
    }

    private static async Task InvokeASMutationRecommendation(
        string userId)
    {
        await ASMutationRecommendationClient.ListRecommendationsAsync(
            new ListRecommendationsRequest
            {
                UserId = userId
            });
    }

    public override async Task<Cart> GetCart(GetCartRequest request, ServerCallContext context)
    {""",
        name="AS-M04 dormant invocation implementation",
        already_applied_marker=(
            "InvokeASMutationRecommendation("
        ),
    )

    # --------------------------------------------------------------
    # D. Invocation point
    # --------------------------------------------------------------

    content = replace_once(
        content,
        """        activity?.SetTag("user.id", request.UserId);
        activity?.AddEvent(new("Fetch cart"));

        try
        {
            var cart = await _cartStore.GetCartAsync(request.UserId);""",
        """        activity?.SetTag("user.id", request.UserId);
        activity?.AddEvent(new("Fetch cart"));

        if (IsASMutationEnabled(context))
        {
            await InvokeASMutationRecommendation(request.UserId);
        }

        try
        {
            var cart = await _cartStore.GetCartAsync(request.UserId);""",
        name="AS-M04 guarded runtime invocation",
        already_applied_marker=(
            "if (IsASMutationEnabled(context))"
        ),
    )

    CART_SERVICE_FILE.write_text(
        content,
        encoding="utf-8",
    )

    print()
    print(f"Updated: {CART_SERVICE_FILE}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())