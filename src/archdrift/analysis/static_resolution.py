from __future__ import annotations

import re

from archdrift.model.source_static import (
    EndpointBinding,
    ResolvedStaticInteraction,
    SourcePathRule,
    SourceStaticFinding,
    StaticResolution,
    StaticResolutionSet,
    StaticResolutionStatus,
)

_ENV_IDENTIFIER = re.compile(r"^[A-Z][A-Z0-9_]*$")

_TEMPLATE_ENV = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")


def _normalize_path(
    path: str,
) -> str:
    return (
        path.replace(
            "\\",
            "/",
        )
        .strip()
        .lstrip("./")
    )


def _path_matches_prefix(
    path: str,
    prefix: str,
) -> bool:
    normalized_path = _normalize_path(path)

    normalized_prefix = _normalize_path(prefix).rstrip("/")

    if normalized_path == normalized_prefix:
        return True

    if normalized_path.startswith(normalized_prefix + "/"):
        return True

    return f"/{normalized_prefix}/" in f"/{normalized_path}/"


def _resolve_source_rule(
    *,
    path: str,
    rules: tuple[
        SourcePathRule,
        ...,
    ],
) -> SourcePathRule | None:
    matches = tuple(
        rule
        for rule in rules
        if _path_matches_prefix(
            path,
            rule.path_prefix,
        )
    )

    if not matches:
        return None

    ranked = sorted(
        matches,
        key=lambda rule: len(_normalize_path(rule.path_prefix)),
        reverse=True,
    )

    if len(ranked) > 1 and len(_normalize_path(ranked[0].path_prefix)) == len(
        _normalize_path(ranked[1].path_prefix)
    ):
        return None

    return ranked[0]


def extract_environment_key(
    expression: str,
) -> str | None:
    """
    Resolve a source-static endpoint expression to exactly one environment
    variable.

    Supported high-confidence forms:

        CURRENCY_ADDR
        `${SHIPPING_ADDR}/get-quote`

    Expressions containing zero or multiple endpoint variables are left
    unresolved.
    """

    normalized = expression.strip()

    if _ENV_IDENTIFIER.fullmatch(normalized):
        return normalized

    matches: tuple[str, ...] = tuple(
        dict.fromkeys(match.group(1) for match in _TEMPLATE_ENV.finditer(normalized))
    )

    if len(matches) == 1:
        return matches[0]

    return None


class StaticTargetResolver:
    """
    Resolve engine-neutral source-static findings against explicit source
    layout and resolved configuration endpoint bindings.
    """

    def resolve(
        self,
        *,
        findings: tuple[
            SourceStaticFinding,
            ...,
        ],
        source_rules: tuple[
            SourcePathRule,
            ...,
        ],
        bindings: tuple[
            EndpointBinding,
            ...,
        ],
    ) -> StaticResolutionSet:
        binding_index: dict[
            tuple[
                str,
                str,
            ],
            list[EndpointBinding],
        ] = {}

        for binding in bindings:
            key = (
                binding.source_service_id,
                binding.environment_key,
            )

            binding_index.setdefault(
                key,
                [],
            ).append(binding)

        results: list[StaticResolution] = []

        for finding in findings:
            source_rule = _resolve_source_rule(
                path=finding.path,
                rules=source_rules,
            )

            if source_rule is None:
                results.append(
                    StaticResolution(
                        finding=finding,
                        status=(StaticResolutionStatus.SOURCE_NOT_RESOLVED),
                        reason=(
                            "No unique source-service mapping "
                            "matched the finding path."
                        ),
                    )
                )

                continue

            environment_key = extract_environment_key(finding.target_expression)

            if environment_key is None:
                results.append(
                    StaticResolution(
                        finding=finding,
                        status=(StaticResolutionStatus.TARGET_EXPRESSION_NOT_RESOLVED),
                        reason=(
                            "Target expression does not resolve "
                            "to exactly one supported environment key."
                        ),
                    )
                )

                continue

            candidates = binding_index.get(
                (
                    source_rule.service_id,
                    environment_key,
                ),
                [],
            )

            if len(candidates) != 1:
                results.append(
                    StaticResolution(
                        finding=finding,
                        status=(StaticResolutionStatus.ENDPOINT_BINDING_NOT_FOUND),
                        reason=(
                            "No unique resolved endpoint binding exists "
                            f"for {source_rule.service_id!r} / "
                            f"{environment_key!r}."
                        ),
                    )
                )

                continue

            binding = candidates[0]

            resolved = ResolvedStaticInteraction(
                finding=finding,
                source_service_id=(source_rule.service_id),
                source_type=(source_rule.service_type),
                environment_key=(environment_key),
                target_service_id=(binding.target_service_id),
                target_type=(binding.target_type),
            )

            results.append(
                StaticResolution(
                    finding=finding,
                    status=(StaticResolutionStatus.RESOLVED),
                    resolved=resolved,
                )
            )

        return StaticResolutionSet(results=tuple(results))
