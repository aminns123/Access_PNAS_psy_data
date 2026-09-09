"""Bounded structural detection and adapter routing, independent of the UI."""
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
import pandas as pd
import yaml
from .base import DatasetError


@dataclass(frozen=True)
class DatasetInfo:
    adapter: str
    title: str
    details: str


def detect_pnas(root):
    required = {
        'data/processed/preferred_frequency.csv': {'condition_id', 'participant_id', 'luminance_cd_m2', 'f_pref_mean_cpd', 'percentile_2_5_cpd', 'percentile_97_5_cpd'},
        'data/processed/csf_thresholds.csv': {'condition_id', 'participant_id', 'luminance_cd_m2', 'spatial_frequency_cpd', 'contrast_threshold', 'contrast_sensitivity', 'included_in_csf_fit'},
        'data/raw/staircase_summary.csv': {'staircase_id', 'participant_id', 'condition_id', 'spatial_frequency_cpd', 'threshold_last8_median', 'included_in_primary_csf', 'n_trials_used', 'n_trials', 'n_detected_reversals', 'exclusion_reason'},
        'data/raw/staircase_reversals.csv': {'staircase_id', 'reversal_number_detected', 'trial_within_staircase', 'contrast_normalized_source', 'in_last8_point_estimate'},
        'data/raw/trials.csv.gz': {'participant_id', 'luminance_cd_m2', 'spatial_frequency_cpd', 'staircase_id', 'trial_within_staircase', 'contrast_normalized_source'},
    }
    if not (root/'data_dictionary.csv').is_file():
        return None
    for relative, columns in required.items():
        if not columns.issubset(pd.read_csv(root/relative, nrows=0).columns):
            return None
    # Bounded sample from a small summary, never decompress the trial table here.
    participants = pd.read_csv(root/'data/processed/preferred_frequency.csv', usecols=['participant_id'], nrows=1000).participant_id.nunique()
    return DatasetInfo('pnas', 'PNAS Psychophysics dataset', f'{participants} participants (summary sample) | processed data available | raw staircase data available')


DETECTORS = (detect_pnas,)


@lru_cache(maxsize=256)
def detect_dataset(root):
    root = Path(root).resolve()
    for detector in DETECTORS:
        try:
            result = detector(root)
            if result:
                return result
        except (OSError, ValueError, KeyError, EOFError):
            continue
    return None


def open_dataset(root):
    root = Path(root).expanduser().resolve()
    detect_dataset.cache_clear()
    info = detect_dataset(root)
    if info is None:
        raise DatasetError('Not a supported PsyView dataset')
    from .pnas_psychophysics import PNASAdapter
    factories = {'pnas': PNASAdapter}
    config = yaml.safe_load(files('psyview').joinpath('configs/pnas_psychophysics.yaml').read_text(encoding='utf-8'))
    adapter = factories[info.adapter](config)
    adapter.load(root)
    return adapter
