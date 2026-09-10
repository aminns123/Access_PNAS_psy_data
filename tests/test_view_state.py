import pytest

from psyview.ui.view_state import (
    SCALE_CHOICES,
    SCOPE_CHOICES,
    cycle_choice,
    parse_axis_limit,
    validate_bound_pair,
)


def test_axis_limit_parser_accepts_auto_and_finite_numbers():
    assert parse_axis_limit("") is None
    assert parse_axis_limit("Auto") is None
    assert parse_axis_limit("-1") == -1
    assert parse_axis_limit("0.001") == pytest.approx(0.001)
    assert parse_axis_limit("1e3") == pytest.approx(1000)


@pytest.mark.parametrize("text", ["abc", "--", "nan", "NaN", "inf", "-inf"])
def test_axis_limit_parser_rejects_invalid_or_nonfinite_values(text):
    with pytest.raises(ValueError):
        parse_axis_limit(text)


def test_scale_and_scope_cycles_include_default():
    assert cycle_choice(None, SCALE_CHOICES, 1) == "linear"
    assert cycle_choice("linear", SCALE_CHOICES, 1) == "log"
    assert cycle_choice("log", SCALE_CHOICES, 1) is None
    assert cycle_choice(None, SCOPE_CHOICES, -1) == "row"


def test_manual_bounds_validation():
    validate_bound_pair(-1, 1, "linear")
    validate_bound_pair(None, 1, "linear")
    with pytest.raises(ValueError):
        validate_bound_pair(1, 1, "linear")
    with pytest.raises(ValueError):
        validate_bound_pair(-1, 1, "log")
