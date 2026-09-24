from pathlib import Path

from archdrift.experiments import run_case
from archdrift.model import (
    EvidenceChannel,
    ReconstructionMode,
    RelationType,
)


def test_as_m01_end_to_end() -> None:
    project_root = Path(__file__).resolve().parents[1]

    result = run_case(
        project_root=project_root,
        case_file=("cases/astronomy-shop/AS-M01.yaml"),
    )

    # -------------------------------------------------------------------------
    # Ground truth
    # -------------------------------------------------------------------------

    expected_relation = (
        "checkout",
        RelationType.CALLS,
        "recommendation",
    )

    assert result.mutation_id == "AS-M01"

    assert result.mutation_delta.added_relation_identities == frozenset(
        {
            expected_relation,
        }
    )

    assert result.expected_violated_contracts == ("AS-C001",)

    # -------------------------------------------------------------------------
    # Ground-truth conformance
    # -------------------------------------------------------------------------

    assert result.baseline_conformance.violated_contract_ids == frozenset()

    assert result.mutant_conformance.violated_contract_ids == frozenset(
        {
            "AS-C001",
        }
    )

    # -------------------------------------------------------------------------
    # Experimental views
    # -------------------------------------------------------------------------

    assert (
        result.views.non_runtime.graph.metadata.reconstruction_mode
        is ReconstructionMode.NON_RUNTIME
    )

    assert (
        result.views.runtime.graph.metadata.reconstruction_mode
        is ReconstructionMode.RUNTIME
    )

    assert (
        result.views.fused.graph.metadata.reconstruction_mode
        is ReconstructionMode.FUSED
    )

    # -------------------------------------------------------------------------
    # Non-Runtime
    #
    # Both nodes are known, but the unexpected connector is not visible.
    # -------------------------------------------------------------------------

    assert expected_relation not in (result.views.non_runtime.graph.relation_identities)

    assert result.non_runtime_conformance.violated_contract_ids == frozenset()

    assert result.non_runtime_detected_expected_violation is False

    # -------------------------------------------------------------------------
    # Runtime
    # -------------------------------------------------------------------------

    assert expected_relation in (result.views.runtime.graph.relation_identities)

    assert result.runtime_conformance.violated_contract_ids == frozenset(
        {
            "AS-C001",
        }
    )

    assert result.runtime_detected_expected_violation is True

    # -------------------------------------------------------------------------
    # Fused
    # -------------------------------------------------------------------------

    assert expected_relation in (result.views.fused.graph.relation_identities)

    assert result.fused_conformance.violated_contract_ids == frozenset(
        {
            "AS-C001",
        }
    )

    assert result.fused_detected_expected_violation is True

    # -------------------------------------------------------------------------
    # Runtime provenance
    # -------------------------------------------------------------------------

    support = result.views.runtime.get_relation_support(expected_relation)

    assert support is not None

    assert support.channels == (EvidenceChannel.RUNTIME,)

    assert support.protocols == ("grpc",)


def test_as_m01_experimental_metrics() -> None:
    project_root = Path(__file__).resolve().parents[1]

    result = run_case(
        project_root=project_root,
        case_file=("cases/astronomy-shop/AS-M01.yaml"),
    )

    # -------------------------------------------------------------------------
    # Structural mutation detection
    # -------------------------------------------------------------------------

    non_runtime = result.metrics.non_runtime.structural.added_relations

    assert non_runtime.true_positive == 0
    assert non_runtime.false_positive == 0
    assert non_runtime.false_negative == 1

    assert non_runtime.recall == 0.0

    runtime = result.metrics.runtime.structural.added_relations

    assert runtime.true_positive == 1
    assert runtime.false_positive == 0
    assert runtime.false_negative == 0

    assert runtime.precision == 1.0
    assert runtime.recall == 1.0
    assert runtime.f1 == 1.0

    fused = result.metrics.fused.structural.added_relations

    assert fused.true_positive == 1
    assert fused.false_positive == 0
    assert fused.false_negative == 0

    assert fused.precision == 1.0
    assert fused.recall == 1.0
    assert fused.f1 == 1.0

    # -------------------------------------------------------------------------
    # Contract-violation detection
    # -------------------------------------------------------------------------

    non_runtime_contract = result.metrics.non_runtime.contract_violations

    assert non_runtime_contract.true_positive == 0

    assert non_runtime_contract.false_negative == 1

    assert non_runtime_contract.recall == 0.0

    runtime_contract = result.metrics.runtime.contract_violations

    assert runtime_contract.true_positive == 1
    assert runtime_contract.false_negative == 0
    assert runtime_contract.precision == 1.0
    assert runtime_contract.recall == 1.0
    assert runtime_contract.f1 == 1.0

    fused_contract = result.metrics.fused.contract_violations

    assert fused_contract.true_positive == 1
    assert fused_contract.false_negative == 0
    assert fused_contract.precision == 1.0
    assert fused_contract.recall == 1.0
    assert fused_contract.f1 == 1.0
