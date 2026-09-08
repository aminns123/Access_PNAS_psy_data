from .csv_adapter import CSVAdapter
from .base import DatasetError
from ..plotting.pnas_plots import subject_plot, csf_plot, staircase_plot


class PNASAdapter(CSVAdapter):
    def load(self, root):
        super().load(root)
        psf = self.table('psf')
        self.table('csf')
        stairs = self.table('stairs')
        conditions = psf[['condition_id', 'participant_id', 'luminance_cd_m2']]
        if conditions.condition_id.duplicated().any():
            raise DatasetError('Duplicate condition_id in preferred-frequency table.')
        joined = stairs.merge(conditions, on=['condition_id', 'participant_id'], how='left', validate='many_to_one')
        if joined.luminance_cd_m2.isna().any():
            raise DatasetError('Staircase condition has no matching participant/luminance in preferred-frequency table.')
        self.tables['stairs'] = joined
        self.filtered.clear()

    def get_plot(self, level, current_filters):
        if level == 0:
            return subject_plot(self.select('psf', current_filters), current_filters)
        if level >= 2:
            stairs = self.select('stairs', current_filters)
            trials = self.select('trials', current_filters)
            ids = tuple(stairs.staircase_id)
            key = ('reversals_by_staircase', ids)
            if key not in self.filtered:
                self.filtered[key] = self.table('reversals').loc[lambda frame: frame.staircase_id.isin(ids)]
            csf_filters = {key: value for key, value in current_filters.items() if key != 'staircase_id'}
            csf = self.select('csf', csf_filters)
            return staircase_plot(stairs, trials, self.filtered[key], current_filters, csf)
        psf = self.select('psf', current_filters).iloc[0]
        csf = self.select('csf', current_filters)
        try:
            curves = self.select('curves', {'condition_id': psf.condition_id})
            note = 'Curve: archived output recomputed with supplied current helper; not a historical saved fit.'
        except DatasetError as exc:
            curves = None
            note = f'Curve unavailable: {exc}'
        return csf_plot(csf, psf, current_filters, curves, note)
