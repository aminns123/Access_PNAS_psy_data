"""Adapter for the lateral-sensitivity / ISF empirical archive."""
from __future__ import annotations

from .csv_adapter import CSVAdapter
from .base import DatasetError


class LateralAdapter(CSVAdapter):
    default_n_reversals = 5
    archived_analysis_label = (
        'ARCHIVED LATERAL — geometric mean of final 5 reversals'
    )

    def interactive_analysis_label(self, n):
        return f'INTERACTIVE — geometric mean of final {n} reversals'

    def load(self, root):
        super().load(root)

        conditions = self.table('conditions').copy(deep=True)
        if conditions.condition_id.duplicated().any():
            raise DatasetError(
                'Duplicate condition_id in lateral condition summary.'
            )

        self.table('endpoints')

        profiles = self.table('profiles').copy(deep=True)
        candidates = (
            profiles.exclusion_candidate
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )
        if 'storage_script_active_exclusions' in candidates:
            profiles = profiles.loc[
                profiles.exclusion_candidate.eq(
                    'storage_script_active_exclusions'
                )
            ].copy()
        elif len(candidates) > 1:
            raise DatasetError(
                'Lateral archive contains multiple exclusion candidates but '
                'the baseline candidate could not be identified safely.'
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
        self.tables['profiles'] = profiles

        stairs = self.table('stairs').copy(deep=True)
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
        self.tables['stairs'] = stairs
        self.filtered.clear()
        self._interactive = None
        self._fit_cache = {}

    def table(self, source):
        frame = super().table(source)

        marker = f'_lateral_enriched_{source}'
        if source == 'trials' and marker not in self.tables:
            conditions = super().table('conditions')[
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

        elif source == 'reversals' and marker not in self.tables:
            stairs = self.tables.get('stairs')
            if stairs is None:
                stairs = super().table('stairs')
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
                ['condition_id', 'staircase_id']
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
            self._interactive = LateralInteractiveAnalysis(self)
        return self._interactive

    def supports_fit(self, level):
        """The equation is fitted to the current luminance-level profile."""
        return level == 1

    def _condition_id(self, current_filters):
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

    def _fit_profile(
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
            cache_key = (
                'interactive',
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
            cache_key = (
                'archived',
                condition_id,
            )

        if cache_key not in self._fit_cache:
            from ..analysis.lateral_fit import (
                fit_lateral_profile,
            )
            self._fit_cache[
                cache_key
            ] = fit_lateral_profile(
                profile
            )

        return self._fit_cache[
            cache_key
        ]

    def get_plot_with_fit(
        self,
        level,
        current_filters,
        analysis=None,
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

        result = self._fit_profile(
            current_filters,
            analysis,
        )

        from ..models import Series
        from ..analysis.lateral_fit import (
            fit_display_text,
        )

        spec.series.append(
            Series(
                result.x_curve,
                result.y_curve,
                (
                    'INTERACTIVE / DIAGNOSTIC Eq. B.25 fit '
                    f'(fₙ={result.frequency_cpd:.3g} cpd)'
                ),
                color='yellow',
            )
        )

        spec.metadata['_fit_display'] = (
            fit_display_text(result)
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
            'Diagnostic fit weighting'
        ] = (
            'full spread with sigma floor 0.05'
        )

        spec.notes += (
            ' The yellow curve is a NEW on-demand diagnostic fit of thesis '
            'Eq. B.25 to the currently displayed profile. It is weighted by '
            'the full recorded spread with a 0.05 floor. It is not an '
            'archived historical fit and does not replace the archived ISF.'
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
