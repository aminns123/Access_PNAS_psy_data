"""On-demand diagnostic fitting for lateral-sensitivity profiles.

This module computes a NEW fit to the currently displayed profile. It does not
claim to reproduce a historical saved-fit row or the archived ISF estimator.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from scipy.optimize import least_squares


@dataclass(frozen=True)
class LateralFitResult:
    x_curve: list[float]
    y_curve: list[float]
    amplitude: float
    phase_rad: float
    frequency_cpd: float
    k_rad_per_deg: float
    decay_per_deg: float
    rmse: float
    weighted_rms: float
    r_squared: float
    frequency_match_score: float
    n_points: int
    excluded_points: int
    sigma_floor: float


def green_function_distance(
    distance_from_flanker_edge_deg,
    amplitude,
    phase_rad,
    frequency_cpd,
    decay_per_deg,
):
    """Thesis Eq. B.25 written directly in flanker-edge coordinates."""
    x = np.asarray(distance_from_flanker_edge_deg, dtype=float)
    k = 2.0 * np.pi * float(frequency_cpd)
    return (
        float(amplitude)
        * np.exp(-float(decay_per_deg) * np.abs(x))
        * (
            np.cos(k * x + float(phase_rad))
            - np.sign(x) * np.sin(k * x + float(phase_rad))
        )
    )


def frequency_match_score(x, y, params):
    """Author-style amplitude-spectrum cosine similarity diagnostic."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    fitted = green_function_distance(x, *params)

    freq_data = np.abs(np.fft.rfft(y))
    freq_fit = np.abs(np.fft.rfft(fitted))

    data_max = float(np.max(freq_data)) if len(freq_data) else 0.0
    fit_max = float(np.max(freq_fit)) if len(freq_fit) else 0.0
    if data_max <= 0 or fit_max <= 0:
        return float('nan')

    freq_data /= data_max
    freq_fit /= fit_max

    denominator = float(
        np.linalg.norm(freq_data) * np.linalg.norm(freq_fit)
    )
    if denominator <= 0:
        return float('nan')

    return float(
        np.dot(freq_data, freq_fit) / denominator
    )


def _is_excluded(value, excluded_x):
    return any(
        math.isclose(
            float(value),
            float(excluded),
            rel_tol=0.0,
            abs_tol=1e-10,
        )
        for excluded in excluded_x
    )


def _clean_profile(frame, sigma_floor, excluded_x):
    required = (
        'distance_from_flanker_edge_deg',
        'log_sensitivity_ratio',
        'spread',
    )
    missing = [
        column
        for column in required
        if column not in frame
    ]
    if missing:
        raise ValueError(
            'Profile is missing fit columns: '
            + ', '.join(missing)
        )

    x_all = frame.distance_from_flanker_edge_deg.to_numpy(dtype=float)
    y_all = frame.log_sensitivity_ratio.to_numpy(dtype=float)
    spread_all = frame.spread.to_numpy(dtype=float)

    finite_mask = np.isfinite(x_all) & np.isfinite(y_all)
    exclusion_mask = np.array(
        [
            _is_excluded(value, excluded_x)
            for value in x_all
        ],
        dtype=bool,
    )
    mask = finite_mask & ~exclusion_mask

    x = x_all[mask]
    y = y_all[mask]
    spread = spread_all[mask]

    sigma = np.where(
        np.isfinite(spread),
        np.maximum(spread, sigma_floor),
        sigma_floor,
    )

    order = np.argsort(x)
    x = x[order]
    y = y[order]
    sigma = sigma[order]

    if len(x) < 5:
        raise ValueError(
            'At least five included finite profile points are required; '
            f'found {len(x)} after exclusions.'
        )

    return x, y, sigma, int(np.count_nonzero(finite_mask & exclusion_mask))


def fit_lateral_profile(
    frame,
    *,
    excluded_x=(),
    frequency_bounds=(0.5, 10.0),
    sigma_floor=0.05,
):
    """Fit Eq. B.25 using error-weighted nonlinear least squares.

    sigma_i = max(full recorded spread_i, 0.05)

    Because sigma is fixed with respect to the model parameters, minimizing
    the sum of squared standardized residuals is mathematically equivalent to
    maximizing an independent Gaussian likelihood.  The implementation uses
    SciPy least_squares for a stable, fast on-demand diagnostic fit.
    """
    x, y, sigma, excluded_count = _clean_profile(
        frame,
        sigma_floor,
        excluded_x,
    )

    lower_f, upper_f = map(float, frequency_bounds)
    if not 0 < lower_f < upper_f:
        raise ValueError(
            'frequency_bounds must satisfy 0 < low < high.'
        )

    lower = np.array(
        [-1.0, -np.pi, lower_f, 0.001],
        dtype=float,
    )
    upper = np.array(
        [1.0, np.pi, upper_f, 1.0],
        dtype=float,
    )

    peak_index = int(np.argmax(np.abs(y)))
    observed_sign = -1.0 if y[peak_index] < 0 else 1.0
    amplitude_size = float(
        np.clip(
            max(np.max(np.abs(y)), 0.05),
            0.05,
            0.8,
        )
    )

    frequency_starts = np.linspace(
        lower_f,
        upper_f,
        17,
    )
    phase_starts = (
        -np.pi / 2.0,
        0.0,
        np.pi / 2.0,
    )

    best = None
    best_cost = float('inf')

    def residuals(params):
        prediction = green_function_distance(
            x,
            *params,
        )
        return (
            prediction - y
        ) / sigma

    for frequency_start in frequency_starts:
        for phase_start in phase_starts:
            for sign in (
                observed_sign,
                -observed_sign,
            ):
                initial = np.array(
                    [
                        sign * amplitude_size,
                        phase_start,
                        frequency_start,
                        0.2,
                    ],
                    dtype=float,
                )
                try:
                    result = least_squares(
                        residuals,
                        initial,
                        bounds=(lower, upper),
                        method='trf',
                        max_nfev=2500,
                        xtol=1e-10,
                        ftol=1e-10,
                        gtol=1e-10,
                    )
                except (
                    ValueError,
                    FloatingPointError,
                ):
                    continue

                cost = float(
                    np.sum(
                        residuals(result.x) ** 2
                    )
                )
                if (
                    result.success
                    and np.all(
                        np.isfinite(result.x)
                    )
                    and np.isfinite(cost)
                    and cost < best_cost
                ):
                    best = result
                    best_cost = cost

    if best is None:
        raise RuntimeError(
            'No stable diagnostic fit was found.'
        )

    (
        amplitude,
        phase_rad,
        frequency_cpd,
        decay_per_deg,
    ) = map(float, best.x)

    k_rad_per_deg = (
        2.0
        * np.pi
        * frequency_cpd
    )

    fitted_at_data = green_function_distance(
        x,
        amplitude,
        phase_rad,
        frequency_cpd,
        decay_per_deg,
    )
    residual = y - fitted_at_data

    rmse = float(
        np.sqrt(
            np.mean(residual ** 2)
        )
    )
    weighted_rms = float(
        np.sqrt(
            np.mean(
                (residual / sigma) ** 2
            )
        )
    )

    total = float(
        np.sum(
            (y - np.mean(y)) ** 2
        )
    )
    r_squared = (
        float(
            1.0
            - np.sum(residual ** 2)
            / total
        )
        if total > 0
        else float('nan')
    )

    params = (
        amplitude,
        phase_rad,
        frequency_cpd,
        decay_per_deg,
    )
    fms = frequency_match_score(
        x,
        y,
        params,
    )

    x_curve = np.linspace(
        float(np.min(x)),
        float(np.max(x)),
        500,
    )
    y_curve = green_function_distance(
        x_curve,
        *params,
    )

    return LateralFitResult(
        x_curve=x_curve.tolist(),
        y_curve=y_curve.tolist(),
        amplitude=amplitude,
        phase_rad=phase_rad,
        frequency_cpd=frequency_cpd,
        k_rad_per_deg=float(k_rad_per_deg),
        decay_per_deg=decay_per_deg,
        rmse=rmse,
        weighted_rms=weighted_rms,
        r_squared=r_squared,
        frequency_match_score=fms,
        n_points=int(len(x)),
        excluded_points=excluded_count,
        sigma_floor=float(sigma_floor),
    )


def fit_display_text(result):
    fms = (
        f'{result.frequency_match_score:.3f}'
        if math.isfinite(result.frequency_match_score)
        else 'n/a'
    )
    r2 = (
        f'{result.r_squared:.3f}'
        if math.isfinite(result.r_squared)
        else 'n/a'
    )

    return (
        'INTERACTIVE / DIAGNOSTIC FIT — thesis Eq. B.25\n'
        'R(X)=A exp(-λ|X|)[cos(kX+φ) − sgn(X) sin(kX+φ)]\n'
        f'A={result.amplitude:.4g}  |  '
        f'φ={result.phase_rad:.4g} rad  |  '
        f'λ={result.decay_per_deg:.4g} deg⁻¹  |  '
        f'k={result.k_rad_per_deg:.4g} rad/deg  |  '
        f'fₙ={result.frequency_cpd:.4g} cpd  |  '
        f'FMS={fms}  |  R²={r2}  |  '
        f'RMSE={result.rmse:.4g}\n'
        f'Fit points={result.n_points}  |  '
        f'Excluded={result.excluded_points}  |  '
        'σ=max(full spread, 0.05)  |  '
        'weighted least-squares = Gaussian MLE for fixed σ'
    )
