"""Adapter for the lateral-sensitivity / ISF empirical archive."""
from __future__ import annotations

import math

from .csv_adapter import CSVAdapter
from .base import DatasetError


class LateralAdapter(CSVAdapter):
    default_n_reversals = 5
    archived_analysis_label = (
        'ARCHIVED LATERAL — geometric mean of final 5 reversals'
    )

    def interactive_analysis_label(self, n):
        return (
            f'INTERACTIVE — geometric mean of final {n} reversals'
        )

    def load(self, root):
        super().load(root)

        conditions = self.table(
            'conditions'
        ).copy(deep=True)

        if conditions.condition_id.duplicated().any():
            raise DatasetError(
                'Duplicate condition_id in lateral condition summary.'
            )

        self.table('endpoints')

        # IMPORTANT: each archived condition already records its own selected
        # exclusion candidate. Do not globally keep only one candidate name.
        # P01 L010-L050 use storage_script_active_exclusions, P01 L200 uses
        # recorded_exclusion_list, and the remaining conditions use
        # no_exclusions.
        profiles = self.table(
            'profiles'
        ).copy(deep=True)

        candidate_counts = (
            profiles
            .groupby('condition_id')
            .exclusion_candidate
            .nunique(dropna=False)
        )
        ambiguous = candidate_counts.loc[
            candidate_counts > 1
        ]
        if not ambiguous.empty:
            raise DatasetError(
                'More than one lateral-profile exclusion candidate is present '
                'within a condition: '
                + ', '.join(ambiguous.index.astype(str))
            )

        actual_positions = (
            profiles.groupby('condition_id')
            .size()
        )
        expected_positions = (
            conditions.set_index('condition_id')
            .profile_positions
        )

        mismatches = []
        for condition_id, expected in expected_positions.items():
            actual = int(
                actual_positions.get(
                    condition_id,
                    0,
                )
            )
            if actual != int(expected):
                mismatches.append(
                    f'{condition_id}: '
                    f'expected {int(expected)}, found {actual}'
                )

        if mismatches:
            raise DatasetError(
                'Lateral profile-position counts do not match '
                'condition_summary.csv: '
                + '; '.join(mismatches)
            )

        profiles = profiles.merge(
            conditions[
                [
                    'condition_id',
                    'participant_id',
                    'luminance_label_cd_m2',
                    'included_in_thesis_main_isf',
                ]
            ],
            on='condition_id',
            how='left',
            validate='many_to_one',
        )

        if profiles.participant_id.isna().any():
            raise DatasetError(
                'A lateral profile has no matching condition metadata.'
            )

        self.tables[
            'profiles'
        ] = profiles

        stairs = self.table(
            'stairs'
        ).copy(deep=True)

        stairs = stairs.merge(
            conditions[
                [
                    'condition_id',
                    'luminance_label_cd_m2',
                    'included_in_thesis_main_isf',
                ]
            ],
            on='condition_id',
            how='left',
            validate='many_to_one',
        )

        if stairs.luminance_label_cd_m2.isna().any():
            raise DatasetError(
                'A staircase has no matching lateral condition metadata.'
            )

        summary = self.table('summary')
        extra_columns = [
            'staircase_id',
            'trials_recorded',
            'trials_used',
            'distinct_signed_positions',
            'final_five_geometric_threshold',
        ]

        stairs = stairs.merge(
            summary[extra_columns],
            on='staircase_id',
            how='left',
            validate='one_to_one',
        )

        self.tables[
            'stairs'
        ] = stairs
        self.filtered.clear()
        self._interactive = None
        self._fit_cache = {}
        self._fit_exclusions = {}

    def table(self, source):
        frame = super().table(source)

        marker = (
            f'_lateral_enriched_{source}'
        )

        if (
            source == 'trials'
            and marker not in self.tables
        ):
            conditions = super().table(
                'conditions'
            )[
                [
                    'condition_id',
                    'participant_id',
                    'luminance_label_cd_m2',
                ]
            ]

            enriched = frame.merge(
                conditions,
                on='condition_id',
                how='left',
                validate='many_to_one',
            )
            self.tables[source] = enriched
            self.tables[marker] = True
            frame = enriched

        elif (
            source == 'reversals'
            and marker not in self.tables
        ):
            stairs = self.tables.get(
                'stairs'
            )
            if stairs is None:
                stairs = super().table(
                    'stairs'
                )

            lookup = stairs[
                [
                    'condition_id',
                    'staircase_id',
                    'participant_id',
                    'luminance_label_cd_m2',
                    'experiment',
                    'probe_position_deg',
                    'included_for_baseline_candidate',
                ]
            ].drop_duplicates(
                [
                    'condition_id',
                    'staircase_id',
                ]
            )

            enriched = frame.merge(
                lookup,
                on=[
                    'condition_id',
                    'staircase_id',
                ],
                how='left',
                validate='many_to_one',
            )
            self.tables[source] = enriched
            self.tables[marker] = True
            frame = enriched

        return frame

    def interactive(self):
        if self._interactive is None:
            from ..analysis.lateral_interactive import (
                LateralInteractiveAnalysis,
            )
            self._interactive = (
                LateralInteractiveAnalysis(
                    self
                )
            )
        return self._interactive

    def supports_fit(self, level):
        return level == 1

    def _condition_id(
        self,
        current_filters,
    ):
        filters = {
            'participant_id':
                current_filters['participant_id'],
            'luminance_label_cd_m2':
                current_filters['luminance_label_cd_m2'],
        }

        rows = self.select(
            'conditions',
            filters,
        )

        if len(rows) != 1:
            raise DatasetError(
                f'Expected exactly one condition for {filters}; '
                f'found {len(rows)}.'
            )

        return rows.iloc[0].condition_id

    def _current_profile(
        self,
        current_filters,
        analysis=None,
    ):
        condition_id = self._condition_id(
            current_filters
        )

        if (
            analysis is not None
            and analysis.mode == 'interactive'
        ):
            profile = self.interactive().profile(
                condition_id,
                analysis.n_reversals,
            )
        else:
            profile = self.select(
                'profiles',
                {
                    'participant_id':
                        current_filters['participant_id'],
                    'luminance_label_cd_m2':
                        current_filters['luminance_label_cd_m2'],
                },
            )

        return condition_id, profile

    def fit_points(
        self,
        current_filters,
        analysis=None,
    ):
        _, profile = self._current_profile(
            current_filters,
            analysis,
        )
        return sorted(
            float(value)
            for value in (
                profile
                .distance_from_flanker_edge_deg
                .dropna()
                .unique()
            )
        )

    def fit_exclusions(
        self,
        current_filters,
    ):
        condition_id = self._condition_id(
            current_filters
        )
        return set(
            self._fit_exclusions.get(
                condition_id,
                set(),
            )
        )

    def toggle_fit_exclusion(
        self,
        current_filters,
        x_value,
    ):
        condition_id = self._condition_id(
            current_filters
        )
        exclusions = self._fit_exclusions.setdefault(
            condition_id,
            set(),
        )

        match = next(
            (
                value
                for value in exclusions
                if math.isclose(
                    float(value),
                    float(x_value),
                    rel_tol=0.0,
                    abs_tol=1e-10,
                )
            ),
            None,
        )

        if match is None:
            exclusions.add(
                float(x_value)
            )
            excluded = True
        else:
            exclusions.remove(match)
            excluded = False

        return excluded

    def clear_fit_exclusions(
        self,
        current_filters,
    ):
        condition_id = self._condition_id(
            current_filters
        )
        self._fit_exclusions[
            condition_id
        ] = set()

    @staticmethod
    def _profile_row_at_x(
        profile,
        x_value,
    ):
        distances = (
            profile
            .distance_from_flanker_edge_deg
            .astype(float)
        )
        mask = (
            distances - float(x_value)
        ).abs() <= 1e-10

        rows = profile.loc[mask]
        return (
            rows.iloc[0]
            if not rows.empty
            else None
        )

    def get_plot_with_fit(
        self,
        level,
        current_filters,
        analysis=None,
        fit_cursor_x=None,
        fit_edit=False,
    ):
        if not self.supports_fit(level):
            return self.get_plot(
                level,
                current_filters,
                analysis,
            )

        spec = self.get_plot(
            level,
            current_filters,
            analysis,
        )

        condition_id, profile = self._current_profile(
            current_filters,
            analysis,
        )

        exclusions = self.fit_exclusions(
            current_filters
        )

        from ..models import Series

        for index, x_value in enumerate(
            sorted(exclusions)
        ):
            row = self._profile_row_at_x(
                profile,
                x_value,
            )
            if row is not None:
                spec.series.append(
                    Series(
                        [float(x_value)],
                        [
                            float(
                                row.log_sensitivity_ratio
                            )
                        ],
                        (
                            'Excluded from diagnostic fit'
                            if index == 0
                            else ''
                        ),
                        'scatter',
                        'red',
                        marker='×',
                    )
                )

        if (
            fit_edit
            and fit_cursor_x is not None
        ):
            row = self._profile_row_at_x(
                profile,
                fit_cursor_x,
            )
            if row is not None:
                spec.series.append(
                    Series(
                        [float(fit_cursor_x)],
                        [
                            float(
                                row.log_sensitivity_ratio
                            )
                        ],
                        'Fit-point cursor',
                        'scatter',
                        'magenta',
                        marker='◆',
                    )
                )

        cache_key = (
            'fit',
            condition_id,
            (
                analysis.mode
                if analysis is not None
                else 'archived'
            ),
            (
                analysis.n_reversals
                if (
                    analysis is not None
                    and analysis.mode == 'interactive'
                )
                else None
            ),
            tuple(
                sorted(
                    round(
                        float(value),
                        10,
                    )
                    for value in exclusions
                )
            ),
        )

        if cache_key not in self._fit_cache:
            from ..analysis.lateral_fit import (
                fit_lateral_profile,
            )
            try:
                result = fit_lateral_profile(
                    profile,
                    excluded_x=exclusions,
                )
                self._fit_cache[
                    cache_key
                ] = (
                    'ok',
                    result,
                )
            except Exception as exc:
                self._fit_cache[
                    cache_key
                ] = (
                    'error',
                    str(exc),
                )

        status, payload = self._fit_cache[
            cache_key
        ]

        if status == 'error':
            spec.metadata[
                '_fit_display'
            ] = (
                'INTERACTIVE / DIAGNOSTIC FIT\n'
                f'Fit unavailable: {payload}\n'
                f'Excluded points: {len(exclusions)}. '
                'Use E + ←/→ + Enter to re-include points.'
            )
            spec.metadata[
                'Diagnostic fit exclusions'
            ] = len(exclusions)
            return spec

        result = payload

        from ..analysis.lateral_fit import (
            fit_display_text,
        )

        spec.series.append(
            Series(
                result.x_curve,
                result.y_curve,
                (
                    'Diagnostic Eq. B.25 fit '
                    f'(fₙ={result.frequency_cpd:.3g} cpd)'
                ),
                color='red',
            )
        )

        spec.metadata[
            '_fit_display'
        ] = fit_display_text(
            result
        )
        spec.metadata[
            'Diagnostic fitted f_n (cpd)'
        ] = round(
            result.frequency_cpd,
            6,
        )
        spec.metadata[
            'Diagnostic fit FMS'
        ] = round(
            result.frequency_match_score,
            6,
        )
        spec.metadata[
            'Diagnostic fit points'
        ] = result.n_points
        spec.metadata[
            'Diagnostic fit exclusions'
        ] = result.excluded_points
        spec.metadata[
            'Diagnostic fit weighting'
        ] = (
            'full spread with sigma floor 0.05'
        )

        spec.notes += (
            ' The red curve is a NEW on-demand diagnostic fit of thesis '
            'Eq. B.25 to the currently displayed profile. Points marked red × '
            'are displayed but excluded from this fit. The objective uses the '
            'full recorded spread with a 0.05 floor. It is not an archived '
            'historical fit and does not replace the archived ISF.'
        )

        return spec

    def get_plot(
        self,
        level,
        current_filters,
        analysis=None,
    ):
        if (
            analysis is not None
            and analysis.mode == 'interactive'
        ):
            engine = self.interactive()
            with engine.lock:
                return engine.plot(
                    level,
                    current_filters,
                    analysis.n_reversals,
                )

        spec = self.archived_plot(
            level,
            current_filters,
        )
        spec.title = (
            'ARCHIVED LATERAL | '
            + spec.title
        )
        spec.metadata[
            'Analysis'
        ] = self.archived_analysis_label
        return spec

    def archived_plot(
        self,
        level,
        current_filters,
    ):
        from ..plotting.lateral_plots import (
            subject_isf_plot,
            lateral_profile_plot,
            position_comparison_plot,
            lateral_threshold_box_plot,
            lateral_staircase_plot,
        )

        if level == 0:
            endpoints = self.select(
                'endpoints',
                current_filters,
            )
            return subject_isf_plot(
                endpoints,
                current_filters,
            )

        condition_filters = {
            key: value
            for key, value in current_filters.items()
            if key in (
                'participant_id',
                'luminance_label_cd_m2',
            )
        }

        if level == 1:
            profile = self.select(
                'profiles',
                condition_filters,
            )
            return lateral_profile_plot(
                profile,
                current_filters,
            )

        if level == 2:
            profile = self.select(
                'profiles',
                current_filters,
            )
            if profile.empty:
                raise DatasetError(
                    'No archived lateral-profile point '
                    'matches this position.'
                )
            return position_comparison_plot(
                profile.iloc[0],
                current_filters,
            )

        stairs = self.select(
            'stairs',
            current_filters,
        )

        if level == 3:
            return lateral_threshold_box_plot(
                stairs,
                current_filters,
                threshold_column='threshold_last_five',
            )

        trials = self.select(
            'trials',
            current_filters,
        )
        reversals = self.select(
            'reversals',
            current_filters,
        )
        return lateral_staircase_plot(
            stairs,
            trials,
            reversals,
            current_filters,
        )
