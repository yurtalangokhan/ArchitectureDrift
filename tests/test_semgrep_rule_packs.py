from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_rules(
    rule_file: Path,
) -> list[dict[str, Any]]:
    document = yaml.safe_load(
        rule_file.read_text(
            encoding="utf-8",
        )
    )

    if not isinstance(
        document,
        dict,
    ):
        raise AssertionError(
            "Semgrep rule pack must contain " "a YAML mapping: " f"{rule_file}"
        )

    raw_rules = document.get("rules")

    if not isinstance(
        raw_rules,
        list,
    ):
        raise AssertionError(
            "Semgrep rule pack must contain " "a 'rules' list: " f"{rule_file}"
        )

    if not raw_rules:
        raise AssertionError(
            "Semgrep rule pack must contain " "at least one rule: " f"{rule_file}"
        )

    rules: list[dict[str, Any]] = []

    for index, raw_rule in enumerate(raw_rules):
        if not isinstance(
            raw_rule,
            dict,
        ):
            raise AssertionError(
                "Semgrep rule must be "
                "a YAML mapping: "
                f"{rule_file}, "
                f"index={index}"
            )

        rules.append(raw_rule)

    return rules


def test_semgrep_rule_ids_are_unique_across_rule_packs() -> None:
    pack_root = PROJECT_ROOT / "rules" / "semgrep" / "packs"

    rule_ids: list[str] = []

    for rule_file in sorted(pack_root.glob("*.yaml")):
        for rule in _load_rules(rule_file):
            rule_id = rule.get("id")

            assert isinstance(
                rule_id,
                str,
            ), (
                "Semgrep rule must contain " f"a string id: {rule_file}"
            )

            rule_ids.append(rule_id)

    assert len(rule_ids) == len(set(rule_ids))


def test_semgrep_rules_have_archdrift_metadata() -> None:
    pack_root = PROJECT_ROOT / "rules" / "semgrep" / "packs"

    for rule_file in sorted(pack_root.glob("*.yaml")):
        for rule in _load_rules(rule_file):
            rule_id = rule.get("id")

            assert isinstance(
                rule_id,
                str,
            ), (
                "Semgrep rule must contain " f"a string id: {rule_file}"
            )

            assert rule_id.startswith("archdrift.")

            metadata = rule.get("metadata")

            assert isinstance(
                metadata,
                dict,
            ), (
                "Semgrep rule must contain " "metadata: " f"{rule_id}"
            )

            archdrift = metadata.get("archdrift")

            assert isinstance(
                archdrift,
                dict,
            ), (
                "Semgrep rule must contain " "metadata.archdrift: " f"{rule_id}"
            )

            interaction = archdrift.get("interaction")

            assert isinstance(
                interaction,
                str,
            )

            assert interaction

            assert "protocol" in archdrift


def test_semgrep_rule_pack_directory_contains_rules() -> None:
    pack_root = PROJECT_ROOT / "rules" / "semgrep" / "packs"

    rule_files = tuple(sorted(pack_root.glob("*.yaml")))

    assert rule_files, "No Semgrep rule packs were found."

    for rule_file in rule_files:
        _load_rules(rule_file)
