"""Read-only interactive final-N analysis for lateral sensitivity.

This recomputes staircase thresholds and deterministic lateral profiles from
the deposited detected reversals. It intentionally does not claim to
reconstruct a new historical ISF fit.
"""
from __future__ import annotations

import threading

import numpy as np
import pandas as pd

from ..data.base import DatasetError


class LateralInteractiveAnalysis:
    def __init__(self, adapter):
        self.adapter = adapter
        self.lock = threading.RLock()
        self.cache = {}

    def max_n(self):
        counts = (
            self.adapter.table('reversals')
            .groupby('staircase_id')
            .size()
        )
        return max(1, int(counts.max())) if len(counts) else 1

    def threshold(self, staircase_id, n):
        if not isinstance(n, int) or n < 1:
            raise ValueError('N must be a positive integer.')

        key = ('threshold', staircase_id, n)
        if key in self.cache:
            return dict(self.cache[key])

        rows = self.adapter.table('reversals').loc[
            lambda frame: frame.staircase_id.eq(staircase_id)
        ].sort_values('reversal_index')

        numeric = rows.normalized_contrast.to_numpy(dtype=float)
        valid = rows.loc[
            np.isfinite(numeric)
            & rows.normalized_contrast.gt(0)
        ]
        selected = valid.tail(n) if len(valid) >= n else valid.iloc[:0]

        if len(selected):
            values = selected.normalized_contrast.to_numpy(dtype=float)
            threshold = float(np.exp(np.mean(np.log(values))))
            reason = ''
        else:
            threshold = None
            reason = (
                f'Insufficient valid reversals: {len(valid)} < N={n}; '
                'excluded from interactive aggregation.'
            )

        result = {
            'threshold': threshold,
            'selected_indices': selected.reversal_index.tolist(),
            'detected_count': len(rows),
            'valid_count': len(valid),
            'reason': reason,
        }
        self.cache[key] = result
        return dict(result)

    def profile(self, condition_id, n):
        key = ('profile', condition_id, n)
        if key in self.cache:
            return self.cache[key].copy(deep=True)

        stairs = self.adapter.table('stairs').loc[
            lambda frame: frame.condition_id.eq(condition_id)
        ].copy()

        threshold_results = {
            sid: self.threshold(sid, n)
            for sid in stairs.staircase_id
        }

        rows = []
        for position in sorted(
            stairs.probe_position_deg.dropna().unique()
        ):
            components = {}
            thresholds_by_experiment = {}

            for experiment in ('base', 'flanker'):
                subset = stairs.loc[
                    stairs.probe_position_deg.eq(position)
                    & stairs.experiment.astype(str).str.lower().eq(experiment)
                    & stairs.included_for_baseline_candidate.astype(bool)
                ]
                values = [
                    threshold_results[sid]['threshold']
                    for sid in subset.staircase_id
                    if threshold_results[sid]['threshold'] is not None
                ]
                thresholds_by_experiment[experiment] = values

                if values:
                    mean_threshold = float(np.mean(values))
                    components[experiment] = {
                        'threshold': mean_threshold,
                        'sensitivity': 1.0 / mean_threshold,
                        'count': len(values),
                    }

            if not all(name in components for name in ('base', 'flanker')):
                continue

            base = components['base']
            flanker = components['flanker']
            log_ratio = float(
                np.log(flanker['sensitivity'] / base['sensitivity'])
            )

            pairwise = [
                float(np.log(tb / tf))
                for tb in thresholds_by_experiment['base']
                for tf in thresholds_by_experiment['flanker']
                if tb > 0 and tf > 0
            ]
            spread = (
                float(np.std(pairwise, ddof=1))
                if len(pairwise) >= 2
                else np.nan
            )

            archived_row = self.adapter.table('profiles').loc[
                lambda frame:
                    frame.condition_id.eq(condition_id)
                    & np.isclose(
                        frame.probe_position_deg,
                        position,
                        rtol=0,
                        atol=1e-12,
                    )
            ]
            distance = (
                float(archived_row.iloc[0].distance_from_flanker_edge_deg)
                if not archived_row.empty
                else float(position + 0.5)
            )

            rows.append(
                {
                    'condition_id': condition_id,
                    'exclusion_candidate': f'interactive_final_{n}',
                    'probe_position_deg': float(position),
                    'distance_from_flanker_edge_deg': distance,
                    'base_threshold': base['threshold'],
                    'flanker_threshold': flanker['threshold'],
                    'base_sensitivity': base['sensitivity'],
                    'flanker_sensitivity': flanker['sensitivity'],
                    'log_sensitivity_ratio': log_ratio,
                    'spread': spread,
                    'base_staircases': base['count'],
                    'flanker_staircases': flanker['count'],
                }
            )

        frame = pd.DataFrame(rows)
        if frame.empty:
            raise DatasetError(
                f'No complete Base/Flanker profile could be formed '
                f'for {condition_id} at N={n}.'
            )

        conditions = self.adapter.table('conditions').loc[
            lambda item: item.condition_id.eq(condition_id)
        ]
        if conditions.empty:
            raise DatasetError(f'Unknown condition: {condition_id}')

        condition = conditions.iloc[0]
        frame['participant_id'] = condition.participant_id
        frame['luminance_label_cd_m2'] = (
            condition.luminance_label_cd_m2
        )
        frame['included_in_thesis_main_isf'] = (
            condition.included_in_thesis_main_isf
        )

        self.cache[key] = frame.copy(deep=True)
        return frame

    def _condition_id(self, filters):
        required = {
            'participant_id': filters['participant_id'],
            'luminance_label_cd_m2': filters['luminance_label_cd_m2'],
        }
        rows = self.adapter.select('conditions', required)
        if len(rows) != 1:
            raise DatasetError(
                f'Expected exactly one lateral condition for {required}; '
                f'found {len(rows)}.'
            )
        return rows.iloc[0].condition_id

    def plot(self, level, filters, n):
        from ..models import Series
        from ..plotting.lateral_plots import (
            subject_isf_plot,
            lateral_profile_plot,
            position_comparison_plot,
            lateral_threshold_box_plot,
            lateral_staircase_plot,
        )

        label = (
            f'INTERACTIVE — geometric mean of final {n} reversals'
        )

        if level == 0:
            spec = subject_isf_plot(
                self.adapter.select('endpoints', filters),
                filters,
            )
            spec.title = (
                label
                + ' | archived ISF endpoint reference | '
                + spec.title
            )
            spec.metadata['Analysis'] = label
            spec.metadata['Interactive ISF'] = 'not recomputed'
            spec.notes = (
                'Interactive N does not alter this subject-level ISF panel. '
                'The archive does not establish the exact historical '
                'fit/input linkage, so PsyView keeps the archived ISF '
                'endpoints as an explicit reference. '
                + spec.notes
            )
            return spec

        condition_id = self._condition_id(filters)
        profile = self.profile(condition_id, n)

        if level == 1:
            spec = lateral_profile_plot(
                profile,
                filters,
                notes_prefix=(
                    f'{label}. Deposited detected reversals are reused. '
                ),
            )
            spec.title = label + ' | ' + spec.title
            spec.metadata['Analysis'] = label
            spec.metadata['Interactive ISF'] = 'not recomputed'
            return spec

        if level == 2:
            position = filters['probe_position_deg']
            match = profile.loc[
                np.isclose(
                    profile.probe_position_deg,
                    position,
                    rtol=0,
                    atol=1e-12,
                )
            ]
            if match.empty:
                raise DatasetError(
                    f'Interactive N={n} profile has no complete '
                    f'Base/Flanker point at {position:g}°.'
                )
            spec = position_comparison_plot(
                match.iloc[0],
                filters,
                notes_prefix=f'{label}. ',
            )
            spec.title = label + ' | ' + spec.title
            spec.metadata['Analysis'] = label
            return spec

        stairs = self.adapter.select(
            'stairs', filters
        ).copy(deep=True)

        archived_thresholds = {}
        results = {}

        for index, row in stairs.iterrows():
            archived_thresholds[row.staircase_id] = (
                row.threshold_last_five
            )
            result = self.threshold(row.staircase_id, n)
            results[row.staircase_id] = result
            stairs.loc[index, 'threshold_last_five'] = (
                result['threshold']
                if result['threshold'] is not None
                else np.nan
            )

        if level == 3:
            spec = lateral_threshold_box_plot(
                stairs,
                filters,
                threshold_column='threshold_last_five',
                notes_prefix=f'{label}. ',
            )
            spec.title = label + ' | ' + spec.title
            spec.metadata['Analysis'] = label
            return spec

        trials = self.adapter.select(
            'trials',
            filters,
        )
        reversals = self.adapter.select(
            'reversals',
            filters,
        ).copy(deep=True)

        # For the individual staircase view, update which reversals are
        # highlighted for the current interactive N.
        for row in stairs.itertuples():
            result = results[row.staircase_id]
            mask = reversals.staircase_id.eq(
                row.staircase_id
            )
            reversals.loc[
                mask,
                'used_in_final_five'
            ] = (
                reversals.loc[
                    mask,
                    'reversal_index'
                ]
                .isin(
                    result['selected_indices']
                )
            )

        spec = lateral_staircase_plot(
            stairs, trials, reversals, filters
        )
        spec.title = label + ' | ' + spec.title
        spec.metadata['Analysis'] = label

        for series in spec.series:
            if series.label == 'Final five':
                series.label = f'Final {n}'
            elif series.label == 'Archived geometric-mean threshold':
                series.label = (
                    f'Interactive N={n} geometric-mean threshold'
                )

        peers = self.adapter.select(
            'stairs',
            {
                key: value
                for key, value in filters.items()
                if key != 'staircase_id'
            },
        )
        peer_values = [
            self.threshold(row.staircase_id, n)['threshold']
            for row in peers.itertuples()
            if bool(row.included_for_baseline_candidate)
        ]
        peer_values = [
            value for value in peer_values
            if value is not None
        ]
        spec.metadata['Interactive mean threshold'] = (
            float(np.mean(peer_values)) if peer_values else None
        )
        spec.metadata['Interactive sensitivity'] = (
            float(1 / np.mean(peer_values)) if peer_values else None
        )

        if 'staircase_id' in filters and len(stairs):
            sid = filters['staircase_id']
            result = results[sid]
            archived = archived_thresholds[sid]
            spec.metadata['Detected reversals'] = (
                result['detected_count']
            )
            spec.metadata['Interactive threshold'] = (
                result['threshold']
            )
            spec.metadata['Archived final-five threshold'] = archived
            if np.isfinite(archived):
                spec.series.append(
                    Series(
                        [],
                        [float(archived)],
                        'Archived final-five reference',
                        'hline',
                        'white',
                        True,
                    )
                )

        failures = [
            f'{sid}: {result["reason"]}'
            for sid, result in results.items()
            if result['reason']
        ]
        spec.notes = (
            f'{label}. Diamonds identify the selected final {n} reversals. '
            + spec.notes
            + (' ' + '; '.join(failures) if failures else '')
        )
        return spec
