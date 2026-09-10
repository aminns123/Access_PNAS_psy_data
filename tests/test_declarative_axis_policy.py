import pytest

from psyview.plotting.axes import (
    apply_declared_limit_policy,
)


def test_csf_soft_preferred_window():
    policy = {
        'rounding': 'decades',
        'preferred_min': 10,
        'preferred_max': 1000,
    }

    assert apply_declared_limit_policy(
        (18, 850),
        'log',
        policy,
    ) == pytest.approx(
        (10, 1000)
    )


def test_csf_soft_min_expands_when_data_drop_below_ten():
    policy = {
        'rounding': 'decades',
        'preferred_min': 10,
        'preferred_max': 1000,
    }

    assert apply_declared_limit_policy(
        (8, 850),
        'log',
        policy,
    ) == pytest.approx(
        (1, 1000)
    )


def test_csf_soft_max_never_clips_high_data():
    policy = {
        'rounding': 'decades',
        'preferred_min': 10,
        'preferred_max': 1000,
    }

    assert apply_declared_limit_policy(
        (18, 1800),
        'log',
        policy,
    ) == pytest.approx(
        (10, 10000)
    )
