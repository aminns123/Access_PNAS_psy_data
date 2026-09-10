"""Scientific plot specifications for the lateral-sensitivity archive."""
from __future__ import annotations

from ..models import PlotSpec, Series
from .axes import finite
from .boxplots import grouped_box_plot


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
                role='uncertainty',
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
                    role='uncertainty',
                )
            )
    spec.series.append(
        Series([], [0.0], 'No lateral modulation', 'hline', 'white', True,
               role='reference')
    )
    return spec



def lateral_grouped_threshold_box_plot(
    stairs,
    trials,
    filters,
    *,
    threshold_column='threshold_last_five',
    notes_prefix='',
    extra_metadata=None,
):
    """Repository-driven threshold distributions at Position/Experiment level."""
    participant = filters['participant_id']
    luminance = filters['luminance_label_cd_m2']
    position = filters['probe_position_deg']

    if 'experiment' in filters:
        title = (
            f'{participant} — {luminance:g} cd/m² — '
            f'{position:g}° — {filters["experiment"]} — staircase thresholds'
        )
    else:
        title = (
            f'{participant} — {luminance:g} cd/m² — '
            f'{position:g}° — staircase threshold distributions'
        )

    metadata = {
        **filters,
        **(extra_metadata or {}),
        'Y-axis basis':
            'current-row staircase threshold range',
    }

    return grouped_box_plot(
        stairs,
        category_column='experiment',
        value_column=threshold_column,
        included_column='included_for_baseline_candidate',
        title=title,
        xlabel='Experiment',
        ylabel='Staircase threshold (normalized digital contrast)',
        yscale='log',
        reference_values=None,
        notes_prefix=(
            notes_prefix
            + 'Category labels are read directly from the repository. '
              'The y-axis is set from the minimum and maximum staircase '
              'thresholds in this row with a small display margin. '
        ),
        metadata=metadata,
        mean_label='Arithmetic mean threshold',
    )


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
                    role='reference',
                )
            )
    return spec
