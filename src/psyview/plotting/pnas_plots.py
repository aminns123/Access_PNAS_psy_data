from ..models import PlotSpec, Series


def subject_plot(frame, filters):
    frame = frame.sort_values('luminance_cd_m2')
    spec = PlotSpec(f"{filters['participant_id']} — Preferred spatial frequency vs luminance", 'Luminance (cd/m²)', 'Preferred spatial frequency (cpd)', xscale='log', notes='Archived mean and 2.5th–97.5th percentiles of retained saved fits.', metadata={**filters, 'Luminance conditions': len(frame), 'Source': 'preferred_frequency.csv'})
    spec.series.append(Series(frame.luminance_cd_m2.tolist(), frame.f_pref_mean_cpd.tolist(), 'Archived mean', 'scatter'))
    for i, row in enumerate(frame.itertuples()):
        spec.series.append(Series([row.luminance_cd_m2]*2, [row.percentile_2_5_cpd, row.percentile_97_5_cpd], '2.5–97.5 percentiles' if i == 0 else '', color='blue'))
    return spec


def csf_plot(frame, psf, filters, curves, note):
    spec = PlotSpec(f"{filters['participant_id']} — {psf.luminance_cd_m2:g} cd/m² — CSF — f_pref = {psf.f_pref_mean_cpd:.5g} cpd", 'Spatial frequency (cpd)', 'Contrast sensitivity (1 / normalized source contrast)', xscale='log', yscale='log', notes=note, metadata={**filters, 'Spatial-frequency conditions': frame.spatial_frequency_cpd.nunique(), 'Archived f_pref (cpd)': psf.f_pref_mean_cpd, 'Sources': 'csf_thresholds.csv; preferred_frequency.csv; csf_curves_recomputed.csv'})
    for included, label, color in [(True, 'Included in fit', 'cyan'), (False, 'Excluded from fit', 'red')]:
        part = frame.loc[frame.included_in_csf_fit.eq(included)]
        if not part.empty:
            spec.series.append(Series(part.spatial_frequency_cpd.tolist(), part.contrast_sensitivity.tolist(), label, 'scatter', color))
    if curves is not None:
        spec.series.append(Series(curves.spatial_frequency_cpd.tolist(), curves.contrast_sensitivity.tolist(), 'Current-helper curve (archived)', color='blue'))
    spec.series.append(Series([psf.f_pref_mean_cpd], [], 'Archived mean f_pref', 'vline', 'yellow', True))
    return spec


def staircase_plot(stairs, trials, reversals, filters, csf):
    individual = 'staircase_id' in filters
    title = f"{filters['participant_id']} — {filters['luminance_cd_m2']:g} cd/m² — {filters['spatial_frequency_cpd']:g} cpd"
    title += f" — {filters['staircase_id']}" if individual else ' — All staircases'
    included = int(stairs.included_in_primary_csf.sum())
    metadata = {**filters, 'Staircases': len(stairs), 'Included': included, 'Excluded': len(stairs)-included}
    if not csf.empty:
        metadata['Archived aggregate threshold'] = csf.iloc[0].contrast_threshold
        metadata['Archived CSF sensitivity'] = csf.iloc[0].contrast_sensitivity
    if individual and not stairs.empty:
        row = stairs.iloc[0]
        for column in ['n_trials', 'n_trials_used', 'n_detected_reversals', 'threshold_last8_median', 'included_in_primary_csf']:
            metadata[column] = row[column]
    excluded = stairs.loc[~stairs.included_in_primary_csf]
    if not excluded.empty:
        metadata['Exclusion reason'] = '; '.join(f'{row.staircase_id}: {row.exclusion_reason}' for row in excluded.itertuples())
    metadata['Sources'] = 'staircase_summary.csv; trials.csv.gz; staircase_reversals.csv; csf_thresholds.csv'
    spec = PlotSpec(title, 'Trial within staircase (1-based)', 'Normalized source contrast', yscale='log', metadata=metadata, notes='Archived trials, detected reversals and thresholds. Final eight highlighted. All recorded trials shown; primary analysis uses n_trials_used. Excluded trajectories are labelled EXCLUDED.')
    palette = ['cyan', 'blue', 'green', 'magenta', 'yellow', 'white']
    for index, row in enumerate(stairs.itertuples()):
        color = palette[index % len(palette)] if row.included_in_primary_csf else 'red'
        label = row.staircase_id + ('' if row.included_in_primary_csf else ' [EXCLUDED]')
        part = trials.loc[trials.staircase_id.eq(row.staircase_id)].sort_values('trial_within_staircase')
        rv = reversals.loc[reversals.staircase_id.eq(row.staircase_id)]
        spec.series.append(Series(part.trial_within_staircase.tolist(), part.contrast_normalized_source.tolist(), label, color=color, dashed=not row.included_in_primary_csf))
        for last, marker_color, suffix in [(False, color, 'reversals'), (True, 'yellow' if individual else color, 'final eight')]:
            points = rv.loc[rv.in_last8_point_estimate.eq(last)]
            spec.series.append(Series(points.trial_within_staircase.tolist(), points.contrast_normalized_source.tolist(), suffix if individual else '', 'scatter', marker_color))
        spec.series.append(Series([], [row.threshold_last8_median], 'Archived threshold' if individual else '', 'hline', color, True))
    return spec
