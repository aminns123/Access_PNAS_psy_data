import math

import pandas as pd
import pytest

from psyview.data.registry import detect_dataset, open_dataset
from psyview.state import AnalysisState


@pytest.fixture
def tiny_lateral(tmp_path):
    root = tmp_path / 'renamed lateral experiment'
    processed = root / 'data' / 'processed'
    processed.mkdir(parents=True)

    (root / 'data_dictionary.csv').write_text(
        'file,field,description,units,data_type,missing_values\n'
        'data/processed/condition_summary.csv,participant_id,Public participant ID,not applicable,string,\n'
        'data/processed/condition_summary.csv,luminance_label_cd_m2,Archived luminance,cd m^-2,number,\n'
        'data/processed/staircase_thresholds.csv,probe_position_deg,Signed probe position,degree of visual angle,number,\n'
        'data/processed/staircase_thresholds.csv,experiment,Base or flanker experiment,not applicable,string,\n'
        'data/processed/staircase_thresholds.csv,staircase_id,Unique staircase identifier,not applicable,string,\n',
        encoding='utf-8',
    )

    pd.DataFrame([{
        'condition_id': 'P01_L010',
        'participant_id': 'P01',
        'luminance_label_cd_m2': 10,
        'included_in_thesis_main_isf': True,
        'recorded_staircases': 2,
        'included_staircases': 2,
        'excluded_staircases': 0,
        'profile_positions': 1,
        'accepted_rows': 100,
        'retained_endpoint_modes': 1,
    }]).to_csv(
        processed / 'condition_summary.csv',
        index=False,
    )

    pd.DataFrame([{
        'condition_id': 'P01_L010',
        'participant_id': 'P01',
        'luminance_label_cd_m2': 10,
        'included_in_thesis_main_isf': True,
        'endpoint_status': 'Retained descriptive mode',
        'candidate_mode': 1,
        'isf_estimate_cpd': 3.0,
        'isf_lower_cpd': 2.0,
        'isf_upper_cpd': 4.0,
        'error_minus_cpd': 1.0,
        'error_plus_cpd': 1.0,
        'accepted_rows': 100,
        'cluster_count': 80,
        'dominant_retained_mode': True,
        'interval_definition': 'test',
        'peak_locator': 'test',
    }]).to_csv(
        processed / 'isf_endpoints.csv',
        index=False,
    )

    pd.DataFrame([{
        'condition_id': 'P01_L010',
        'exclusion_candidate': 'storage_script_active_exclusions',
        'probe_position_deg': 0.0,
        'distance_from_flanker_edge_deg': 0.5,
        'base_threshold': 0.02,
        'flanker_threshold': 0.025,
        'base_sensitivity': 50.0,
        'flanker_sensitivity': 40.0,
        'log_sensitivity_ratio': math.log(40 / 50),
        'spread': 0.2,
        'base_staircases': 1,
        'flanker_staircases': 1,
    }]).to_csv(
        processed / 'lateral_profiles_recomputed.csv',
        index=False,
    )

    thresholds = []
    summaries = []
    reversals = []
    trials = []

    for experiment, sid, values in (
        ('base', 'B01', [0.01, 0.02, 0.03, 0.04, 0.05]),
        ('flanker', 'F01', [0.02, 0.03, 0.04, 0.05, 0.06]),
    ):
        threshold = float(
            math.exp(
                sum(math.log(v) for v in values)
                / len(values)
            )
        )

        thresholds.append({
            'condition_id': 'P01_L010',
            'participant_id': 'P01',
            'experiment': experiment,
            'staircase_id': sid,
            'probe_position_deg': 0.0,
            'distance_from_flanker_edge_deg': 0.5,
            'detected_reversals': 5,
            'threshold_last_five': threshold,
            'included_for_baseline_candidate': True,
        })

        summaries.append({
            'condition_id': 'P01_L010',
            'experiment': experiment,
            'staircase_id': sid,
            'source_id': sid,
            'source_staircase_id': 1,
            'probe_position_deg': 0.0,
            'trials_recorded': 6,
            'trials_used': 6,
            'distinct_signed_positions': 1,
            'detected_reversals': 5,
            'final_five_geometric_threshold': threshold,
        })

        for i, value in enumerate(values):
            reversals.append({
                'condition_id': 'P01_L010',
                'staircase_id': sid,
                'reversal_index': i,
                'trial_within_staircase': i + 1,
                'source_row': i + 1,
                'normalized_contrast': value,
                'used_in_final_five': True,
            })

        for i, value in enumerate([0.08] + values):
            trials.append({
                'condition_id': 'P01_L010',
                'experiment': experiment,
                'staircase_id': sid,
                'source_id': sid,
                'source_row': i + 1,
                'trial_within_staircase': i,
                'probe_position_deg': 0.0,
                'probe_digital_intensity': value,
                'normalized_contrast': value,
                'is_detected_reversal': i > 0,
                'reversal_index': i - 1 if i > 0 else None,
                'used_in_final_five': i > 0,
                'included_for_baseline_candidate': True,
            })

    pd.DataFrame(thresholds).to_csv(
        processed / 'staircase_thresholds.csv',
        index=False,
    )
    pd.DataFrame(summaries).to_csv(
        processed / 'staircase_summary.csv',
        index=False,
    )
    pd.DataFrame(reversals).to_csv(
        processed / 'staircase_reversals.csv',
        index=False,
    )
    pd.DataFrame(trials).to_csv(
        processed / 'staircase_trials.csv.gz',
        index=False,
    )

    return root


def test_lateral_detection_and_levels(tiny_lateral):
    info = detect_dataset(tiny_lateral)
    assert info.adapter == 'lateral'

    adapter = open_dataset(tiny_lateral)
    assert [
        level.name
        for level in adapter.levels()
    ] == [
        'Subject',
        'Luminance',
        'Position',
        'Experiment',
        'Staircase',
    ]
    assert adapter.default_n_reversals == 5


def test_lateral_archived_plots(tiny_lateral):
    adapter = open_dataset(tiny_lateral)

    filters0 = {'participant_id': 'P01'}
    assert 'ISF' in adapter.get_plot(
        0,
        filters0,
    ).title

    filters1 = {
        **filters0,
        'luminance_label_cd_m2': 10,
    }
    profile = adapter.get_plot(
        1,
        filters1,
    )
    assert profile.series[0].y[0] == pytest.approx(
        math.log(40 / 50)
    )

    filters2 = {
        **filters1,
        'probe_position_deg': 0.0,
    }
    comparison = adapter.get_plot(
        2,
        filters2,
    )
    assert comparison.metadata[
        'Base sensitivity'
    ] == 50.0

    filters3 = {
        **filters2,
        'experiment': 'base',
    }
    multi = adapter.get_plot(
        3,
        filters3,
    )
    assert multi.metadata[
        'Staircases'
    ] == 1

    filters4 = {
        **filters3,
        'staircase_id': 'B01',
    }
    single = adapter.get_plot(
        4,
        filters4,
    )
    assert single.metadata[
        'detected_reversals'
    ] == 5


def test_lateral_interactive_geometric_mean(
    tiny_lateral,
):
    adapter = open_dataset(tiny_lateral)
    engine = adapter.interactive()

    result = engine.threshold(
        'B01',
        3,
    )
    expected = (
        0.03
        * 0.04
        * 0.05
    ) ** (1 / 3)

    assert result['threshold'] == pytest.approx(
        expected
    )
    assert result['selected_indices'] == [
        2,
        3,
        4,
    ]

    filters = {
        'participant_id': 'P01',
        'luminance_label_cd_m2': 10,
    }
    spec = adapter.get_plot(
        1,
        filters,
        AnalysisState(
            'interactive',
            3,
        ),
    )
    assert (
        'geometric mean of final 3'
        in spec.title
    )
    assert spec.metadata[
        'Interactive ISF'
    ] == 'not recomputed'


def test_lateral_source_files_not_mutated(
    tiny_lateral,
):
    before = {
        path: path.read_bytes()
        for path in tiny_lateral.rglob('*')
        if path.is_file()
    }

    adapter = open_dataset(
        tiny_lateral
    )
    adapter.get_plot(
        4,
        {
            'participant_id': 'P01',
            'luminance_label_cd_m2': 10,
            'probe_position_deg': 0.0,
            'experiment': 'base',
            'staircase_id': 'B01',
        },
        AnalysisState(
            'interactive',
            3,
        ),
    )

    after = {
        path: path.read_bytes()
        for path in before
    }
    assert before == after
