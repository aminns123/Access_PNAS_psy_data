import pytest

from psyview.plotting.axes import (
    apply_declared_limit_policy,
)


def test_csf_18_to_850_becomes_10_to_1000():
    assert apply_declared_limit_policy(
        (18, 850),
        'log',
        {
            'rounding': 'decades',
            'preferred_min': 10,
            'preferred_max': 1000,
        },
    ) == pytest.approx(
        (10, 1000)
    )


def test_csf_value_below_10_expands_down_to_1():
    assert apply_declared_limit_policy(
        (8, 850),
        'log',
        {
            'rounding': 'decades',
            'preferred_min': 10,
            'preferred_max': 1000,
        },
    ) == pytest.approx(
        (1, 1000)
    )


def test_preferred_bounds_never_clip_data():
    assert apply_declared_limit_policy(
        (18, 1800),
        'log',
        {
            'rounding': 'decades',
            'preferred_min': 10,
            'preferred_max': 1000,
        },
    ) == pytest.approx(
        (10, 10000)
    )
