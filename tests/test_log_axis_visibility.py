from types import SimpleNamespace

import pytest

from psyview.plotting.axes import axis_policy


def _series(x, y, kind='line'):
    return SimpleNamespace(
        x=x,
        y=y,
        kind=kind,
    )


def _spec(series, xscale='linear', yscale='linear', xlim=None, ylim=None):
    return SimpleNamespace(
        series=series,
        xscale=xscale,
        yscale=yscale,
        xlim=xlim,
        ylim=ylim,
    )


def test_log_x_keeps_physical_shared_limits():
    spec = _spec(
        [_series([10, 20, 403], [2, 4, 8])],
        xscale='log',
        xlim=(5, 1000),
    )

    scale, limits, fallback = axis_policy(
        spec,
        'x',
    )

    assert scale == 'log'
    assert limits == pytest.approx((5, 1000))
    assert fallback is False


def test_negative_auxiliary_y_does_not_force_valid_csf_linear():
    spec = _spec(
        [
            _series([0.5, 1, 2], [130, 200, 250], 'scatter'),
            _series([0.5, 1, 2, 16], [120, 210, 230, -5], 'line'),
        ],
        yscale='log',
        ylim=(10, 1000),
    )

    scale, limits, fallback = axis_policy(
        spec,
        'y',
    )

    assert scale == 'log'
    assert limits == pytest.approx((10, 1000))
    assert fallback is False


def test_log_falls_back_only_when_no_positive_values_exist():
    spec = _spec(
        [_series([1, 2], [-2, 0])],
        yscale='log',
    )

    scale, limits, fallback = axis_policy(
        spec,
        'y',
    )

    assert scale == 'linear'
    assert fallback is True
    assert limits[0] < limits[1]
