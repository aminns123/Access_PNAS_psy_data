import numpy as np
import pandas as pd

from psyview.plotting.lateral_plots import (
    lateral_threshold_box_plot,
)


def _stairs():
    return pd.DataFrame({
        'staircase_id': ['S1', 'S2', 'S3', 'S4'],
        'threshold_last_five': [0.02, 0.03, 0.04, 0.05],
        'included_for_baseline_candidate': [True, True, True, True],
    })


def test_lateral_experiment_plot_is_threshold_box():
    spec = lateral_threshold_box_plot(
        _stairs(),
        {
            'participant_id': 'P01',
            'luminance_label_cd_m2': 50,
            'probe_position_deg': 0.1,
            'experiment': 'base',
        },
    )

    assert spec.metadata['Included staircases'] == 4
    assert spec.metadata['Median threshold'] == 0.035
    assert spec.metadata['Arithmetic mean threshold'] == 0.035
    assert any(
        series.label == 'Q1–Q3 box'
        for series in spec.series
    )
    assert any(
        series.label == 'Included staircase thresholds'
        for series in spec.series
    )


def test_box_ignores_excluded_staircase_in_summary():
    frame = _stairs()
    frame.loc[3, 'included_for_baseline_candidate'] = False

    spec = lateral_threshold_box_plot(
        frame,
        {
            'participant_id': 'P01',
            'luminance_label_cd_m2': 50,
            'probe_position_deg': 0.1,
            'experiment': 'base',
        },
    )

    assert spec.metadata['Included staircases'] == 3
    assert spec.metadata['Excluded staircases'] == 1
    assert spec.metadata['Arithmetic mean threshold'] == np.mean(
        [0.02, 0.03, 0.04]
    )
