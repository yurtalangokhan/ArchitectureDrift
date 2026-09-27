from pathlib import Path

import yaml

PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)


def test_astronomy_shop_semgrep_rules_exist() -> None:
    rules = (
        PROJECT_ROOT
        / "rules"
        / "semgrep"
        / "astronomy-shop.yaml"
    )

    assert rules.is_file()


def test_astronomy_shop_semgrep_rule_ids_are_stable() -> None:
    rules = (
        PROJECT_ROOT
        / "rules"
        / "semgrep"
        / "astronomy-shop.yaml"
    )

    document = yaml.safe_load(
        rules.read_text(
            encoding="utf-8",
        )
    )

    rule_ids = {
        rule["id"]
        for rule in document["rules"]
    }

    assert rule_ids == {
        "archdrift.typescript.fetch",
        "archdrift.typescript.grpc-client",
    }