import csv
import gzip
import hashlib
from pathlib import Path
import pandas as pd
import pytest
from psyview.data.base import DatasetError
from psyview.data.csv_adapter import CSVAdapter
from psyview.data.detector import discover, infer_schema
from psyview.state import SelectionState


def test_empty_discovery(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # An installed editable checkout may still supply its convenience archive.
    assert discover(tmp_path) == tmp_path
    assert discover(tmp_path / 'missing') == tmp_path / 'missing'


def test_all_hierarchy_branches_and_thresholds(adapter):
    psf = adapter.table('psf')
    for row in psf.itertuples():
        filters = {'participant_id': row.participant_id, 'luminance_cd_m2': row.luminance_cd_m2}
        frequencies = adapter.get_values(2, filters)
        expected = adapter.table('stairs').loc[lambda t: t.condition_id.eq(row.condition_id)]
        assert frequencies == sorted(expected.spatial_frequency_cpd.unique())
        for frequency in frequencies:
            current = {**filters, 'spatial_frequency_cpd': frequency}
            ids = adapter.get_values(3, current)
            assert ids == sorted(expected.loc[expected.spatial_frequency_cpd.eq(frequency)].staircase_id)
            assert not adapter.select('stairs', current).empty
        plot = adapter.get_plot(1, filters)
        assert plot.metadata['Archived f_pref (cpd)'] == row.f_pref_mean_cpd
        assert plot.series[-1].x == [row.f_pref_mean_cpd]
    # This independent archive identity verifies correct inclusion/filter propagation.
    for row in adapter.table('csf').itertuples():
        stairs = adapter.table('stairs').loc[lambda t: t.condition_id.eq(row.condition_id) & t.spatial_frequency_cpd.eq(row.spatial_frequency_cpd) & t.included_in_primary_csf]
        assert 1 / stairs.threshold_last8_median.mean() == pytest.approx(row.contrast_sensitivity, rel=1e-12)


def test_staircase_lookup_and_lazy_cache(adapter):
    state = SelectionState(adapter)
    assert set(adapter.tables) == {'psf', 'csf', 'stairs'}
    state.down(); state.down(); state.down()
    spec = adapter.get_plot(3, state.filters())
    assert len(adapter.table('trials')) == 41606
    table = adapter.table('trials')
    selected = adapter.select('trials', state.filters())
    assert adapter.select('trials', state.filters()) is selected
    assert adapter.table('trials') is table
    row = adapter.select('stairs', state.filters()).iloc[0]
    assert spec.metadata['threshold_last8_median'] == row.threshold_last8_median
    assert spec.series[-1].y == [row.threshold_last8_median]
    assert len(spec.series[2].x) == 8
    assert spec.series[0].x == selected.trial_within_staircase.sort_values().tolist()


def test_exclusions(adapter):
    excluded = adapter.table('stairs').loc[lambda t: ~t.included_in_primary_csf]
    assert len(excluded) == 2
    for row in excluded.itertuples():
        filters = {'participant_id': row.participant_id, 'luminance_cd_m2': row.luminance_cd_m2, 'spatial_frequency_cpd': row.spatial_frequency_cpd, 'staircase_id': row.staircase_id}
        spec = adapter.get_plot(3, filters)
        assert '[EXCLUDED]' in spec.series[0].label
        assert spec.metadata['Excluded'] == 1
        assert 'author_reason_not_recorded' in spec.metadata['Exclusion reason']
    spec = adapter.get_plot(1, {'participant_id': 'P01', 'luminance_cd_m2': 72})
    assert len(next(s for s in spec.series if s.label == 'Excluded from fit').x) == 1


def test_missing_required_file(adapter, tmp_path):
    with pytest.raises(DatasetError, match='Missing required file:.*preferred_frequency.csv'):
        type(adapter)(adapter.config).load(tmp_path)


def generic_config():
    return {'dataset': {'name': 'Tiny experiment', 'adapter': 'csv'}, 'sources': {'records': 'measurements.csv.gz'},
            'hierarchy': [{'name': 'Subject', 'column': 'subject', 'source': 'records'}],
            'plots': {'subject': {'source': 'records', 'x': 'trial', 'y': 'response'}}}


@pytest.fixture
def generic(tmp_path):
    with gzip.open(tmp_path / 'measurements.csv.gz', 'wt') as file:
        file.write('subject,trial,response\nA,1,0.4\nA,2,0.3\nB,1,0.8\n')
    adapter = CSVAdapter(generic_config())
    adapter.load(tmp_path)
    return adapter


def test_generic_compressed_csv(generic):
    assert generic.get_values(0, {}) == ['A', 'B']
    plot = generic.get_plot(0, {'subject': 'A'})
    assert plot.series[0].y == [0.4, 0.3]
    state = SelectionState(generic)
    state.move(1)
    assert state.filters() == {'subject': 'B'}
    state.move(edge='first')
    assert state.filters() == {'subject': 'A'}


def test_detector_is_tentative(generic):
    schema = infer_schema(generic.root)
    assert schema['hierarchy'][0]['column'] == 'subject'
    assert schema['plots'] == {}
    assert 'tentative' in schema['detection']['confidence']
    assert schema['detection']['tables']['measurements.csv.gz']['numeric_candidates'] == ['trial', 'response']


def test_invalid_schemas_and_filters(generic):
    with pytest.raises(DatasetError, match='YAML'):
        CSVAdapter(None)
    with pytest.raises(DatasetError, match='lacks filter column'):
        generic.select('records', {'invented': 2})
    config = generic_config()
    config['sources']['records'] = '../outside.csv'
    with pytest.raises(DatasetError, match='escapes dataset root'):
        CSVAdapter(config).load(generic.root)
