import pytest

from psyview.ui.fit_function_state import (
    fit_function_panel_text,
    validate_fit_function,
)


def test_default_panel_uses_thesis_fit():
    text = fit_function_panel_text(
        None
    )
    assert "ACTIVE FIT" in text
    assert "Thesis Eq. B.25" in text
    assert "F  Fit active Eq. B.25" in text


def test_custom_definition_becomes_active_panel_fit():
    definition = validate_fit_function(
        "A*cos(2*pi*f*x+phi)+C",
        (
            "A=0.2[-2,2]; "
            "f=3[0.1,20]; "
            "phi=0[-pi,pi]; "
            "C=0[-2,2]"
        ),
    )

    text = fit_function_panel_text(
        definition
    )

    assert "ACTIVE FIT" in text
    assert "Custom • session-only" in text
    assert "A*cos(2*pi*f*x+phi)+C" in text
    assert "F  Fit active custom function" in text


def test_invalid_custom_definition_is_rejected():
    with pytest.raises(ValueError):
        validate_fit_function(
            "A*cos(2*pi*f*x)",
            "A; f",
        )
