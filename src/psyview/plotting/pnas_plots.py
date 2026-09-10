import numpy as np

from ..models import PlotSpec, Series
from .axes import finite
from .boxplots import grouped_box_plot


def csf_staircase_variability(stairs, threshold_column='threshold_last8_median'):
    """Return descriptive CSF error-bar bounds from staircase thresholds.

    The archived CSF point is:
        S = 1 / mean(T_i)

    where T_i is the included per-staircase threshold at one spatial
    frequency.  PsyView displays descriptive variability by taking the sample
    SD of those threshold estimates and mapping mean(T) ± SD(T) through the
    same reciprocal transform.

    This is deliberately labelled as across-staircase threshold variability;
    it is not a population confidence interval and is not part of the archived
    PSF resampling interval.
    """
    if stairs is None or stairs.empty or threshold_column not in stairs:
        return []

    results = []
    included = stairs.loc[
        stairs.included_in_primary_csf.astype(bool)
    ].copy()

    for spatial_frequency, group in included.groupby('spatial_frequency_cpd'):
        values = group[threshold_column].to_numpy(dtype=float)
        values = values[np.isfinite(values) & (values > 0)]

        if len(values) < 2:
            continue

        mean_threshold = float(np.mean(values))
        sd_threshold = float(np.std(values, ddof=1))
        lower_sensitivity = 1.0 / (mean_threshold + sd_threshold)

        # In ordinary data SD < mean because thresholds are strictly positive.
        # If an extreme sample violates this, use the largest observed
        # staircase sensitivity rather than manufacturing an infinite bound.
        if mean_threshold > sd_threshold:
            upper_sensitivity = 1.0 / (mean_threshold - sd_threshold)
            upper_status = 'reciprocal(mean threshold - SD)'
        else:
            upper_sensitivity = float(np.max(1.0 / values))
            upper_status = 'max observed staircase sensitivity (mean-SD <= 0)'

        results.append({
            'spatial_frequency_cpd': float(spatial_frequency),
            'mean_threshold': mean_threshold,
            'sd_threshold': sd_threshold,
            'n_staircases': int(len(values)),
            'lower_sensitivity': lower_sensitivity,
            'upper_sensitivity': upper_sensitivity,
            'upper_status': upper_status,
        })

    return results


def add_csf_variability_bars(spec, variability, label='Across-staircase threshold SD'):
    for index, row in enumerate(variability):
        spec.series.append(
            Series(
                [row['spatial_frequency_cpd']] * 2,
                [row['lower_sensitivity'], row['upper_sensitivity']],
                label if index == 0 else '',
                color='white',
                role='uncertainty',
            )
        )
    return spec


def subject_plot(frame, filters):
    frame = frame.sort_values('luminance_cd_m2')
    spec = PlotSpec(
        f"{filters['participant_id']} — Preferred spatial frequency vs luminance",
        'Luminance (cd/m²)',
        'Preferred spatial frequency (cpd)',
        xscale='log',
        notes='Archived mean and 2.5th–97.5th percentiles of retained saved fits.',
        metadata={
            **filters,
            'Luminance conditions': len(frame),
            'Source': 'preferred_frequency.csv',
        },
    )
    spec.series.append(
        Series(
            frame.luminance_cd_m2.tolist(),
            frame.f_pref_mean_cpd.tolist(),
            'Archived mean',
            'scatter',
        )
    )
    for i, row in enumerate(frame.itertuples()):
        spec.series.append(
            Series(
                [row.luminance_cd_m2] * 2,
                [row.percentile_2_5_cpd, row.percentile_97_5_cpd],
                '2.5–97.5 percentiles' if i == 0 else '',
                color='blue',
                role='uncertainty',
            )
        )
    return spec


def csf_plot(frame, psf, filters, curves, note, stairs=None):
    variability = csf_staircase_variability(stairs)

    spec = PlotSpec(
        (
            f"{filters['participant_id']} — {psf.luminance_cd_m2:g} cd/m² "
            f"— CSF — f_pref = {psf.f_pref_mean_cpd:.5g} cpd"
        ),
        'Spatial frequency (cpd)',
        'Contrast sensitivity (1 / normalized source contrast)',
        xscale='log',
        yscale='log',
        notes=(
            note
            + ' Error bars: descriptive across-staircase variability. '
              'For each spatial frequency, PsyView takes the sample SD of '
              'the included final-eight staircase thresholds and maps '
              'mean threshold ± 1 SD through sensitivity = 1/threshold. '
              'These bars are not confidence intervals.'
        ),
        metadata={
            **filters,
            'Spatial-frequency conditions': frame.spatial_frequency_cpd.nunique(),
            'Archived f_pref (cpd)': psf.f_pref_mean_cpd,
            'CSF error bars': 'threshold mean ± 1 sample SD, reciprocal-transformed',
            'Sources': (
                'csf_thresholds.csv; staircase_summary.csv; '
                'preferred_frequency.csv; csf_curves_recomputed.csv'
            ),
        },
    )

    for included, label, color in [
        (True, 'Included in fit', 'cyan'),
        (False, 'Excluded from fit', 'red'),
    ]:
        part = frame.loc[frame.included_in_csf_fit.eq(included)]
        if not part.empty:
            spec.series.append(
                Series(
                    part.spatial_frequency_cpd.tolist(),
                    part.contrast_sensitivity.tolist(),
                    label,
                    'scatter',
                    color,
                )
            )

    add_csf_variability_bars(spec, variability)

    if curves is not None:
        spec.series.append(
            Series(
                curves.spatial_frequency_cpd.tolist(),
                curves.contrast_sensitivity.tolist(),
                'Current-helper curve (archived)',
                color='red',
                role='fit',
            )
        )

    spec.series.append(
        Series(
            [psf.f_pref_mean_cpd],
            [],
            'Archived mean f_pref',
            'vline',
            'yellow',
            True,
            role='reference',
        )
    )
    return spec



def pnas_threshold_box_plot(
    stairs,
    trials,
    filters,
    *,
    threshold_column='threshold_last8_median',
    notes_prefix='',
):
    """Single threshold-distribution box for the selected CSF frequency.

    This is the same generic grouped-box machinery used by the lateral adapter.
    The category is the repository's spatial-frequency column; after the user
    selects one frequency, it naturally contains one category and therefore
    renders one box.
    """
    participant = filters['participant_id']
    luminance = filters['luminance_cd_m2']
    frequency = filters['spatial_frequency_cpd']

    spec = grouped_box_plot(
        stairs,
        category_column='spatial_frequency_cpd',
        value_column=threshold_column,
        included_column='included_in_primary_csf',
        title=(
            f'{participant} — {luminance:g} cd/m² — '
            f'{frequency:g} cpd — staircase thresholds'
        ),
        xlabel='Spatial frequency (cpd)',
        ylabel='Staircase threshold (normalized source contrast)',
        yscale='log',
        reference_values=None,
        notes_prefix=(
            notes_prefix
            + 'The y-axis is set from the minimum and maximum staircase '
              'thresholds at this selected spatial frequency with a small '
              'display margin. '
        ),
        metadata={
            **filters,
            'Y-axis basis':
                'current-row staircase threshold range',
        },
        mean_label='Arithmetic mean threshold',
    )

    groups = spec.metadata.get('Box-plot groups', {})
    if len(groups) == 1:
        summary = next(iter(groups.values()))
        mean_threshold = summary.get('mean')
        if mean_threshold is not None and mean_threshold > 0:
            spec.metadata['Sensitivity from arithmetic mean threshold'] = (
                1.0 / float(mean_threshold)
            )

    return spec

def staircase_plot(stairs, trials, reversals, filters, csf):
    individual = 'staircase_id' in filters
    title = (
        f"{filters['participant_id']} — "
        f"{filters['luminance_cd_m2']:g} cd/m² — "
        f"{filters['spatial_frequency_cpd']:g} cpd"
    )
    title += (
        f" — {filters['staircase_id']}"
        if individual
        else ' — All staircases'
    )

    included = int(stairs.included_in_primary_csf.sum())
    metadata = {
        **filters,
        'Staircases': len(stairs),
        'Included': included,
        'Excluded': len(stairs) - included,
    }

    if not csf.empty:
        metadata['Archived aggregate threshold'] = (
            csf.iloc[0].contrast_threshold
        )
        metadata['Archived CSF sensitivity'] = (
            csf.iloc[0].contrast_sensitivity
        )

    if individual and not stairs.empty:
        row = stairs.iloc[0]
        for column in [
            'n_trials',
            'n_trials_used',
            'n_detected_reversals',
            'threshold_last8_median',
            'included_in_primary_csf',
        ]:
            metadata[column] = row.get(column)

    excluded = stairs.loc[
        ~stairs.included_in_primary_csf
    ]
    if not excluded.empty:
        metadata['Exclusion reason'] = '; '.join(
            f'{row.staircase_id}: {row.exclusion_reason}'
            for row in excluded.itertuples()
        )

    metadata['Sources'] = (
        'staircase_summary.csv; trials.csv.gz; '
        'staircase_reversals.csv; csf_thresholds.csv'
    )

    spec = PlotSpec(
        title,
        'Trial within staircase (1-based)',
        'Normalized source contrast',
        yscale='log',
        metadata=metadata,
        notes=(
            'Archived trials, detected reversals and thresholds. '
            'Final eight highlighted. All recorded trials shown; primary '
            'analysis uses n_trials_used. Excluded trajectories are labelled EXCLUDED.'
        ),
    )

    palette = [
        'cyan',
        'blue',
        'green',
        'magenta',
        'yellow',
        'white',
    ]

    for index, row in enumerate(stairs.itertuples()):
        color = (
            palette[index % len(palette)]
            if row.included_in_primary_csf
            else 'red'
        )
        label = (
            str(row.staircase_id)
            + (
                ''
                if row.included_in_primary_csf
                else ' [EXCLUDED]'
            )
        )

        part = trials.loc[
            trials.staircase_id.eq(row.staircase_id)
        ].sort_values('trial_within_staircase')
        rv = reversals.loc[
            reversals.staircase_id.eq(row.staircase_id)
        ]

        spec.series.append(
            Series(
                part.trial_within_staircase.tolist(),
                part.contrast_normalized_source.tolist(),
                label,
                color=color,
                dashed=not row.included_in_primary_csf,
            )
        )

        for last, marker_color, suffix in [
            (False, color, 'reversals'),
            (
                True,
                'yellow' if individual else color,
                'final eight',
            ),
        ]:
            points = rv.loc[
                rv.in_last8_point_estimate.eq(last)
            ]
            spec.series.append(
                Series(
                    points.trial_within_staircase.tolist(),
                    points.contrast_normalized_source.tolist(),
                    suffix if individual else '',
                    'scatter',
                    marker_color,
                    marker='◆' if last else '●',
                )
            )

        threshold = getattr(
            row,
            'threshold_last8_median',
            None,
        )
        if finite(threshold):
            spec.series.append(
                Series(
                    [],
                    [threshold],
                    (
                        'Archived threshold'
                        if individual
                        else ''
                    ),
                    'hline',
                    color,
                    True,
                    role='reference',
                )
            )

    return spec
