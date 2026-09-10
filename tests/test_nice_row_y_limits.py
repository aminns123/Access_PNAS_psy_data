import pytest

from psyview.plotting.axes import nice_y_limits


def test_csf_like_log_row_uses_readable_decades():
    # Representative sensitivity range:
    # min around tens, max several hundred.
    assert nice_y_limits(
        [18, 42, 155, 730],
        'log',
    ) == pytest.approx(
        (10, 1000)
    )


def test_tight_threshold_log_row_stays_local():
    assert nice_y_limits(
        [0.023, 0.028, 0.031, 0.036],
        'log',
    ) == pytest.approx(
        (0.02, 0.05)
    )


def test_linear_row_rounds_outward_from_current_values():
    lo, hi = nice_y_limits(
        [-0.37, -0.11, 0.08, 0.46],
        'linear',
    )

    assert lo < -0.37
    assert hi > 0.46
    assert lo >= -1.0
    assert hi <= 1.0
