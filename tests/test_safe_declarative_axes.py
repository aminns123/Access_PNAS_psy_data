import pytest

from psyview.models import PlotSpec, Series
from psyview.plotting.axes import (
    shared_axis_limits_for_scale,
)


def _spec(values, scale='log'):
    return PlotSpec(
        'test',
        'x',
        'y',
        [
            Series(
                list(range(1, len(values) + 1)),
                values,
                'data',
                'scatter',
            )
        ],
        yscale=scale,
    )


def test_csf_row_18_to_850_prefers_10_to_1000():
    policy = {
        'rounding': 'decades',
        'preferred_min': 10,
        'preferred_max': 1000,
    }

    limits = shared_axis_limits_for_scale(
        [
            _spec([18, 120, 400]),
            _spec([32, 300, 850]),
        ],
        'y',
        'log',
        policy,
    )

    assert limits == pytest.approx(
        (10, 1000)
    )


def test_csf_row_with_value_8_expands_to_1():
    policy = {
        'rounding': 'decades',
        'preferred_min': 10,
        'preferred_max': 1000,
    }

    limits = shared_axis_limits_for_scale(
        [
            _spec([8, 120, 400]),
            _spec([32, 300, 850]),
        ],
        'y',
        'log',
        policy,
    )

    assert limits == pytest.approx(
        (1, 1000)
    )


def test_row_union_is_calculated_once_from_raw_values():
    # A very tight row should not balloon through repeated padding/union.
    limits = shared_axis_limits_for_scale(
        [
            _spec([0.023, 0.028]),
            _spec([0.031, 0.036]),
        ],
        'y',
        'log',
        {
            'rounding': 'nice',
        },
    )

    assert limits == pytest.approx(
        (0.02, 0.05)
    )
