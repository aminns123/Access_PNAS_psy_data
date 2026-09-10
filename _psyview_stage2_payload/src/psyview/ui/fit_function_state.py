"""Session-only selection of the lateral diagnostic fit function."""

from __future__ import annotations

import textwrap

from ..analysis.custom_fit import (
    CustomFitDefinition,
    build_custom_fit_definition,
)


DEFAULT_EQUATION = (
    "A*exp(-lam*abs(x))*"
    "(cos(2*pi*f*x+phi)-"
    "sign(x)*sin(2*pi*f*x+phi))"
)

DEFAULT_PARAMETERS = (
    "A=-0.2[-1,1]; "
    "lam=0.2[0.001,1]; "
    "f=3[0.5,10]; "
    "phi=0[-pi,pi]"
)

THESIS_DISPLAY_EQUATION = (
    "R(X)=A exp(-λ|X|)"
    "[cos(kX+φ) − sgn(X) sin(kX+φ)]"
)


def validate_fit_function(
    equation,
    parameters,
):
    return build_custom_fit_definition(
        equation,
        parameters,
    )


def fit_function_panel_text(
    definition: CustomFitDefinition | None,
    *,
    width=29,
):
    if definition is None:
        equation = textwrap.wrap(
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
            *equation,
            "",
            "G  Edit fit function",
            "F  Fit active Eq. B.25",
        ]

        return "\n".join(lines)

    equation = textwrap.wrap(
        "R(x)=" + definition.source_expression,
        width=width,
        break_long_words=True,
        break_on_hyphens=False,
    ) or [""]

    parameters = textwrap.wrap(
        "Params: " + definition.parameter_text(),
        width=width,
        break_long_words=True,
        break_on_hyphens=False,
    ) or [""]

    lines = [
        "FIT FUNCTION",
        "",
        "ACTIVE FIT",
        "Custom • session-only",
        *equation[:4],
        *parameters[:4],
        "",
        "G  Edit fit function",
        "F  Fit active custom function",
    ]

    return "\n".join(lines)
