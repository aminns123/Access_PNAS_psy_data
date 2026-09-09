from .csv_adapter import CSVAdapter
from .base import DatasetError
from ..plotting.pnas_plots import (
    subject_plot,
    csf_plot,
    staircase_plot,
    pnas_threshold_box_plot,
)


class PNASAdapter(CSVAdapter):
    default_n_reversals = 8
    archived_analysis_label = (
        'ARCHIVED PNAS — median of final 8 reversals'
    )

    def interactive_analysis_label(self, n):
        return f'INTERACTIVE — median of final {n} reversals'

    def load(self, root):
        super().load(root)
        psf = self.table('psf')
        self.table('csf')
        stairs = self.table('stairs')

        conditions = psf[
            [
                'condition_id',
                'participant_id',
                'luminance_cd_m2',
            ]
        ]

        if conditions.condition_id.duplicated().any():
            raise DatasetError(
                'Duplicate condition_id in preferred-frequency table.'
            )

        joined = stairs.merge(
            conditions,
            on=[
                'condition_id',
                'participant_id',
            ],
            how='left',
            validate='many_to_one',
        )

        if joined.luminance_cd_m2.isna().any():
            raise DatasetError(
                'Staircase condition has no matching '
                'participant/luminance in preferred-frequency table.'
            )

        self.tables['stairs'] = joined
        self.filtered.clear()
        self._interactive = None

        self.analysis_source_stamp = tuple(
            (
                source,
                (
                    self.root
                    / self.config['sources'][source]
                ).stat().st_mtime_ns,
                (
                    self.root
                    / self.config['sources'][source]
                ).stat().st_size,
            )
            for source in (
                'psf',
                'csf',
                'stairs',
                'trials',
                'reversals',
            )
            if (
                self.root
                / self.config['sources'][source]
            ).exists()
        )

    def interactive(self):
        if self._interactive is None:
            from ..analysis.interactive import InteractiveAnalysis
            self._interactive = InteractiveAnalysis(self)
        return self._interactive

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
                if level == 2:
                    return self.interactive_threshold_box_plot(
                        current_filters,
                        analysis.n_reversals,
                        engine,
                    )

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
            'ARCHIVED PNAS | '
            + spec.title
        )
        spec.metadata[
            'Analysis'
        ] = 'ARCHIVED PNAS'

        return spec

    def interactive_threshold_box_plot(
        self,
        current_filters,
        n_reversals,
        engine=None,
    ):
        """Recompute final-N thresholds and display their distribution."""
        import numpy as np

        engine = engine or self.interactive()
        engine.check_sources()

        stairs = self.select(
            'stairs',
            current_filters,
        ).copy(deep=True)

        trials = self.select(
            'trials',
            current_filters,
        )

        failures = []

        for index, row in stairs.iterrows():
            result = engine.threshold(
                row.staircase_id,
                n_reversals,
            )

            stairs.loc[
                index,
                'threshold_last8_median',
            ] = (
                result['threshold']
                if result['threshold'] is not None
                else np.nan
            )

            if result['reason']:
                failures.append(
                    f'{row.staircase_id}: {result["reason"]}'
                )

        label = (
            f'INTERACTIVE — median of final '
            f'{n_reversals} reversals'
        )

        spec = pnas_threshold_box_plot(
            stairs,
            trials,
            current_filters,
            threshold_column='threshold_last8_median',
            notes_prefix=(
                f'{label}. The box is rebuilt from the current '
                'per-staircase final-N thresholds. '
            ),
        )

        spec.title = label + ' | ' + spec.title
        spec.metadata['Analysis'] = label
        spec.metadata['Interactive N'] = int(
            n_reversals
        )

        if failures:
            spec.notes += (
                ' '
                + '; '.join(failures)
            )

        return spec

    def archived_plot(
        self,
        level,
        current_filters,
    ):
        if level == 0:
            return subject_plot(
                self.select(
                    'psf',
                    current_filters,
                ),
                current_filters,
            )

        if level == 2:
            stairs = self.select(
                'stairs',
                current_filters,
            )
            trials = self.select(
                'trials',
                current_filters,
            )

            return pnas_threshold_box_plot(
                stairs,
                trials,
                current_filters,
                threshold_column='threshold_last8_median',
                notes_prefix=(
                    'Archived staircase thresholds use the median of the '
                    'final eight detected reversals. '
                ),
            )

        if level >= 3:
            stairs = self.select(
                'stairs',
                current_filters,
            )
            trials = self.select(
                'trials',
                current_filters,
            )

            ids = tuple(
                stairs.staircase_id
            )
            cache_key = (
                'reversals_by_staircase',
                ids,
            )

            if cache_key not in self.filtered:
                self.filtered[
                    cache_key
                ] = (
                    self.table(
                        'reversals'
                    ).loc[
                        lambda frame:
                            frame.staircase_id.isin(
                                ids
                            )
                    ]
                )

            csf_filters = {
                key: value
                for key, value
                in current_filters.items()
                if key != 'staircase_id'
            }

            csf = self.select(
                'csf',
                csf_filters,
            )

            return staircase_plot(
                stairs,
                trials,
                self.filtered[
                    cache_key
                ],
                current_filters,
                csf,
            )

        psf = self.select(
            'psf',
            current_filters,
        ).iloc[0]

        csf = self.select(
            'csf',
            current_filters,
        )

        staircase_filters = {
            key: value
            for key, value
            in current_filters.items()
            if key in (
                'participant_id',
                'luminance_cd_m2',
            )
        }

        stairs = self.select(
            'stairs',
            staircase_filters,
        )

        try:
            curves = self.select(
                'curves',
                {
                    'condition_id':
                        psf.condition_id
                },
            )

            note = (
                'Curve: archived output recomputed with supplied '
                'current helper; not a historical saved fit.'
            )

        except DatasetError as exc:
            curves = None
            note = (
                f'Curve unavailable: {exc}'
            )

        return csf_plot(
            csf,
            psf,
            current_filters,
            curves,
            note,
            stairs=stairs,
        )
