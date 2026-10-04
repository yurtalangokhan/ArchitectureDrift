from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_astronomy_shop_semgrep_rules_exist() -> None:
    rules = PROJECT_ROOT / "rules" / "semgrep" / "astronomy-shop.yaml"

    assert rules.is_file()


