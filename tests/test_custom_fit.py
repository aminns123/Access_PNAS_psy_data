import numpy as np
import pandas as pd
import pytest

from psyview.analysis.custom_fit import (
    build_custom_fit_definition,
    evaluate_custom_function,
    fit_custom_profile,
)


def test_custom_definition_accepts_math_and_latex_like_notation():
    definition = build_custom_fit_definition(
        r"A*\exp(-\lambda*|x|)*\cos(2*\pi*f*x+\phi)",
        (
            "A=0.2[-2,2]; "
            "lam=1[0.001,10]; "
            "f=3[0.1,20]; "
            "phi=0[-pi,pi]"
        ),
    )

    assert [
        parameter.name
        for parameter in definition.parameters
    ] == [
        "A",
        "lam",
        "f",
        "phi",
    ]

    values = evaluate_custom_function(
        definition,
        np.array([0.0, 0.2]),
        [0.2, 1.0, 3.0, 0.0],
    )
    assert np.all(np.isfinite(values))


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('echo bad')",
        "(1).__class__",
        "x[0] + A",
        "[A for A in x]",
        "open('file')",
    ],
)
def test_custom_definition_rejects_python_execution(expression):
    with pytest.raises(ValueError):
        build_custom_fit_definition(
            expression,
            "A=1[0,2]",
        )


def test_custom_definition_requires_complete_valid_bounds():
    with pytest.raises(ValueError, match="Missing parameter"):
        build_custom_fit_definition(
            "A*x+C",
            "A=1[-2,2]",
        )

    with pytest.raises(ValueError, match="lower bound"):
        build_custom_fit_definition(
            "A*x",
            "A=1[2,-2]",
        )

    with pytest.raises(ValueError, match="inside its bounds"):
        build_custom_fit_definition(
            "A*x",
            "A=5[-2,2]",
        )


def test_custom_fit_recovers_synthetic_damped_exponential():
    x = np.linspace(
        -0.8,
        0.8,
        31,
    )
    true_a = 0.42
    true_b = 1.35
    y = (
        true_a
        * np.exp(
            -true_b
            * np.abs(x)
        )
    )

    frame = pd.DataFrame(
        {
            "distance_from_flanker_edge_deg": x,
            "log_sensitivity_ratio": y,
            "spread": np.full_like(
                x,
                0.12,
            ),
        }
    )

    definition = build_custom_fit_definition(
        "A*exp(-b*abs(x))",
        "A=0.2[-1,1]; b=0.8[0.001,5]",
    )

    result = fit_custom_profile(
        frame,
        definition,
    )
    parameters = dict(
        result.parameters
    )

    assert parameters["A"] == pytest.approx(
        true_a,
        abs=1e-3,
    )
    assert parameters["b"] == pytest.approx(
        true_b,
        abs=1e-3,
    )
    assert result.rmse < 1e-5
