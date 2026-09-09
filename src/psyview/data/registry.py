"""Bounded structural detection and adapter routing, independent of the UI."""
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

import pandas as pd
import yaml

from .base import DatasetError
from .inspector import inspect_repository, generic_config


@dataclass(frozen=True)
class DatasetInfo:
    adapter: str
    title: str
    details: str
    confidence: float = 1.0
    evidence: tuple[str, ...] = ()


def _header(root: Path, relative: str) -> set[str]:
    path = root / relative
    if not path.is_file():
        return set()
    return set(pd.read_csv(path, nrows=0).columns)


def detect_pnas(root):
    root = Path(root)
    required = {
        'data/processed/preferred_frequency.csv': {
            'condition_id', 'participant_id', 'luminance_cd_m2',
            'f_pref_mean_cpd', 'percentile_2_5_cpd', 'percentile_97_5_cpd',
        },
        'data/processed/csf_thresholds.csv': {
            'condition_id', 'participant_id', 'luminance_cd_m2',
            'spatial_frequency_cpd', 'contrast_threshold',
            'contrast_sensitivity', 'included_in_csf_fit',
        },
        'data/raw/staircase_summary.csv': {
            'staircase_id', 'participant_id', 'condition_id',
            'spatial_frequency_cpd', 'threshold_last8_median',
            'included_in_primary_csf', 'n_trials_used', 'n_trials',
            'n_detected_reversals', 'exclusion_reason',
        },
        'data/raw/staircase_reversals.csv': {
            'staircase_id', 'reversal_number_detected',
            'trial_within_staircase', 'contrast_normalized_source',
            'in_last8_point_estimate',
        },
        'data/raw/trials.csv.gz': {
            'participant_id', 'luminance_cd_m2', 'spatial_frequency_cpd',
            'staircase_id', 'trial_within_staircase',
            'contrast_normalized_source',
        },
    }
    if not (root / 'data_dictionary.csv').is_file():
        return None
    for relative, columns in required.items():
        if not columns.issubset(_header(root, relative)):
            return None

    participants = pd.read_csv(
        root / 'data/processed/preferred_frequency.csv',
        usecols=['participant_id'],
        nrows=1000,
    ).participant_id.nunique()

    return DatasetInfo(
        'pnas',
        'Contrast sensitivity / PSF dataset',
        f'{participants} participants | CSF/PSF summaries + raw staircases',
        0.995,
        ('preferred_frequency.csv', 'csf_thresholds.csv', 'threshold_last8_median'),
    )


def detect_lateral(root):
    root = Path(root)
    required = {
        'data/processed/condition_summary.csv': {
            'condition_id', 'participant_id', 'luminance_label_cd_m2',
            'included_in_thesis_main_isf',
        },
        'data/processed/isf_endpoints.csv': {
            'condition_id', 'participant_id', 'luminance_label_cd_m2',
            'candidate_mode', 'isf_estimate_cpd', 'isf_lower_cpd',
            'isf_upper_cpd', 'dominant_retained_mode',
        },
        'data/processed/lateral_profiles_recomputed.csv': {
            'condition_id', 'probe_position_deg',
            'distance_from_flanker_edge_deg', 'base_threshold',
            'flanker_threshold', 'base_sensitivity', 'flanker_sensitivity',
            'log_sensitivity_ratio', 'spread',
        },
        'data/processed/staircase_thresholds.csv': {
            'condition_id', 'participant_id', 'experiment', 'staircase_id',
            'probe_position_deg', 'threshold_last_five',
            'included_for_baseline_candidate',
        },
        'data/processed/staircase_summary.csv': {
            'condition_id', 'experiment', 'staircase_id',
            'probe_position_deg', 'trials_used',
            'final_five_geometric_threshold',
        },
        'data/processed/staircase_reversals.csv': {
            'condition_id', 'staircase_id', 'reversal_index',
            'trial_within_staircase', 'normalized_contrast',
            'used_in_final_five',
        },
        'data/processed/staircase_trials.csv.gz': {
            'condition_id', 'experiment', 'staircase_id',
            'trial_within_staircase', 'probe_position_deg',
            'normalized_contrast', 'included_for_baseline_candidate',
        },
    }
    if not (root / 'data_dictionary.csv').is_file():
        return None
    for relative, columns in required.items():
        if not columns.issubset(_header(root, relative)):
            return None

    summary = pd.read_csv(
        root / 'data/processed/condition_summary.csv',
        usecols=['participant_id', 'condition_id'],
        nrows=1000,
    )
    return DatasetInfo(
        'lateral',
        'Lateral sensitivity / ISF dataset',
        (
            f'{summary.participant_id.nunique()} participants | '
            f'{summary.condition_id.nunique()} luminance conditions | '
            'Base/Flanker lateral profiles + staircases'
        ),
        0.995,
        (
            'lateral_profiles_recomputed.csv',
            'isf_endpoints.csv',
            'threshold_last_five',
            'experiment=base/flanker',
        ),
    )


def detect_generic(root):
    root = Path(root)
    has_root_evidence = (
        (root / 'data_dictionary.csv').is_file()
        or any(root.glob('*.csv'))
        or any(root.glob('*.csv.gz'))
        or (root / 'data').is_dir()
    )
    if not has_root_evidence:
        return None

    report = inspect_repository(root)
    if report.best_table is None or len(report.hierarchy) < 1:
        return None
    if report.confidence < 0.62:
        return None

    hierarchy = ' → '.join(
        item.role.replace('_', ' ') for item in report.hierarchy
    )
    return DatasetInfo(
        'generic',
        'Structured empirical dataset — generic explorer',
        (
            f'Inferred hierarchy: {hierarchy}. '
            'Scientific analysis type not identified; no derived analysis will be guessed.'
        ),
        report.confidence,
        tuple(report.evidence),
    )


DETECTORS = (detect_pnas, detect_lateral, detect_generic)


@lru_cache(maxsize=256)
def detect_dataset(root):
    root = Path(root).expanduser().resolve()
    for detector in DETECTORS:
        try:
            result = detector(root)
            if result:
                return result
        except (OSError, ValueError, KeyError, EOFError, UnicodeError):
            continue
    return None


def _packaged_config(name: str):
    return yaml.safe_load(
        files('psyview').joinpath(f'configs/{name}').read_text(encoding='utf-8')
    )


def open_dataset(root):
    root = Path(root).expanduser().resolve()
    detect_dataset.cache_clear()
    inspect_repository.cache_clear()

    info = detect_dataset(root)
    if info is None:
        raise DatasetError(
            'No supported or safely inferable empirical dataset structure was found.'
        )

    if info.adapter == 'pnas':
        from .pnas_psychophysics import PNASAdapter
        adapter = PNASAdapter(_packaged_config('pnas_psychophysics.yaml'))
    elif info.adapter == 'lateral':
        from .lateral_sensitivity import LateralAdapter
        adapter = LateralAdapter(_packaged_config('lateral_sensitivity.yaml'))
    elif info.adapter == 'generic':
        from .csv_adapter import CSVAdapter
        try:
            config = generic_config(inspect_repository(root))
        except ValueError as exc:
            raise DatasetError(str(exc)) from exc
        adapter = CSVAdapter(config)
    else:
        raise DatasetError(f'No adapter factory registered for {info.adapter!r}.')

    adapter.load(root)
    return adapter
