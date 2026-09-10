"""Small, UI-agnostic helpers for PsyView's session-only View overrides."""

from __future__ import annotations

import math
from typing import TypeVar


T = TypeVar("T")

SCALE_CHOICES = (None, "linear", "log")
SCOPE_CHOICES = (None, "data", "row")


def cycle_choice(current: T, choices: tuple[T, ...], delta: int) -> T:
    """Cycle left/right through a finite set of choices."""
    if not choices:
        raise ValueError("choices must not be empty")
    try:
        index = choices.index(current)
    except ValueError:
        index = 0
    step = 1 if delta >= 0 else -1
    return choices[(index + step) % len(choices)]


def parse_axis_limit(text: str) -> float | None:
    """Parse a manual axis bound; blank/Auto means automatic."""
    value = text.strip()
    if not value or value.casefold() == "auto":
        return None

    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError("Enter a finite number or Auto.") from exc

    if not math.isfinite(number):
        raise ValueError("Enter a finite number or Auto.")

    return number


def validate_bound_pair(
    lower: float | None,
    upper: float | None,
    scale: str,
) -> None:
    """Validate a resolved manual/automatic bound pair."""
    for value in (lower, upper):
        if value is not None and not math.isfinite(float(value)):
            raise ValueError("Axis limits must be finite.")

    if scale == "log":
        if lower is not None and lower <= 0:
            raise ValueError("Logarithmic axis minimum must be greater than zero.")
        if upper is not None and upper <= 0:
            raise ValueError("Logarithmic axis maximum must be greater than zero.")

    if lower is not None and upper is not None and lower >= upper:
        raise ValueError("Axis minimum must be smaller than axis maximum.")
