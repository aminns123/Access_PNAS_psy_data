import numpy as np
import pytest

from psyview.plotting.pnas_plots import (
    csf_staircase_variability,
)


def test_archived_csf_errorbars_match_threshold_sd(adapter):
    psf = adapter.table('psf').iloc[0]
    stairs = adapter.table('stairs').loc[
        lambda frame:
            frame.condition_id.eq(psf.condition_id)
    ]

    variability = csf_staircase_variability(stairs)
    assert variability

    first = variability[0]
    sf = first['spatial_frequency_cpd']
    values = stairs.loc[
        stairs.spatial_frequency_cpd.eq(sf)
        & stairs.included_in_primary_csf,
        'threshold_last8_median',
    ].to_numpy(dtype=float)

    mean_t = np.mean(values)
    sd_t = np.std(values, ddof=1)

    assert first['mean_threshold'] == pytest.approx(mean_t)
    assert first['sd_threshold'] == pytest.approx(sd_t)
    assert first['lower_sensitivity'] == pytest.approx(
        1 / (mean_t + sd_t)
    )

    if mean_t > sd_t:
        assert first['upper_sensitivity'] == pytest.approx(
            1 / (mean_t - sd_t)
        )


def test_archived_csf_plot_contains_variability_bars(adapter):
    psf = adapter.table('psf').iloc[0]
    filters = {
        'participant_id': psf.participant_id,
        'luminance_cd_m2': psf.luminance_cd_m2,
    }
    spec = adapter.get_plot(1, filters)

    bars = [
        series
        for series in spec.series
        if series.label == 'Across-staircase threshold SD'
    ]
    assert len(bars) == 1
    assert len(bars[0].x) == 2
    assert bars[0].x[0] == bars[0].x[1]
    assert bars[0].y[0] < bars[0].y[1]

    assert (
        spec.metadata['CSF error bars']
        == 'threshold mean ± 1 sample SD, reciprocal-transformed'
    )
