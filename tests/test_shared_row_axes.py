from psyview.models import PlotSpec, Series
from psyview.plotting.axes import shared_axis_limits


def test_shared_y_limits_union_sibling_conditions():
    first = PlotSpec(
        'A',
        'x',
        'y',
        [
            Series(
                [1, 2, 3],
                [2.0, 4.0, 6.0],
                'data',
            )
        ],
    )

    second = PlotSpec(
        'B',
        'x',
        'y',
        [
            Series(
                [1, 2, 3],
                [1.0, 5.0, 9.0],
                'data',
            )
        ],
    )

    limits = shared_axis_limits(
        [first, second],
        'y',
    )

    assert limits[0] <= 1.0
    assert limits[1] >= 9.0


def test_shared_x_limits_union_sibling_conditions():
    first = PlotSpec(
        'A',
        'x',
        'y',
        [Series([1, 2], [4, 5], 'data')],
    )

    second = PlotSpec(
        'B',
        'x',
        'y',
        [Series([10, 20], [4, 5], 'data')],
    )

    limits = shared_axis_limits(
        [first, second],
        'x',
    )

    assert limits[0] < 1.0
    assert limits[1] > 20.0


def test_explicit_sibling_limits_are_respected_in_union():
    first = PlotSpec(
        'A',
        'x',
        'y',
        [Series([1], [2], 'data')],
        ylim=(0.0, 10.0),
    )

    second = PlotSpec(
        'B',
        'x',
        'y',
        [Series([1], [2], 'data')],
        ylim=(-5.0, 8.0),
    )

    assert shared_axis_limits(
        [first, second],
        'y',
    ) == (-5.0, 10.0)
