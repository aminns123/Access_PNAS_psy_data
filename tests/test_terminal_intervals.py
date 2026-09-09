from dataclasses import dataclass

import pytest

from psyview.plotting.terminal import (
    _interval_samples,
    _is_vertical_interval,
)


@dataclass
class DummySeries:
    x: list
    y: list
    kind: str = 'line'


def test_vertical_interval_detection():
    assert _is_vertical_interval(
        DummySeries([3.0, 3.0], [10.0, 20.0])
    )
    assert not _is_vertical_interval(
        DummySeries([3.0, 4.0], [10.0, 20.0])
    )
    assert not _is_vertical_interval(
        DummySeries([3.0, 3.0], [10.0, 20.0], kind='scatter')
    )


def test_log_interval_sampling_stays_positive_and_hits_endpoints():
    values = _interval_samples(10.0, 1000.0, 'log', count=9)
    assert values[0] == pytest.approx(10.0)
    assert values[-1] == pytest.approx(1000.0)
    assert all(value > 0 for value in values)


def test_linear_interval_sampling_hits_endpoints():
    values = _interval_samples(-1.0, 1.0, 'linear', count=9)
    assert values[0] == pytest.approx(-1.0)
    assert values[-1] == pytest.approx(1.0)
