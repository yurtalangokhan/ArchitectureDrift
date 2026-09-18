from __future__ import annotations


def normalize_identifier(
    value: str,
    *,
    field_name: str = "identifier",
) -> str:
    """
    Normalize and validate a canonical identifier.

    Canonical identifiers are stable machine-readable names such as:

        checkout
        recommendation
        astronomy-shop
        AS-C001

    Whitespace is intentionally not allowed because identifiers are later
    used in graph identities, contracts, mutation oracles, and result files.
    """

    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{field_name} must not be empty."
        )

    if any(character.isspace() for character in normalized):
        raise ValueError(
            f"{field_name} must not contain whitespace: {value!r}"
        )

    return normalized


def normalize_required_text(
    value: str,
    *,
    field_name: str,
) -> str:
    """
    Normalize a required free-text field.
    """

    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{field_name} must not be empty."
        )

    return normalized


def normalize_optional_text(
    value: str | None,
) -> str | None:
    """
    Normalize an optional free-text field.

    Blank strings are converted to None.
    """

    if value is None:
        return None

    normalized = value.strip()

    return normalized or None