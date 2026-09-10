import pandas as pd
import pytest

from psyview.plotting.axes import padded_limits
from psyview.plotting.boxplots import grouped_box_plot


def test_boxplot_ylim_uses_current_row_threshold_extremes():
    frame = pd.DataFrame({
        'group': ['base'] * 4 + ['flanker'] * 4,
        'threshold': [
            0.020, 0.025, 0.030, 0.035,
            0.040, 0.045, 0.050, 0.060,
        ],
        'included': [True] * 8,
    })

    # Deliberately huge raw/reference range: it must no longer control ylim.
    raw_trial_values = [0.001, 0.5]

    spec = grouped_box_plot(
        frame,
        category_column='group',
        value_column='threshold',
        included_column='included',
        title='test',
        xlabel='Group',
        ylabel='Threshold',
        yscale='log',
        reference_values=raw_trial_values,
    )

    expected = padded_limits(
        frame.threshold,
        'log',
        fraction=.07,
    )

    assert spec.ylim == pytest.approx(expected)
    assert spec.ylim[0] < frame.threshold.min()
    assert spec.ylim[1] > frame.threshold.max()
    assert spec.ylim[0] > min(raw_trial_values)
    assert spec.ylim[1] < max(raw_trial_values)


def test_excluded_visible_threshold_is_included_in_axis_range():
    frame = pd.DataFrame({
        'group': ['base'] * 4,
        'threshold': [0.02, 0.03, 0.04, 0.08],
        'included': [True, True, True, False],
    })

    spec = grouped_box_plot(
        frame,
        category_column='group',
        value_column='threshold',
        included_column='included',
        title='test',
        xlabel='Group',
        ylabel='Threshold',
        yscale='log',
    )

    # The excluded 0.08 point is still plotted red, so the axis must contain it.
    assert spec.ylim[1] > 0.08
