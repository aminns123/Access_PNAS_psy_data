import pytest

from psyview.ui.fit_function_state import (
    FitFunctionPreview,
    fit_function_panel_text,
    validate_preview,
)


def test_fit_function_preview_validation_and_panel():
    preview = validate_preview(
        "A*cos(k*x+phi)",
        "A; k; phi",
    )
    assert preview == FitFunctionPreview(
        "A*cos(k*x+phi)",
        "A; k; phi",
    )

    text = fit_function_panel_text(preview)
    assert "ACTIVE FIT" in text
    assert "Thesis Eq. B.25" in text
    assert "CUSTOM PREVIEW — NOT FITTED" in text
    assert "A*cos(k*x+phi)" in text
    assert "F  Fit active Eq. B.25" in text


@pytest.mark.parametrize(
    "equation,parameters",
    [
        ("", "A"),
        ("A*x", ""),
    ],
)
def test_fit_function_preview_rejects_empty_fields(
    equation,
    parameters,
):
    with pytest.raises(ValueError):
        validate_preview(
            equation,
            parameters,
        )
