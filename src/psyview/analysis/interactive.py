"""Deterministic, read-only analysis over a loaded dataset snapshot."""
import hashlib
import json
import threading
import warnings
import logging
import os
import tempfile
from pathlib import Path
import numpy as np
from ..data.base import DatasetError
from .source_helpers import count_reversals_HighLow, AoE, fit_to_CSF

VERSION = 'pnas-final-n-v1'


class InteractiveAnalysis:
    def __init__(self, adapter):
        self.adapter = adapter
        self.lock = threading.RLock()
        self.cache = {}
        self.detected = {}
        self.fingerprint = None

    def source_stamp(self):
        return tuple((source, (self.adapter.root/self.adapter.config['sources'][source]).stat().st_mtime_ns,
                      (self.adapter.root/self.adapter.config['sources'][source]).stat().st_size)
                     for source in ('psf', 'csf', 'stairs', 'trials', 'reversals'))

    def check_sources(self):
        if self.source_stamp() != self.adapter.analysis_source_stamp:
            raise DatasetError('Dataset source files changed. Press R to reload before recomputing.')

    def identity(self):
        if self.fingerprint is None:
            digest = hashlib.sha256(str(self.adapter.root.resolve()).encode())
            for source in ('psf', 'csf', 'stairs', 'trials', 'reversals'):
                path = self.adapter.root/self.adapter.config['sources'][source]
                digest.update(source.encode())
                with path.open('rb') as stream:
                    for chunk in iter(lambda: stream.read(1024*1024), b''):
                        digest.update(chunk)
            digest.update(Path(__file__).read_bytes())
            digest.update(Path(__file__).with_name('source_helpers.py').read_bytes())
            import scipy
            digest.update(f'{VERSION}:{np.__version__}:{scipy.__version__}'.encode())
            self.fingerprint = digest.hexdigest()
        return self.fingerprint

    def reversal_rows(self, staircase_id):
        if staircase_id in self.detected:
            return self.detected[staircase_id].copy(deep=True)
        row = self.adapter.table('stairs').set_index('staircase_id').loc[staircase_id]
        trial = self.adapter.table('trials').loc[lambda f: f.staircase_id.eq(staircase_id)].sort_values('trial_within_staircase')
        values = trial.contrast_normalized_source.iloc[:int(row.n_trials_used)].tolist()
        if not np.isfinite(values).all():
            raise DatasetError(f'{staircase_id}: nonfinite raw trial contrast')
        _, indices, detected = count_reversals_HighLow(values)
        deposited = self.adapter.table('reversals').loc[lambda f: f.staircase_id.eq(staircase_id)].sort_values('reversal_number_detected').copy()
        if deposited.reversal_number_detected.duplicated().any():
            raise DatasetError(f'{staircase_id}: duplicate reversal numbers')
        trials = trial.trial_within_staircase.iloc[indices].tolist() if len(values) > 1 else []
        if len(values) <= 1:
            detected = []  # helper's short-input sentinel is not a detected reversal
        if trials != deposited.trial_within_staircase.tolist() or not np.array_equal(detected, deposited.contrast_normalized_source.to_numpy()):
            raise DatasetError(f'{staircase_id}: raw-trial reversal detection differs from deposited reversals; interactive analysis stopped')
        self.detected[staircase_id] = deposited
        return deposited.copy(deep=True)

    def max_n(self):
        counts = self.adapter.table('reversals').groupby('staircase_id').size()
        return max(1, int(counts.max())) if len(counts) else 1

    def threshold(self, staircase_id, n):
        if not isinstance(n, int) or n < 1:
            raise ValueError('N must be a positive integer')
        key = (self.identity(), 'threshold', staircase_id, n)
        if key not in self.cache:
            rows = self.reversal_rows(staircase_id)
            values = rows.contrast_normalized_source.to_numpy(dtype=float)
            valid = rows.loc[np.isfinite(values) & (values > 0)]
            selected = valid.tail(n) if len(valid) >= n else valid.iloc[:0]
            value = float(np.median(selected.contrast_normalized_source)) if len(selected) else None
            reason = '' if value is not None else f'Insufficient valid reversals: {len(valid)} < N={n}; excluded from interactive aggregation'
            self.cache[key] = {'threshold': value, 'selected_numbers': selected.reversal_number_detected.tolist(),
                               'detected_count': len(rows), 'valid_count': len(valid), 'reason': reason}
        return dict(self.cache[key])

    def condition(self, condition_id, n, fit=False):
        key = (self.identity(), 'condition', condition_id, n, fit)
        if key in self.cache:
            return self.cache[key]
        from ..preferences import cache_directory
        cache_path = cache_directory()/self.identity()/(hashlib.sha256(f'{condition_id}:{n}:{fit}'.encode()).hexdigest()+'.json')
        cache_allowed = not cache_path.resolve().is_relative_to(self.adapter.root)
        if fit and cache_allowed:
            try:
                payload = json.loads(cache_path.read_text(encoding='utf-8'))
                if payload['key'] == list(key):
                    import pandas as pd
                    result = payload['result']
                    result['frame'] = pd.DataFrame(result['frame'])
                    self.cache[key] = result
                    return result
            except (OSError, ValueError, KeyError, TypeError):
                pass
        stairs = self.adapter.table('stairs').loc[lambda f: f.condition_id.eq(condition_id)]
        frame = self.adapter.table('csf').loc[lambda f: f.condition_id.eq(condition_id)].sort_values('spatial_frequency_cpd').copy(deep=True)
        omissions = []
        thresholds = {}
        for row in stairs.itertuples():
            result = self.threshold(row.staircase_id, n)
            thresholds[row.staircase_id] = result
            if result['reason']:
                omissions.append(f'{row.staircase_id}: {result["reason"]}')
        for index, row in frame.iterrows():
            subset = stairs.loc[stairs.spatial_frequency_cpd.eq(row.spatial_frequency_cpd) & stairs.included_in_primary_csf]
            values = [thresholds[sid]['threshold'] for sid in subset.staircase_id if thresholds[sid]['threshold'] is not None]
            threshold = float(np.mean(values)) if values else np.nan
            frame.loc[index, 'contrast_threshold'] = threshold
            frame.loc[index, 'contrast_sensitivity'] = 1/threshold if threshold > 0 else np.nan
            frame.loc[index, 'interactive_staircases_used'] = len(values)
            frame.loc[index, 'interactive_staircases_insufficient'] = len(subset)-len(values)
        result = {'frame': frame, 'peak': None, 'curve_x': [], 'curve_y': [], 'notes': '; '.join(omissions), 'fit_status': 'not requested'}
        if fit:
            included = frame.loc[frame.included_in_csf_fit]
            if len(included) < 4 or not np.isfinite(included.contrast_sensitivity).all():
                result['fit_status'] = 'Unavailable: fewer than four fit points or missing included condition sensitivity'
            else:
                try:
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter('always')
                        x, y, parameters, peak = fit_to_CSF(included.spatial_frequency_cpd.tolist(), included.contrast_sensitivity.tolist(), AoE, [], [], [], 5000000, 'trf')
                    if not np.isfinite(y).all() or not np.isfinite(peak):
                        raise ValueError('Nonfinite AoE fit output')
                    result.update(peak=float(peak), curve_x=x, curve_y=y, fit_status='Deterministic current-helper AoE fit', parameters=parameters)
                    if caught:
                        result['fit_status'] += '; '+ '; '.join(sorted({str(w.message) for w in caught}))
                except (ValueError, RuntimeError, FloatingPointError) as exc:
                    result['fit_status'] = f'AoE fit unavailable: {exc}'
        self.cache[key] = result
        if fit and cache_allowed and result['peak'] is not None:
            try:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                payload = {'key': list(key), 'result': {**result, 'frame': frame.to_dict('records')}}
                with tempfile.NamedTemporaryFile(mode='w', dir=cache_path.parent, suffix='.tmp', encoding='utf-8', delete=False) as stream:
                    temporary = Path(stream.name)
                    json.dump(payload, stream, default=lambda v: v.item() if isinstance(v, np.generic) else str(v))
                os.replace(temporary, cache_path)
            except OSError:
                logging.getLogger(__name__).warning('Cache unavailable; retaining in-memory result', exc_info=True)
        return result

    def plot(self, level, filters, n):
        self.check_sources()
        from ..models import PlotSpec, Series
        from ..plotting.pnas_plots import staircase_plot
        prefix = f'INTERACTIVE — final {n} reversals'
        metadata = {**filters, 'Analysis': prefix, 'Interactive uncertainty': 'not computed'}
        notes = 'Deterministic current-helper analysis. Interactive uncertainty: not computed. Archived inclusion rules retained.'
        if level == 0:
            frame = self.adapter.select('psf', filters).sort_values('luminance_cd_m2')
            x, y, failures = [], [], []
            for row in frame.itertuples():
                result = self.condition(row.condition_id, n, fit=True)
                if result['notes']:
                    failures.append(f'{row.luminance_cd_m2:g} cd/m²: staircases with insufficient reversals omitted; inspect condition/staircase details')
                if result['peak'] is not None:
                    x.append(row.luminance_cd_m2)
                    y.append(result['peak'])
                else:
                    failures.append(f'{row.luminance_cd_m2:g} cd/m²: {result["fit_status"]}')
            return PlotSpec(f'{prefix} | {filters["participant_id"]} — Preferred spatial frequency vs luminance',
                            'Luminance (cd/m²)', 'Preferred spatial frequency (cpd)',
                            [Series(x, y, f'Interactive N={n} PSF', 'scatter'),
                             Series(frame.luminance_cd_m2.tolist(), frame.f_pref_mean_cpd.tolist(), 'Archived mean reference', 'scatter', 'white')],
                            xscale='log', notes=notes+' '+'; '.join(failures), metadata=metadata)
        psf = self.adapter.select('psf', {k:v for k,v in filters.items() if k in ('participant_id','luminance_cd_m2')}).iloc[0]
        if level == 1:
            result = self.condition(psf.condition_id, n, fit=True)
            frame = result['frame']
            spec = PlotSpec(f'{prefix} | {filters["participant_id"]} — {psf.luminance_cd_m2:g} cd/m² — CSF',
                            'Spatial frequency (cpd)', 'Contrast sensitivity', xscale='log', yscale='log',
                            metadata={**metadata, 'Interactive f_pref (cpd)': result['peak'], 'Archived mean f_pref (cpd)': psf.f_pref_mean_cpd},
                            notes=notes+' '+result['fit_status']+' '+result['notes'])
            for included, color, label in ((True, 'cyan', 'Included'), (False, 'red', 'Excluded from fit')):
                part = frame.loc[frame.included_in_csf_fit.eq(included) & np.isfinite(frame.contrast_sensitivity)]
                if not part.empty:
                    spec.series.append(Series(part.spatial_frequency_cpd.tolist(), part.contrast_sensitivity.tolist(), f'Interactive {label}', 'scatter', color))
            if result['peak'] is not None:
                spec.series.append(Series(result['curve_x'], result['curve_y'], 'Interactive AoE fit', color='blue'))
                spec.series.append(Series([result['peak']], [], 'Interactive f_pref', 'vline', 'yellow'))
            return spec
        stairs = self.adapter.select('stairs', filters).copy(deep=True)
        trials = self.adapter.select('trials', filters)
        reversals = self.adapter.table('reversals').loc[lambda f: f.staircase_id.isin(stairs.staircase_id)].copy(deep=True)
        results = {}
        for index, row in stairs.iterrows():
            result = self.threshold(row.staircase_id, n)
            results[row.staircase_id] = result
            stairs.loc[index, 'threshold_last8_median'] = result['threshold'] if result['threshold'] is not None else np.nan
            mask = reversals.staircase_id.eq(row.staircase_id)
            reversals.loc[mask, 'in_last8_point_estimate'] = reversals.loc[mask, 'reversal_number_detected'].isin(result['selected_numbers'])
        archived_csf = self.adapter.select('csf', {k:v for k,v in filters.items() if k != 'staircase_id'})
        spec = staircase_plot(stairs, trials, reversals, filters, archived_csf)
        spec.title = prefix+' | '+spec.title
        spec.metadata.update(metadata)
        spec.metadata.pop('threshold_last8_median', None)
        # This level only needs one frequency; no CSF fits or other frequencies.
        peers = self.adapter.select('stairs', {k:v for k,v in filters.items() if k != 'staircase_id'})
        included = [self.threshold(row.staircase_id, n)['threshold'] for row in peers.itertuples() if row.included_in_primary_csf]
        included = [v for v in included if v is not None]
        spec.metadata['Interactive sensitivity'] = float(1/np.mean(included)) if included else None
        spec.metadata['Interactive staircase thresholds'] = {sid:r['threshold'] for sid,r in results.items()}
        if 'staircase_id' in filters:
            sid = filters['staircase_id']
            archived = self.adapter.select('stairs', filters).iloc[0].threshold_last8_median
            spec.metadata.update({'Detected reversals': results[sid]['detected_count'], 'Interactive threshold': results[sid]['threshold'], 'Archived threshold': archived})
            if np.isfinite(archived):
                spec.series.append(Series([], [float(archived)], 'Archived threshold reference', 'hline', 'white', True))
        for series in spec.series:
            if series.label == 'final eight':
                series.label = f'final {n}'
            elif series.label == 'Archived threshold':
                series.label = f'Interactive N={n} threshold'
        spec.notes = notes + f' Diamonds: final {n} selected reversals. ' + '; '.join(f'{sid}: {r["reason"]}' for sid,r in results.items() if r['reason'])
        return spec
