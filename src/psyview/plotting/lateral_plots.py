"""Scientific plot specifications for the lateral-sensitivity archive."""
from __future__ import annotations

import numpy as np

from ..models import PlotSpec, Series
from .axes import finite


def subject_isf_plot(frame, filters):
    frame = frame.copy()
    participant = filters['participant_id']
    retained = frame.loc[
        frame.isf_estimate_cpd.notna()
        & frame.isf_lower_cpd.notna()
        & frame.isf_upper_cpd.notna()
    ].sort_values(['luminance_label_cd_m2', 'candidate_mode'])

    diagnostic = (
        not retained.empty
        and not bool(
            retained.included_in_thesis_main_isf.astype(bool).all()
        )
    )
    missing = frame.loc[
        frame.isf_estimate_cpd.isna(), 'condition_id'
    ].nunique()

    spec = PlotSpec(
        f'{participant} — archived ISF endpoints vs luminance',
        'Luminance (cd/m²)',
        'Intrinsic spatial frequency (cpd)',
        xscale='log',
        notes=(
            'Archived retained candidate medians with within-candidate '
            '0.5th–99.5th percentile endpoints; estimator-stability ranges, '
            'not population confidence intervals.'
            + (
                ' Subject is marked diagnostic/not included in thesis main ISF.'
                if diagnostic
                else ''
            )
        ),
        metadata={
            **filters,
            'Retained endpoint rows': len(retained),
            'Conditions with no retained mode': int(missing),
            'Source': 'isf_endpoints.csv',
        },
    )

    for index, row in enumerate(retained.itertuples()):
        dominant = bool(row.dominant_retained_mode)
        color = 'yellow' if dominant else 'cyan'
        spec.series.append(
            Series(
                [row.luminance_label_cd_m2, row.luminance_label_cd_m2],
                [row.isf_lower_cpd, row.isf_upper_cpd],
                '0.5–99.5 percentile endpoints' if index == 0 else '',
                color='blue',
            )
        )
        spec.series.append(
            Series(
                [row.luminance_label_cd_m2],
                [row.isf_estimate_cpd],
                'Dominant retained mode' if dominant else 'Other retained mode',
                'scatter',
                color,
                marker='◆' if dominant else '●',
            )
        )
    return spec


def lateral_profile_plot(frame, filters, *, notes_prefix=''):
    frame = frame.sort_values('distance_from_flanker_edge_deg').copy()
    title = (
        f"{filters['participant_id']} — "
        f"{filters['luminance_label_cd_m2']:g} cd/m² — lateral sensitivity"
    )
    spec = PlotSpec(
        title,
        'Distance from flanker edge (deg)',
        'ln(S_flanker / S_base)',
        notes=(
            notes_prefix
            + 'R(x) = ln(S_flanker / S_base). Error-bar half-width is '
              'spread/2 following the archived plotting convention; spread '
              'is a pairwise staircase sample SD, not a confidence interval.'
        ),
        metadata={
            **filters,
            'Profile positions': int(len(frame)),
            'Source': 'lateral_profiles_recomputed.csv',
        },
    )
    spec.series.append(
        Series(
            frame.distance_from_flanker_edge_deg.tolist(),
            frame.log_sensitivity_ratio.tolist(),
            'Lateral sensitivity',
            'scatter',
            'cyan',
        )
    )
    for index, row in enumerate(frame.itertuples()):
        if finite(row.spread) and finite(row.log_sensitivity_ratio):
            half = float(row.spread) / 2.0
            spec.series.append(
                Series(
                    [row.distance_from_flanker_edge_deg] * 2,
                    [
                        row.log_sensitivity_ratio - half,
                        row.log_sensitivity_ratio + half,
                    ],
                    'spread / 2' if index == 0 else '',
                    color='blue',
                )
            )
    spec.series.append(
        Series([], [0.0], 'No lateral modulation', 'hline', 'white', True)
    )
    return spec


def position_comparison_plot(row, filters, *, notes_prefix=''):
    title = (
        f"{filters['participant_id']} — "
        f"{filters['luminance_label_cd_m2']:g} cd/m² — "
        f"position {filters['probe_position_deg']:g}°"
    )
    metadata = {
        **filters,
        'Distance from flanker edge (deg)': row.distance_from_flanker_edge_deg,
        'Base threshold': row.base_threshold,
        'Flanker threshold': row.flanker_threshold,
        'Base sensitivity': row.base_sensitivity,
        'Flanker sensitivity': row.flanker_sensitivity,
        'ln(S_flanker/S_base)': row.log_sensitivity_ratio,
        'Pairwise spread': row.spread,
        'Base staircases': row.base_staircases,
        'Flanker staircases': row.flanker_staircases,
    }
    spec = PlotSpec(
        title,
        'Experiment index (1 = base, 2 = flanker)',
        'Sensitivity (1 / normalized contrast)',
        notes=(
            notes_prefix
            + 'This view exposes the two component sensitivities underlying '
              'the selected lateral-profile point.'
        ),
        metadata=metadata,
    )
    x = [1.0, 2.0]
    y = [row.base_sensitivity, row.flanker_sensitivity]
    spec.series.append(Series(x, y, 'Base → Flanker', color='blue'))
    spec.series.append(
        Series(x, y, 'Base / Flanker sensitivity', 'scatter', 'cyan')
    )
    return spec



def lateral_threshold_box_plot(
    stairs,
    filters,
    *,
    threshold_column='threshold_last_five',
    notes_prefix='',
):
    """Descriptive box plot of staircase thresholds for one experiment.

    The box uses raw threshold quartiles. Whiskers show the observed minimum
    and maximum because there are usually only a few staircases at a position.
    The arithmetic mean is shown separately because THAT is the quantity used
    in the lateral sensitivity calculation.
    """
    title = (
        f"{filters['participant_id']} — "
        f"{filters['luminance_label_cd_m2']:g} cd/m² — "
        f"{filters['probe_position_deg']:g}° — "
        f"{filters['experiment']} — staircase thresholds"
    )

    if threshold_column not in stairs:
        raise ValueError(
            f'Missing threshold column: {threshold_column}'
        )

    finite_threshold = np.isfinite(
        stairs[threshold_column]
        .to_numpy(dtype=float)
    ) & (
        stairs[threshold_column]
        .to_numpy(dtype=float)
        > 0
    )

    included_mask = (
        stairs.included_for_baseline_candidate
        .astype(bool)
        .to_numpy()
    )

    included = (
        stairs.loc[
            finite_threshold
            & included_mask,
            threshold_column,
        ]
        .to_numpy(dtype=float)
    )

    excluded = (
        stairs.loc[
            finite_threshold
            & ~included_mask,
            threshold_column,
        ]
        .to_numpy(dtype=float)
    )

    if len(included) == 0:
        raise ValueError(
            'No included finite staircase thresholds '
            'are available for this selection.'
        )

    q1, median, q3 = np.percentile(
        included,
        [25, 50, 75],
        method='linear',
    )
    minimum = float(np.min(included))
    maximum = float(np.max(included))
    mean = float(np.mean(included))

    left = 0.84
    right = 1.16
    cap_left = 0.94
    cap_right = 1.06

    spec = PlotSpec(
        title,
        '',
        'Staircase threshold (normalized digital contrast)',
        yscale='log',
        notes=(
            notes_prefix
            + 'Descriptive box plot of the included staircase thresholds. '
              'Box = Q1–Q3; centre line = median; whiskers = observed min–max. '
              'The diamond is the arithmetic mean threshold actually used '
              'to compute sensitivity. Individual staircase thresholds are '
              'shown as points. This is not a confidence interval.'
        ),
        metadata={
            **filters,
            'Included staircases': int(len(included)),
            'Excluded staircases': int(len(excluded)),
            'Minimum threshold': minimum,
            'Q1 threshold': float(q1),
            'Median threshold': float(median),
            'Q3 threshold': float(q3),
            'Maximum threshold': maximum,
            'Arithmetic mean threshold': mean,
            'Sensitivity from mean threshold': float(1.0 / mean),
        },
    )

    # Whisker.
    spec.series.append(
        Series(
            [1.0, 1.0],
            [minimum, maximum],
            'Observed min–max',
            color='blue',
        )
    )
    spec.series.append(
        Series(
            [cap_left, cap_right],
            [minimum, minimum],
            '',
            color='blue',
        )
    )
    spec.series.append(
        Series(
            [cap_left, cap_right],
            [maximum, maximum],
            '',
            color='blue',
        )
    )

    # Q1–Q3 box.
    spec.series.append(
        Series(
            [left, left],
            [float(q1), float(q3)],
            'Q1–Q3 box',
            color='cyan',
        )
    )
    spec.series.append(
        Series(
            [right, right],
            [float(q1), float(q3)],
            '',
            color='cyan',
        )
    )
    spec.series.append(
        Series(
            [left, right],
            [float(q1), float(q1)],
            '',
            color='cyan',
        )
    )
    spec.series.append(
        Series(
            [left, right],
            [float(q3), float(q3)],
            '',
            color='cyan',
        )
    )

    # Median.
    spec.series.append(
        Series(
            [left, right],
            [float(median), float(median)],
            'Median',
            color='white',
        )
    )

    # Individual included thresholds, lightly spread in x only to make
    # overlapping points visible. Their scientific y values are unchanged.
    if len(included) == 1:
        x_points = [1.0]
    else:
        x_points = np.linspace(
            0.94,
            1.06,
            len(included),
        ).tolist()

    spec.series.append(
        Series(
            x_points,
            included.tolist(),
            'Included staircase thresholds',
            'scatter',
            'cyan',
            marker='●',
        )
    )

    # Arithmetic mean: this is the actual aggregator used downstream.
    spec.series.append(
        Series(
            [1.0],
            [mean],
            'Arithmetic mean threshold',
            'scatter',
            'yellow',
            marker='◆',
        )
    )

    # Preserve excluded observations visibly without letting them define the box.
    if len(excluded):
        if len(excluded) == 1:
            x_excluded = [1.12]
        else:
            x_excluded = np.linspace(
                1.10,
                1.18,
                len(excluded),
            ).tolist()

        spec.series.append(
            Series(
                x_excluded,
                excluded.tolist(),
                'Excluded staircase thresholds',
                'scatter',
                'red',
                marker='×',
            )
        )

    return spec


def lateral_staircase_plot(stairs, trials, reversals, filters):
    individual = 'staircase_id' in filters
    title = (
        f"{filters['participant_id']} — "
        f"{filters['luminance_label_cd_m2']:g} cd/m² — "
        f"{filters['probe_position_deg']:g}° — "
        f"{filters['experiment']}"
    )
    title += (
        f" — {filters['staircase_id']}"
        if individual
        else ' — all staircases'
    )

    included = (
        int(stairs.included_for_baseline_candidate.astype(bool).sum())
        if len(stairs)
        else 0
    )
    metadata = {
        **filters,
        'Staircases': int(len(stairs)),
        'Included': included,
        'Excluded': int(len(stairs) - included),
        'Sources': (
            'staircase_thresholds.csv; staircase_summary.csv; '
            'staircase_trials.csv.gz; staircase_reversals.csv'
        ),
    }

    if individual and not stairs.empty:
        row = stairs.iloc[0]
        for column in (
            'detected_reversals',
            'trials_recorded',
            'trials_used',
            'threshold_last_five',
            'included_for_baseline_candidate',
            'distance_from_flanker_edge_deg',
        ):
            if column in row.index:
                metadata[column] = row[column]
        if not bool(row.included_for_baseline_candidate):
            metadata['Exclusion status'] = (
                'Excluded under the baseline candidate reproducing archived input zero.'
            )

    spec = PlotSpec(
        title,
        'Trial within staircase (0-based)',
        'Normalized digital contrast',
        yscale='log',
        notes=(
            'Archived trial trajectory and detected reversals. Diamonds mark '
            'the final five reversals used by the archived geometric-mean '
            'threshold. Excluded staircases remain visible.'
        ),
        metadata=metadata,
    )

    palette = ['cyan', 'blue', 'green', 'magenta', 'yellow', 'white']
    for index, row in enumerate(stairs.itertuples()):
        included_row = bool(row.included_for_baseline_candidate)
        color = (
            palette[index % len(palette)]
            if included_row
            else 'red'
        )
        label = (
            str(row.staircase_id)
            + ('' if included_row else ' [EXCLUDED]')
        )

        part = trials.loc[
            trials.staircase_id.eq(row.staircase_id)
        ].sort_values('trial_within_staircase')
        rv = reversals.loc[
            reversals.staircase_id.eq(row.staircase_id)
        ].sort_values('reversal_index')

        spec.series.append(
            Series(
                part.trial_within_staircase.tolist(),
                part.normalized_contrast.tolist(),
                label,
                color=color,
                dashed=not included_row,
            )
        )

        earlier = rv.loc[~rv.used_in_final_five.astype(bool)]
        final = rv.loc[rv.used_in_final_five.astype(bool)]

        spec.series.append(
            Series(
                earlier.trial_within_staircase.tolist(),
                earlier.normalized_contrast.tolist(),
                'Detected reversals' if individual else '',
                'scatter',
                color,
                marker='●',
            )
        )
        spec.series.append(
            Series(
                final.trial_within_staircase.tolist(),
                final.normalized_contrast.tolist(),
                'Final five' if individual else '',
                'scatter',
                'yellow' if individual else color,
                marker='◆',
            )
        )

        threshold = getattr(row, 'threshold_last_five', None)
        if individual and finite(threshold):
            spec.series.append(
                Series(
                    [],
                    [float(threshold)],
                    'Archived geometric-mean threshold',
                    'hline',
                    color,
                    True,
                )
            )
    return spec
