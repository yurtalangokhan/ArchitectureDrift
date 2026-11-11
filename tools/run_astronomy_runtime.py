from __future__ import annotations

import argparse
import http.client
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path

import yaml

from archdrift.experiments.astronomy_runtime_profile import (
    AstronomyComposeMode,
    AstronomyWorkload,
    require_astronomy_runtime_profile,
)
from archdrift.experiments.otlp_capture import (
    merge_otlp_json_lines,
    relation_present,
)
from archdrift.experiments.runtime_execution import (
    RuntimeVariant,
    prepare_runtime_execution,
)
from archdrift.model.graph import (
    NodeType,
)

ASTRONOMY_VERSION = "3.1.0"
FRONTEND_CONTAINER_PORT = 8080

ASTRONOMY_MUTABLE_SERVICES = (
    "frontend",
    "checkout",
    "payment",
    "cart",
)

FRONTEND_URL = "http://localhost:8080"

PRODUCT_ID = "0PUK6V6EV0"

CHECKOUT_PERSON = {
    "email": "archdrift@example.com",
    "address": {
        "streetAddress": ("1600 Amphitheatre Parkway"),
        "zipCode": "94043",
        "city": "Mountain View",
        "state": "CA",
        "country": "United States",
    },
    "userCurrency": "USD",
    "creditCard": {
        "creditCardNumber": ("4432-8015-6152-0454"),
        "creditCardExpirationMonth": 1,
        "creditCardExpirationYear": 2039,
        "creditCardCvv": 672,
    },
}


class AstronomyRuntimeError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Run the Astronomy Shop " "ArchitectureDrift runtime slice.")
    )

    parser.add_argument(
        "--mutation",
        default="AS-M01",
    )

    parser.add_argument(
        "--variant",
        required=True,
        choices=tuple(item.value for item in RuntimeVariant),
    )

    parser.add_argument(
        "--replace-mutant",
        action="store_true",
    )

    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
    )

    return parser.parse_args()


def run_command(
    command: list[str],
    *,
    cwd: Path,
    environment: Mapping[
        str,
        str,
    ],
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    print(
        "$",
        " ".join(command),
    )

    process = subprocess.run(
        command,
        cwd=cwd,
        env=dict(environment),
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if check and process.returncode != 0:
        raise AstronomyRuntimeError("Command failed: " + " ".join(command))

    return process


def resolve_frontend_url(
    *,
    compose: list[str],
    cwd: Path,
    environment: Mapping[str, str],
    timeout_seconds: int = 60,
) -> str:
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        process = subprocess.run(
            compose
            + [
                "port",
                "frontend",
                str(FRONTEND_CONTAINER_PORT),
            ],
            cwd=cwd,
            env=dict(environment),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )

        if process.returncode == 0:
            for line in process.stdout.splitlines():
                endpoint = line.strip()

                if not endpoint:
                    continue

                _, separator, port_text = endpoint.rpartition(":")

                if separator and port_text.isdigit():
                    frontend_url = f"http://127.0.0.1:{port_text}"

                    print("[OK] frontend endpoint " f"resolved: {frontend_url}")

                    return frontend_url

        time.sleep(1)

    raise AstronomyRuntimeError("Could not resolve frontend host port.")


def wait_for_frontend(
    *,
    frontend_url: str,
    timeout_seconds: int = 300,
) -> None:
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(
                frontend_url,
                timeout=5,
            ) as response:
                if 200 <= response.status < 500:
                    print("[OK] frontend ready")
                    return

        except (
            urllib.error.URLError,
            TimeoutError,
            ConnectionError,
            http.client.HTTPException,
        ):
            pass

        time.sleep(2)

    raise AstronomyRuntimeError("Astronomy frontend did not " "become ready.")


def post_json(
    *,
    url: str,
    payload: dict[
        str,
        object,
    ],
) -> None:
    body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "baggage": ("synthetic_request=true," "archdrift.runtime=true"),
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=30,
        ) as response:
            if not (200 <= response.status < 300):
                raise AstronomyRuntimeError(
                    "Unexpected HTTP status: " f"{response.status}"
                )

    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode(
            "utf-8",
            errors="replace",
        )

        raise AstronomyRuntimeError(f"HTTP {exc.code}: " f"{body_text[:500]}") from exc

    except (
        urllib.error.URLError,
        TimeoutError,
        ConnectionError,
        http.client.HTTPException,
    ) as exc:
        raise AstronomyRuntimeError(
            "HTTP request failed: " f"{type(exc).__name__}: {exc}"
        ) from exc


def run_checkout(
    *,
    frontend_url: str,
    mutation_id: str,
    variant: RuntimeVariant,
    timeout_seconds: int = 120,
) -> None:
    deadline = time.monotonic() + timeout_seconds

    attempt = 0
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        attempt += 1

        user_id = (
            "archdrift-" f"{mutation_id.lower()}-" f"{variant.value}-" f"{attempt:02d}"
        )

        try:
            post_json(
                url=(frontend_url + "/api/cart"),
                payload={
                    "item": {
                        "productId": PRODUCT_ID,
                        "quantity": 1,
                    },
                    "userId": user_id,
                },
            )

            checkout = dict(CHECKOUT_PERSON)

            checkout["userId"] = user_id

            post_json(
                url=(frontend_url + "/api/checkout"),
                payload=checkout,
            )

            print(
                "[OK] deterministic "
                "checkout completed "
                f"after {attempt} "
                "attempt(s)"
            )

            return

        except AstronomyRuntimeError as exc:
            last_error = exc

            print("[WAIT] checkout attempt " f"{attempt} failed: " f"{exc}")

            time.sleep(5)

    raise AstronomyRuntimeError(
        "Checkout workload did not "
        "succeed within "
        f"{timeout_seconds}s. "
        f"Last error: {last_error}"
    )


def load_astronomy_node_types(
    root: Path,
) -> dict[
    str,
    NodeType,
]:
    configuration = yaml.safe_load(
        (root / "cases" / "real-evidence.yaml").read_text(encoding="utf-8")
    )

    raw_types = configuration["subjects"]["astronomy-shop"]["scope"]["node_types"]

    return {
        name: NodeType(value)
        for (
            name,
            value,
        ) in raw_types.items()
    }


def main() -> int:
    args = parse_args()

    root = args.project_root.resolve()

    variant = RuntimeVariant(args.variant)

    profile = require_astronomy_runtime_profile(args.mutation)

    record, _ = prepare_runtime_execution(
        project_root=root,
        mutation_id=(args.mutation),
        variant=variant,
        replace_mutant=(args.replace_mutant),
    )

    workspace = (root / record.workspace).resolve()

    output_directory = (root / record.output_directory).resolve()

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    raw_trace_file = output_directory / "traces.otlp.jsonl"

    normalized_trace_file = (root / record.otlp_trace_file).resolve()

    if raw_trace_file.exists():
        raw_trace_file.unlink()

    if normalized_trace_file.exists():
        normalized_trace_file.unlink()

    collector_config = (
        root / "runtime" / "astronomy" / "otelcol-capture.yml"
    ).resolve()

    compose_override = (
        root / "runtime" / "astronomy" / "compose.runtime.yaml"
    ).resolve()

    environment = dict(os.environ)

    environment["ARCHDRIFT_CAPTURE_DIR"] = output_directory.as_posix()

    environment["ARCHDRIFT_COLLECTOR_CONFIG"] = collector_config.as_posix()

    # Do not use DEMO_VERSION=latest
    # during the experiment.
    environment["DEMO_VERSION"] = ASTRONOMY_VERSION

    compose = [
        "docker",
        "compose",
        "--project-directory",
        str(workspace),
        "-f",
        str(workspace / "compose.yaml"),
    ]

    if profile.compose_mode is AstronomyComposeMode.FULL:
        compose.extend(
            [
                "-f",
                str(workspace / "compose.full.yaml"),
            ]
        )

    compose.extend(
        [
            "-f",
            str(compose_override),
        ]
    )

    if profile.compose_mode is AstronomyComposeMode.FULL:
        compose.extend(
            [
                "-f",
                str(root / "runtime" / "astronomy" / "compose.runtime.full.yaml"),
            ]
        )

    try:
        # Clean any previous Astronomy execution first.
        run_command(
            compose
            + [
                "down",
                "--volumes",
                "--remove-orphans",
            ],
            cwd=workspace,
            environment=environment,
            check=False,
        )

        # Restore official pinned images for all services that
        # can be modified by Astronomy Shop mutations.
        #
        # This prevents a mutant image from contaminating a
        # subsequent baseline or another mutation execution.
        run_command(
            compose
            + [
                "pull",
                *ASTRONOMY_MUTABLE_SERVICES,
            ],
            cwd=workspace,
            environment=environment,
        )

        # Build only the service modified by the current
        # mutation/profile from the exact selected workspace.
        run_command(
            compose
            + [
                "build",
                *profile.build_services,
            ],
            cwd=workspace,
            environment=environment,
        )

        runtime_services = [
            "frontend",
        ]

        if profile.compose_mode is AstronomyComposeMode.FULL:
            runtime_services.append("kafka")

        up_result = run_command(
            compose
            + [
                "up",
                "-d",
                "--no-build",
                *runtime_services,
            ],
            cwd=workspace,
            environment=environment,
            check=False,
        )

        if up_result.returncode != 0:
            print(
                "[ERROR] Astronomy Shop startup failed. "
                "Collecting diagnostics before cleanup."
            )

            run_command(
                compose
                + [
                    "ps",
                    "-a",
                ],
                cwd=workspace,
                environment=environment,
                check=False,
            )

            for diagnostic_service in (
                "frontend",
                "checkout",
                "payment",
                "product-catalog",
                "shipping",
                "quote",
                "recommendation",
                "cart",
                "email",
            ):
                run_command(
                    compose
                    + [
                        "logs",
                        "--no-color",
                        "--tail",
                        "120",
                        diagnostic_service,
                    ],
                    cwd=workspace,
                    environment=environment,
                    check=False,
                )

                run_command(
                    [
                        "docker",
                        "inspect",
                        diagnostic_service,
                        "--format",
                        "{{json .State.Health}}",
                    ],
                    cwd=workspace,
                    environment=environment,
                    check=False,
                )

            raise AstronomyRuntimeError("Astronomy Shop failed to start.")

        frontend_url = resolve_frontend_url(
            compose=compose,
            cwd=workspace,
            environment=environment,
        )

        wait_for_frontend(
            frontend_url=frontend_url,
        )

        if profile.workload is AstronomyWorkload.CHECKOUT:
            try:
                run_checkout(
                    frontend_url=frontend_url,
                    mutation_id=args.mutation,
                    variant=variant,
                )

            except AstronomyRuntimeError:
                print(
                    "[ERROR] Astronomy workload failed. "
                    "Collecting runtime diagnostics."
                )

                for diagnostic_service in (
                    "frontend",
                    "checkout",
                    "payment",
                ):
                    run_command(
                        compose
                        + [
                            "logs",
                            "--no-color",
                            "--tail",
                            "200",
                            diagnostic_service,
                        ],
                        cwd=workspace,
                        environment=environment,
                        check=False,
                    )

                raise
        else:
            raise AstronomyRuntimeError(
                "Unsupported Astronomy workload: " f"{profile.workload}"
            )

        # Give SDK batch exporters and
        # Collector file exporter time to
        # flush the controlled request.
        time.sleep(5)

    finally:
        run_command(
            compose
            + [
                "down",
                "--volumes",
                "--remove-orphans",
            ],
            cwd=workspace,
            environment=environment,
            check=False,
        )

    record_count = merge_otlp_json_lines(
        source=raw_trace_file,
        destination=(normalized_trace_file),
    )

    node_types = load_astronomy_node_types(root)

    (
        expected_source,
        expected_relation,
        expected_target,
    ) = profile.expected_relation

    detected = relation_present(
        trace_file=normalized_trace_file,
        node_types=node_types,
        source=expected_source,
        relation=expected_relation,
        target=expected_target,
    )

    expected = (
        False if variant is RuntimeVariant.BASELINE else profile.mutant_runtime_expected
    )

    print(
        "[RESULT] "
        f"mutation={profile.mutation_id} "
        f"variant={variant.value} "
        f"records={record_count} "
        f"{expected_source} "
        f"{expected_relation.value} "
        f"{expected_target}="
        f"{detected}"
    )

    if detected != expected:
        raise AstronomyRuntimeError(
            f"{profile.mutation_id} runtime "
            "acceptance criterion failed. "
            f"Expected "
            f"{expected_source} "
            f"{expected_relation.value} "
            f"{expected_target}="
            f"{expected}, "
            f"observed={detected}."
        )

    print("[OK] " f"{profile.mutation_id} runtime " "acceptance criterion passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
