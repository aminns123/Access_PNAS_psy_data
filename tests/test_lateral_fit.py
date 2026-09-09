import numpy as np
import pandas as pd
import pytest

from psyview.analysis.lateral_fit import (
    fit_lateral_profile,
    green_function_distance,
)


def test_diagnostic_fit_recovers_synthetic_frequency():
    x = np.linspace(
        0.02,
        0.9,
        18,
    )
    true = {
        'amplitude': -0.35,
        'phase_rad': 0.35,
        'frequency_cpd': 3.2,
        'decay_per_deg': 0.45,
    }
    y = green_function_distance(
        x,
        true['amplitude'],
        true['phase_rad'],
        true['frequency_cpd'],
        true['decay_per_deg'],
    )

    frame = pd.DataFrame({
        'distance_from_flanker_edge_deg': x,
        'log_sensitivity_ratio': y,
        'spread': np.full_like(x, 0.15),
    })

    result = fit_lateral_profile(
        frame
    )
    assert (
        result.frequency_cpd
        == pytest.approx(
            true['frequency_cpd'],
            abs=0.08,
        )
    )
    assert result.rmse < 1e-4
    assert (
        result.frequency_match_score
        > 0.99
    )


def test_fit_uses_sigma_floor_for_missing_or_small_spread():
    x = np.linspace(
        0.02,
        0.9,
        12,
    )
    y = green_function_distance(
        x,
        -0.2,
        0.1,
        2.4,
        0.3,
    )
    spread = np.array(
        [0.0, np.nan] + [0.02] * 10
    )

    frame = pd.DataFrame({
        'distance_from_flanker_edge_deg': x,
        'log_sensitivity_ratio': y,
        'spread': spread,
    })

    result = fit_lateral_profile(
        frame
    )
    assert result.sigma_floor == 0.05
    assert np.isfinite(
        result.frequency_cpd
    )
