from archdrift.analysis.static_observation import (
    static_interactions_to_observations,
)
from archdrift.model import (
    InteractionType,
    NodeType,
    ResolvedStaticInteraction,
    SourceStaticFinding,
    StaticTargetResolutionBasis,
)


def test_static_interaction_becomes_normalized_relation_observation() -> None:
    interaction = ResolvedStaticInteraction(
        finding=SourceStaticFinding(
            rule_id=("archdrift.typescript.grpc-client"),
            path=("src/frontend/gateways/" "rpc/Currency.gateway.ts"),
            line=9,
            interaction=(InteractionType.SERVICE_CALL),
            target_expression=("CURRENCY_ADDR"),
            protocol="grpc",
        ),
        source_service_id="frontend",
        source_type=NodeType.SERVICE,
        resolution_basis=(StaticTargetResolutionBasis.CONFIGURATION_BINDING),
        environment_key="CURRENCY_ADDR",
        target_service_id="currency",
        target_type=NodeType.SERVICE,
    )

    observations = static_interactions_to_observations((interaction,))

    assert len(observations) == 1

    observation = observations[0]

    assert observation.source.id == "frontend"

    assert observation.target.id == "currency"

    assert observation.interaction is InteractionType.SERVICE_CALL

    assert observation.protocol == "grpc"

    assert len(observation.evidence) == 1

    evidence = observation.evidence[0]

    assert evidence.artifact == ("src/frontend/gateways/" "rpc/Currency.gateway.ts")

    assert "CURRENCY_ADDR" in evidence.locator

    assert (
    observation.evidence[0].locator
    == (
        "line:9;"
        "rule:archdrift.typescript.grpc-client;"
        "resolution:CONFIGURATION_BINDING;"
        "env:CURRENCY_ADDR"
    )
)
