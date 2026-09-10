import math

import pytest

from psyview.plotting.axes import anchor_ticks


def test_linear_anchor_ticks_are_min_mid_max():
    assert anchor_ticks(
        (-0.4, 0.8),
        'linear',
    ) == pytest.approx(
        [-0.4, 0.2, 0.8]
    )


def test_log_anchor_ticks_use_geometric_midpoint():
    ticks = anchor_ticks(
        (0.01, 1.0),
        'log',
    )

    assert ticks == pytest.approx(
        [0.01, 0.1, 1.0]
    )

    # The middle value is therefore physically centred on a log axis.
    assert math.log10(ticks[1]) == pytest.approx(
        (
            math.log10(ticks[0])
            + math.log10(ticks[2])
        ) / 2.0
    )
