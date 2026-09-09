import gzip
from pathlib import Path
import pytest
from textual.widgets import OptionList, Static
from psyview.data.registry import detect_dataset, open_dataset
from psyview.ui.dataset_browser import DatasetBrowser


@pytest.fixture
def tiny_dataset(tmp_path):
    root = tmp_path/'arbitrarily renamed experiment'
    (root/'data/raw').mkdir(parents=True)
    (root/'data/processed').mkdir()
    (root/'data_dictionary.csv').write_text('field,description\nx,test\n')
    (root/'data/processed/preferred_frequency.csv').write_text('condition_id,participant_id,luminance_cd_m2,f_pref_mean_cpd,percentile_2_5_cpd,percentile_97_5_cpd\nC,S,10,2,1,3\n')
    (root/'data/processed/csf_thresholds.csv').write_text('condition_id,participant_id,luminance_cd_m2,spatial_frequency_cpd,contrast_sensitivity,contrast_threshold,included_in_csf_fit\nC,S,10,1,10,0.1,True\n')
    (root/'data/raw/staircase_summary.csv').write_text('staircase_id,participant_id,condition_id,spatial_frequency_cpd,threshold_last8_median,included_in_primary_csf,n_trials,n_trials_used,n_detected_reversals,exclusion_reason\nA,S,C,1,0.1,True,3,3,1,\n')
    (root/'data/raw/staircase_reversals.csv').write_text('condition_id,participant_id,staircase_id,reversal_number_detected,trial_within_staircase,contrast_normalized_source,in_last8_point_estimate\nC,S,A,1,2,0.1,True\n')
    with gzip.open(root/'data/raw/trials.csv.gz','wt') as stream:
        stream.write('condition_id,participant_id,luminance_cd_m2,spatial_frequency_cpd,staircase_id,trial_within_staircase,contrast_normalized_source\nC,S,10,1,A,1,0.2\nC,S,10,1,A,2,0.1\nC,S,10,1,A,3,0.2\n')
    detect_dataset.cache_clear()
    return root


def test_external_renamed_detection_readonly(tiny_dataset):
    before = {p: p.read_bytes() for p in tiny_dataset.rglob('*') if p.is_file()}
    info = detect_dataset(tiny_dataset)
    assert info.adapter == 'pnas'
    adapter = open_dataset(tiny_dataset)
    assert adapter.root == tiny_dataset
    adapter.get_plot(0, {'participant_id':'S'})
    assert before == {p:p.read_bytes() for p in before}
    assert detect_dataset(tiny_dataset.parent) is None


async def test_browser_navigation(tiny_dataset):
    ordinary = tiny_dataset.parent/'ordinary'
    ordinary.mkdir()
    app = DatasetBrowser(tiny_dataset.parent)
    async with app.run_test() as pilot:
        await pilot.press('end','enter')
        assert app.folder == ordinary
        await pilot.press('backspace')
        assert app.folder == tiny_dataset.parent
        await pilot.press('home','down')
        assert 'SUPPORTED DATASET' in str(app.query_one('#details', Static).render())
        await pilot.press('r','home','down','enter')
    assert app.return_value.root == tiny_dataset


def test_cli_bypasses_browser(tiny_dataset, monkeypatch):
    import sys
    from psyview.__main__ import main
    from psyview.app import PsyView
    called = []
    monkeypatch.setattr(sys,'argv',['psyview','--data-root',str(tiny_dataset)])
    monkeypatch.setattr(PsyView,'run',lambda app: called.append(app.adapter.root))
    monkeypatch.setattr(DatasetBrowser,'run',lambda app: pytest.fail('Browser must be bypassed'))
    monkeypatch.setattr('psyview.preferences.remember_dataset',lambda root: None)
    main()
    assert called == [tiny_dataset]
