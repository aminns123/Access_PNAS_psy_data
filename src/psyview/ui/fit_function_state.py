"""Session-only fit-function preview state.

Stage 1 deliberately does NOT execute or fit custom equations.  The existing
lateral thesis Eq. B.25 fitter remains the only active fitter.
"""
from __future__ import annotations

from dataclasses import dataclass
import textwrap


DEFAULT_EQUATION = (
    "A*exp(-lam*abs(x))*(cos(2*pi*f*x+phi)-"
    "sign(x)*sin(2*pi*f*x+phi))"
)

DEFAULT_PARAMETERS = (
    "A; lam; f; phi"
)

THESIS_DISPLAY_EQUATION = (
    "R(X)=A exp(-λ|X|)[cos(kX+φ) − sgn(X) sin(kX+φ)]"
)


@dataclass(frozen=True)
class FitFunctionPreview:
    equation: str
    parameters: str


def validate_preview(equation: str, parameters: str) -> FitFunctionPreview:
    """Validate text for display/storage only; nothing here is executed."""
    equation = str(equation).strip()
    parameters = str(parameters).strip()

    if not equation:
        raise ValueError("Equation cannot be empty.")
    if not parameters:
        raise ValueError("Parameter description cannot be empty.")
    if len(equation) > 600:
        raise ValueError("Equation is too long (maximum 600 characters).")
    if len(parameters) > 600:
        raise ValueError(
            "Parameter description is too long (maximum 600 characters)."
        )

    return FitFunctionPreview(
        equation=equation,
        parameters=parameters,
    )


def fit_function_panel_text(
    preview: FitFunctionPreview | None,
    *,
    width: int = 29,
) -> str:
    """Build the visible right-side panel text."""
    active = textwrap.wrap(
        THESIS_DISPLAY_EQUATION,
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [""]

    lines = [
        "FIT FUNCTION",
        "",
        "ACTIVE FIT",
        "Thesis Eq. B.25",
        *active,
        "",
    ]

    if preview is None:
        lines.extend(
            [
                "CUSTOM PREVIEW",
                "None — using thesis fit only",
            ]
        )
    else:
        equation = textwrap.wrap(
            "R(x)=" + preview.equation,
            width=width,
            break_long_words=True,
            break_on_hyphens=False,
        ) or [""]
        parameters = textwrap.wrap(
            "Params: " + preview.parameters,
            width=width,
            break_long_words=True,
            break_on_hyphens=False,
        ) or [""]

        lines.extend(
            [
                "CUSTOM PREVIEW — NOT FITTED",
                *equation[:4],
                *parameters[:3],
            ]
        )

    lines.extend(
        [
            "",
            "G  Edit function preview",
            "F  Fit active Eq. B.25",
        ]
    )
    return "\n".join(lines)
