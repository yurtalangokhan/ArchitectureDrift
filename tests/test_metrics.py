from archdrift.analysis import (
    ConformanceReport,
    ConformanceStatus,
    ContractEvaluation,
    compute_set_detection_metrics,
    evaluate_contract_violation_detection,
    evaluate_structural_detection,
)
from archdrift.model import (
    ArchitectureGraph,
    ArchitectureNode,
    ArchitectureRelation,
    ExpectedGraphDelta,
    GraphMetadata,
    GraphRole,
    NodeType,
    ReconstructionMode,
    RelationType,
    ContractType,
    GraphMetadata,
    GraphRole,
)

# =============================================================================
# Generic Set Metrics
# =============================================================================


def test_perfect_set_detection() -> None:
    metrics = compute_set_detection_metrics(
        expected={
            "A",
            "B",
        },
        predicted={
            "A",
            "B",
        },
    )

    assert metrics.true_positive == 2
    assert metrics.false_positive == 0
    assert metrics.false_negative == 0

    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.f1 == 1.0


def test_set_detection_false_positive_and_false_negative() -> None:
    metrics = compute_set_detection_metrics(
        expected={
            "A",
            "B",
        },
        predicted={
            "A",
            "C",
        },
    )

    assert metrics.true_positive == 1
    assert metrics.false_positive == 1
    assert metrics.false_negative == 1

    assert metrics.precision == 0.5
    assert metrics.recall == 0.5
    assert metrics.f1 == 0.5


def test_precision_is_undefined_when_nothing_predicted() -> None:
    metrics = compute_set_detection_metrics(
        expected={
            "A",
        },
        predicted=set(),
    )

    assert metrics.precision is None
    assert metrics.recall == 0.0
    assert metrics.f1 is None


def test_recall_is_undefined_when_no_ground_truth_positive() -> None:
    metrics = compute_set_detection_metrics(
        expected=set(),
        predicted={
            "A",
        },
    )

    assert metrics.precision == 0.0
    assert metrics.recall is None
    assert metrics.f1 is None


# =============================================================================
# Contract Metrics
# =============================================================================


def report_with(
    *evaluations: ContractEvaluation,
) -> ConformanceReport:
    return ConformanceReport(
        graph=GraphMetadata(
            system_id="test-system",
            role=GraphRole.BASELINE,
        ),
        contract_system_id="test-system",
        evaluations=tuple(evaluations),
    )


def evaluation(
    contract_id: str,
    status: ConformanceStatus,
) -> ContractEvaluation:
    return ContractEvaluation(
        contract_id=contract_id,
        contract_type=ContractType.FORBIDDEN_RELATION,
        status=status,
        message="test",
    )


def test_contract_violation_confusion_matrix() -> None:
    report = report_with(
        evaluation(
            "C001",
            ConformanceStatus.VIOLATED,
        ),
        evaluation(
            "C002",
            ConformanceStatus.SATISFIED,
        ),
        evaluation(
            "C003",
            ConformanceStatus.VIOLATED,
        ),
    )

    metrics = evaluate_contract_violation_detection(
        report=report,
        expected_violations={
            "C001",
            "C002",
        },
    )

    assert metrics.true_positive == 1
    assert metrics.false_positive == 1
    assert metrics.false_negative == 1
    assert metrics.true_negative == 0

    assert metrics.precision == 0.5
    assert metrics.recall == 0.5
    assert metrics.f1 == 0.5


def test_not_evaluable_expected_violation_is_false_negative() -> None:
    report = report_with(
        evaluation(
            "C001",
            ConformanceStatus.NOT_EVALUABLE,
        ),
    )

    metrics = evaluate_contract_violation_detection(
        report=report,
        expected_violations={
            "C001",
        },
    )

    assert metrics.true_positive == 0
    assert metrics.false_negative == 1

    assert metrics.not_evaluable_positive == 1

    assert metrics.recall == 0.0
    assert metrics.evaluability_rate == 0.0


def test_not_evaluable_negative_is_not_true_negative() -> None:
    report = report_with(
        evaluation(
            "C001",
            ConformanceStatus.NOT_EVALUABLE,
        ),
    )

    metrics = evaluate_contract_violation_detection(
        report=report,
        expected_violations=set(),
    )

    assert metrics.true_negative == 0

    assert metrics.not_evaluable_negative == 1

    assert metrics.evaluability_rate == 0.0


def test_perfect_contract_detection() -> None:
    report = report_with(
        evaluation(
            "C001",
            ConformanceStatus.VIOLATED,
        ),
        evaluation(
            "C002",
            ConformanceStatus.SATISFIED,
        ),
    )

    metrics = evaluate_contract_violation_detection(
        report=report,
        expected_violations={
            "C001",
        },
    )

    assert metrics.true_positive == 1
    assert metrics.true_negative == 1
    assert metrics.false_positive == 0
    assert metrics.false_negative == 0

    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.f1 == 1.0
    assert metrics.evaluability_rate == 1.0


def test_missing_baseline_relation_is_not_inferred_as_removal() -> None:
    relation = ArchitectureRelation(
        source="a",
        relation=RelationType.CALLS,
        target="b",
    )

    baseline = ArchitectureGraph(
        metadata=GraphMetadata(
            system_id="system",
            role=GraphRole.BASELINE,
        ),
        nodes=(
            ArchitectureNode(
                id="a",
                type=NodeType.SERVICE,
            ),
            ArchitectureNode(
                id="b",
                type=NodeType.SERVICE,
            ),
        ),
        relations=(relation,),
    )

    observed = ArchitectureGraph(
        metadata=GraphMetadata(
            system_id="system",
            role=GraphRole.OBSERVED,
            reconstruction_mode=(ReconstructionMode.RUNTIME),
        ),
        nodes=baseline.nodes,
        relations=(),
    )

    metrics = evaluate_structural_detection(
        baseline=baseline,
        observed=observed,
        expected=ExpectedGraphDelta(),
    )

    # Diagnostic graph delta can see the missing relation.
    assert metrics.raw_graph_delta.removed_relation_identities == frozenset(
        {
            relation.identity,
        }
    )

    # But open-world detection must not claim a removal.
    assert metrics.removed_relations.true_positive == 0
    assert metrics.removed_relations.false_positive == 0
    assert metrics.removed_relations.false_negative == 0
