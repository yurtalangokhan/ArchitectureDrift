from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

TARGET = (
    PROJECT_ROOT
    / "workspaces"
    / "authoring"
    / "astronomy-shop"
    / "AS-M01"
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
    if not TARGET.is_file():
        raise FileNotFoundError(
            f"AS-M01 authoring file not found: {TARGET}"
        )

    content = TARGET.read_text(
        encoding="utf-8",
    )

    # ------------------------------------------------------------------
    # A. Mutation endpoint constant
    # ------------------------------------------------------------------

    content = replace_once(
        content,
        "const emailRequestTimeout = time.Second",
        """const (
\temailRequestTimeout            = time.Second
\tasM01RecommendationServiceAddr = "recommendation:9001"
)""",
        name="recommendation endpoint constant",
        already_applied_marker=(
            "asM01RecommendationServiceAddr"
        ),
    )

    # ------------------------------------------------------------------
    # B. Recommendation client field
    # ------------------------------------------------------------------

    content = replace_once(
        content,
        """\tKafkaProducerClient     sarama.AsyncProducer
\tshippingSvcClient       pb.ShippingServiceClient
\tproductCatalogSvcClient pb.ProductCatalogServiceClient
\tcartSvcClient           pb.CartServiceClient
\tcurrencySvcClient       pb.CurrencyServiceClient
\temailSvcClient          pb.EmailServiceClient
\tpaymentSvcClient        pb.PaymentServiceClient
\thttpClient              *http.Client""",
        """\tKafkaProducerClient     sarama.AsyncProducer
\tshippingSvcClient       pb.ShippingServiceClient
\tproductCatalogSvcClient pb.ProductCatalogServiceClient
\tcartSvcClient           pb.CartServiceClient
\tcurrencySvcClient       pb.CurrencyServiceClient
\temailSvcClient          pb.EmailServiceClient
\tpaymentSvcClient        pb.PaymentServiceClient
\trecommendationSvcClient pb.RecommendationServiceClient
\thttpClient              *http.Client""",
        name="recommendation client field",
        already_applied_marker=(
            "recommendationSvcClient pb.RecommendationServiceClient"
        ),
    )

    # ------------------------------------------------------------------
    # C. Recommendation client initialization
    # ------------------------------------------------------------------

    content = replace_once(
        content,
        """\tmustMapEnv(&svc.paymentSvcAddr, "PAYMENT_ADDR")
\tc = mustCreateClient(svc.paymentSvcAddr)
\tsvc.paymentSvcClient = pb.NewPaymentServiceClient(c)
\tdefer c.Close()

\tsvc.kafkaBrokerSvcAddr = os.Getenv("KAFKA_ADDR")""",
        """\tmustMapEnv(&svc.paymentSvcAddr, "PAYMENT_ADDR")
\tc = mustCreateClient(svc.paymentSvcAddr)
\tsvc.paymentSvcClient = pb.NewPaymentServiceClient(c)
\tdefer c.Close()

\tc = mustCreateClient(asM01RecommendationServiceAddr)
\tsvc.recommendationSvcClient = pb.NewRecommendationServiceClient(c)
\tdefer c.Close()

\tsvc.kafkaBrokerSvcAddr = os.Getenv("KAFKA_ADDR")""",
        name="recommendation client initialization",
        already_applied_marker=(
            "pb.NewRecommendationServiceClient(c)"
        ),
    )

    # ------------------------------------------------------------------
    # D. Invoke mutation in PlaceOrder
    # ------------------------------------------------------------------

    content = replace_once(
        content,
        """\tprep, err := cs.prepareOrderItemsAndShippingQuoteFromCart(ctx, req.UserId, req.UserCurrency, req.Address)
\tif err != nil {
\t\treturn nil, status.Error(codes.Internal, err.Error())
\t}
\tspan.AddEvent("prepared")

\ttotal := &pb.Money{""",
        """\tprep, err := cs.prepareOrderItemsAndShippingQuoteFromCart(ctx, req.UserId, req.UserCurrency, req.Address)
\tif err != nil {
\t\treturn nil, status.Error(codes.Internal, err.Error())
\t}
\tspan.AddEvent("prepared")

\tcs.invokeASMutationRecommendation(
\t\tctx,
\t\treq.UserId,
\t\tprep.cartItems,
\t)

\ttotal := &pb.Money{""",
        name="PlaceOrder mutation invocation",
        already_applied_marker=(
            "cs.invokeASMutationRecommendation("
        ),
    )

    # ------------------------------------------------------------------
    # E. Mutation implementation method
    # ------------------------------------------------------------------

    content = replace_once(
        content,
        """func (cs *checkout) quoteShipping(ctx context.Context, address *pb.Address, items []*pb.CartItem) (*pb.Money, error) {""",
        """func (cs *checkout) invokeASMutationRecommendation(
\tctx context.Context,
\tuserID string,
\titems []*pb.CartItem,
) {
\tproductIDs := make([]string, 0, len(items))

\tfor _, item := range items {
\t\tproductIDs = append(
\t\t\tproductIDs,
\t\t\titem.GetProductId(),
\t\t)
\t}

\t_, err := cs.recommendationSvcClient.ListRecommendations(
\t\tctx,
\t\t&pb.ListRecommendationsRequest{
\t\t\tUserId:     userID,
\t\t\tProductIds: productIDs,
\t\t},
\t)
\tif err != nil {
\t\tlogger.Warn(
\t\t\t"AS-M01 recommendation mutation call failed",
\t\t\tslog.Any(
\t\t\t\t"error",
\t\t\t\terr,
\t\t\t),
\t\t)
\t}
}

func (cs *checkout) quoteShipping(ctx context.Context, address *pb.Address, items []*pb.CartItem) (*pb.Money, error) {""",
        name="mutation method",
        already_applied_marker=(
            "func (cs *checkout) invokeASMutationRecommendation("
        ),
    )

    TARGET.write_text(
        content,
        encoding="utf-8",
    )

    print()
    print(f"Updated: {TARGET}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())