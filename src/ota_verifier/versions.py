"""Explicit numeric release versions; prereleases are deliberately unsupported."""

import re
from typing import Literal

Operator = Literal["==", "!=", ">=", "<=", ">", "<"]


def parse_version(value: str) -> tuple[int, ...]:
    """Parse a dotted numeric version, normalizing trailing zero components."""
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", value):
        raise ValueError(f"Unsupported numeric version: {value!r}")
    parts = [int(part) for part in value.split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def parse_spec(value: str) -> tuple[str, tuple[int, ...]]:
    """Parse one comparison; ranges and implicit operators are unsupported."""
    match = re.fullmatch(r"(==|!=|>=|<=|>|<)([0-9]+(?:\.[0-9]+)*)", value)
    if match is None:
        raise ValueError(f"Unsupported version specification: {value!r}")
    return match[1], parse_version(match[2])


def matches(version: str, specification: str) -> bool:
    """Return whether a numeric version satisfies an explicit comparison."""
    actual = parse_version(version)
    operator, expected = parse_spec(specification)
    return {"==": actual == expected, "!=": actual != expected,
            ">=": actual >= expected, "<=": actual <= expected,
            ">": actual > expected, "<": actual < expected}[operator]
