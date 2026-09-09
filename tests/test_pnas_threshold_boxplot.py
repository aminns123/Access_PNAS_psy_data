import numpy as np
import pandas as pd
import pytest

from psyview.plotting.axes import padded_limits
from psyview.plotting.pnas_plots import (
    pnas_threshold_box_plot,
)


def test_pnas_spatial_frequency_uses_single_threshold_box():
    stairs = pd.DataFrame({
        'spatial_frequency_cpd': [4.0, 4.0, 4.0, 4.0],
        'threshold_last8_median': [0.02, 0.03, 0.04, 0.05],
        'included_in_primary_csf': [True, True, True, True],
    })

    trials = pd.DataFrame({
        'contrast_normalized_source': [
            0.005, 0.01, 0.02, 0.04, 0.08, 0.16
        ]
    })

    spec = pnas_threshold_box_plot(
        stairs,
        trials,
        {
            'participant_id': 'P01',
            'luminance_cd_m2': 50.0,
            'spatial_frequency_cpd': 4.0,
        },
    )

    # One repository-defined category => one box.
    assert spec.xticks == [(1.0, '4.0')]

    summary = spec.metadata['Box-plot groups']['4.0']
    assert summary['n_included'] == 4
    assert summary['median'] == pytest.approx(0.035)
    assert summary['mean'] == pytest.approx(0.035)

    # Same contextual y range as the underlying staircase trial values.
    assert spec.ylim == pytest.approx(
        padded_limits(
            trials.contrast_normalized_source,
            'log',
        )
    )

    assert (
        spec.metadata['Sensitivity from arithmetic mean threshold']
        == pytest.approx(1.0 / 0.035)
    )
