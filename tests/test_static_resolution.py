from archdrift.analysis.static_resolution import (
    StaticTargetResolver,
    extract_environment_key,
)
from archdrift.model import (
    EndpointBinding,
    InteractionType,
    NodeType,
    SourcePathRule,
    SourceStaticFinding,
    StaticResolutionStatus,
)


def finding(
    *,
    path: str,
    target: str,
) -> SourceStaticFinding:
    return SourceStaticFinding(
        rule_id=(
            "archdrift.typescript.grpc-client"
        ),
        path=path,
        line=9,
        interaction=(
            InteractionType.SERVICE_CALL
        ),
        target_expression=target,
        protocol="grpc",
    )


def test_extract_environment_key_from_identifier() -> None:
    assert (
        extract_environment_key(
            "CURRENCY_ADDR"
        )
        == "CURRENCY_ADDR"
    )


def test_extract_environment_key_from_template_literal() -> None:
    assert (
        extract_environment_key(
            "`${SHIPPING_ADDR}/get-quote`"
        )
        == "SHIPPING_ADDR"
    )


def test_extract_environment_key_rejects_multiple_variables() -> None:
    assert (
        extract_environment_key(
            "`${HOST}:${PORT}`"
        )
        is None
    )


def test_static_target_resolver_resolves_service_call() -> None:
    resolver = (
        StaticTargetResolver()
    )

    result = resolver.resolve(
        findings=(
            finding(
                path=(
                    "subjects/astronomy-shop/"
                    "src/frontend/gateways/"
                    "rpc/Currency.gateway.ts"
                ),
                target=(
                    "CURRENCY_ADDR"
                ),
            ),
        ),
        source_rules=(
            SourcePathRule(
                path_prefix=(
                    "src/frontend"
                ),
                service_id=(
                    "frontend"
                ),
            ),
        ),
        bindings=(
            EndpointBinding(
                source_service_id=(
                    "frontend"
                ),
                environment_key=(
                    "CURRENCY_ADDR"
                ),
                target_service_id=(
                    "currency"
                ),
                target_type=(
                    NodeType.SERVICE
                ),
                raw_value=(
                    "currency:8080"
                ),
            ),
        ),
    )

    assert (
        result.resolved_count
        == 1
    )

    assert (
        result.unresolved_count
        == 0
    )

    resolution = (
        result.results[0]
    )

    assert (
        resolution.status
        is StaticResolutionStatus.RESOLVED
    )

    assert (
        resolution.resolved
        is not None
    )

    assert (
        resolution.resolved
        .source_service_id
        == "frontend"
    )

    assert (
        resolution.resolved
        .environment_key
        == "CURRENCY_ADDR"
    )

    assert (
        resolution.resolved
        .target_service_id
        == "currency"
    )