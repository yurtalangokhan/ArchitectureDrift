from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


DIRECTORIES = [
    # Source package
    "src/archdrift",
    "src/archdrift/model",
    "src/archdrift/adapters",
    "src/archdrift/analysis",
    "src/archdrift/experiments",

    # Contracts
    "contracts",

    # Case definitions
    "cases/astronomy-shop",
    "cases/eshop",
    "cases/teastore",

    # Mutations
    "mutations/astronomy-shop",
    "mutations/eshop",
    "mutations/teastore",

    # Experiment artifacts
    "workloads",
    "evidence",
    "graphs",
    "results",

    # Tests
    "tests",
]


FILES = [
    # Root files
    "pyproject.toml",
    "README.md",
    ".gitignore",

    # Python package
    "src/archdrift/__init__.py",
    "src/archdrift/cli.py",

    # Model
    "src/archdrift/model/__init__.py",
    "src/archdrift/model/graph.py",
    "src/archdrift/model/evidence.py",
    "src/archdrift/model/contract.py",
    "src/archdrift/model/mutation.py",

    # Adapters
    "src/archdrift/adapters/__init__.py",
    "src/archdrift/adapters/compose.py",
    "src/archdrift/adapters/aspire.py",
    "src/archdrift/adapters/otel.py",
    "src/archdrift/adapters/repository.py",

    # Analysis
    "src/archdrift/analysis/__init__.py",
    "src/archdrift/analysis/normalize.py",
    "src/archdrift/analysis/fusion.py",
    "src/archdrift/analysis/graph_delta.py",
    "src/archdrift/analysis/conformance.py",
    "src/archdrift/analysis/metrics.py",

    # Experiments
    "src/archdrift/experiments/__init__.py",
    "src/archdrift/experiments/runner.py",
    "src/archdrift/experiments/activation.py",
    "src/archdrift/experiments/reporting.py",

    # Architecture contracts
    "contracts/astronomy-shop.yaml",
    "contracts/eshop.yaml",
    "contracts/teastore.yaml",

    # Case definitions
    "cases/astronomy-shop/case.yaml",
    "cases/eshop/case.yaml",
    "cases/teastore/case.yaml",

    # Tests
    "tests/__init__.py",
    "tests/test_graph.py",
    "tests/test_graph_delta.py",
    "tests/test_contract.py",
    "tests/test_mutation.py",
]


def create_directories() -> None:
    for directory in DIRECTORIES:
        path = PROJECT_ROOT / directory
        path.mkdir(parents=True, exist_ok=True)
        print(f"[DIR ] {path.relative_to(PROJECT_ROOT)}")


def create_files() -> None:
    for file_name in FILES:
        path = PROJECT_ROOT / file_name

        # Parent directory may not yet exist.
        path.parent.mkdir(parents=True, exist_ok=True)

        if not path.exists():
            path.touch()
            print(f"[FILE] {path.relative_to(PROJECT_ROOT)}")
        else:
            print(f"[SKIP] {path.relative_to(PROJECT_ROOT)} already exists")


def main() -> None:
    print(f"Creating ArchitectureDrift project structure under:")
    print(PROJECT_ROOT)
    print()

    create_directories()
    create_files()

    print()
    print("Project structure created successfully.")


if __name__ == "__main__":
    main()