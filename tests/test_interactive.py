import copy
import gzip
import numpy as np
import pandas as pd
import pytest
from test_browser import tiny_dataset
from psyview.analysis.interactive import InteractiveAnalysis
from psyview.analysis.source_helpers import AoE, count_reversals_HighLow
from psyview.data.registry import open_dataset
from psyview.state import AnalysisState, SelectionState
from psyview.app import PsyView
from psyview.plotting.matplotlib_plots import MatplotlibPlotRenderer
from psyview.plotting.terminal import ScientificPlot, TerminalPlotRenderer


@pytest.fixture
def synthetic(tiny_dataset):
    rows, trials, reversals, points = [], [], [], []
    for j, sf in enumerate([.5, 1, 2, 4, 8]):
        sid = f'S{j}'
        sensitivity = float(AoE(sf, 1, 100, 3, 2))
        contrast = 1/sensitivity
        values = [contrast*(1.1 if i % 2 == 0 else .9) for i in range(12)]
        count, indices, detected = count_reversals_HighLow(values)
        threshold = float(np.median(detected[-8:]))
        rows.append(dict(staircase_id=sid, participant_id='S', condition_id='C', spatial_frequency_cpd=sf,
                         threshold_last8_median=threshold, included_in_primary_csf=True,
                         n_trials=12,n_trials_used=12,n_detected_reversals=count,exclusion_reason=''))
        for i, value in enumerate(values):
            trials.append(dict(condition_id='C',participant_id='S',luminance_cd_m2=10,spatial_frequency_cpd=sf,
                               staircase_id=sid,trial_within_staircase=i+1,contrast_normalized_source=value))
        for i, (index,value) in enumerate(zip(indices,detected)):
            reversals.append(dict(condition_id='C',participant_id='S',staircase_id=sid,reversal_number_detected=i+1,
                                  trial_within_staircase=index+1,contrast_normalized_source=value,in_last8_point_estimate=i>=count-8))
        points.append(dict(condition_id='C',participant_id='S',luminance_cd_m2=10,spatial_frequency_cpd=sf,
                           contrast_sensitivity=1/threshold,contrast_threshold=threshold,included_in_csf_fit=True))
    pd.DataFrame(rows).to_csv(tiny_dataset/'data/raw/staircase_summary.csv',index=False)
    pd.DataFrame(trials).to_csv(tiny_dataset/'data/raw/trials.csv.gz',index=False)
    pd.DataFrame(reversals).to_csv(tiny_dataset/'data/raw/staircase_reversals.csv',index=False)
    pd.DataFrame(points).to_csv(tiny_dataset/'data/processed/csf_thresholds.csv',index=False)
    return open_dataset(tiny_dataset)


def test_reversal_membership_threshold_and_short(synthetic):
    engine = synthetic.interactive()
    eight = engine.threshold('S0',8)
    assert eight['selected_numbers'] == list(range(3,11))
    assert eight['threshold'] == synthetic.table('stairs').iloc[0].threshold_last8_median
    six = engine.threshold('S0',6)
    assert six['selected_numbers'] == list(range(5,11))
    assert engine.threshold('S0',11)['threshold'] is None
    assert 'Insufficient' in engine.threshold('S0',11)['reason']
    assert engine.max_n() == 10
    assert len(engine.cache) == 3


def test_sensitivity_fit_and_psf_propagation(synthetic):
    engine = synthetic.interactive()
    result = engine.condition('C',8,fit=True)
    np.testing.assert_allclose(result['frame'].contrast_sensitivity, synthetic.table('csf').contrast_sensitivity, rtol=1e-14)
    assert result['peak'] is not None and len(result['curve_x']) >= 999
    assert engine.condition('C',8,fit=True) is result
    interactive = synthetic.get_plot(0,{'participant_id':'S'},AnalysisState('interactive',8))
    assert interactive.series[0].y == [result['peak']]
    assert all(s.kind=='scatter' for s in interactive.series)  # no archived error bars reused
    assert engine.condition('C',1,fit=True) is not result


@pytest.mark.parametrize('level',range(4))
def test_both_renderers_immutability(synthetic,level):
    state = SelectionState(synthetic)
    state.active = level
    synthetic.table('trials'); synthetic.table('reversals')
    before = {k:v.copy(deep=True) for k,v in synthetic.tables.items()}
    archived = synthetic.get_plot(level,state.filters())
    for mode in ('archived','interactive'):
        spec = synthetic.get_plot(level,state.filters(),AnalysisState(mode,6))
        assert ('INTERACTIVE' if mode=='interactive' else 'ARCHIVED PNAS') in spec.title
        MatplotlibPlotRenderer().figure(spec).clear()
        widget=ScientificPlot()
        TerminalPlotRenderer().render(widget,spec)
        plot=copy.deepcopy(widget.plt); plot.plotsize(100,30); assert plot.build()
    assert synthetic.get_plot(level,state.filters()) == archived
    for key in before:
        pd.testing.assert_frame_equal(before[key],synthetic.tables[key])


def test_excluded_staircase_is_visible_not_aggregated(synthetic):
    synthetic.tables['stairs'].loc[0,'included_in_primary_csf']=False
    synthetic.tables['stairs']['exclusion_reason']=synthetic.tables['stairs'].exclusion_reason.astype(object)
    synthetic.tables['stairs'].loc[0,'exclusion_reason']='synthetic exclusion'
    engine=synthetic.interactive()
    assert engine.threshold('S0',8)['threshold'] is not None
    assert np.isnan(engine.condition('C',8)['frame'].iloc[0].contrast_sensitivity)
    spec=synthetic.get_plot(3,{'participant_id':'S','luminance_cd_m2':10,'spatial_frequency_cpd':.5,'staircase_id':'S0'},AnalysisState('interactive',8))
    assert '[EXCLUDED]' in spec.series[0].label


def test_dataset_cache_separation_and_modification(synthetic,tiny_dataset,tmp_path):
    import shutil
    first=synthetic.interactive().identity()
    second=tmp_path/'second'
    shutil.copytree(tiny_dataset,second)  # tiny synthetic fixture only
    assert open_dataset(second).interactive().identity() != first
    path=tiny_dataset/'data/raw/staircase_reversals.csv'
    path.write_text(path.read_text()+'\n')
    with pytest.raises(ValueError,match='Press R'):
        synthetic.get_plot(0,{'participant_id':'S'},AnalysisState('interactive',8))


def test_persistent_cache_reuses_only_matching_n(synthetic,monkeypatch):
    result=synthetic.interactive().condition('C',8,fit=True)
    reopened=open_dataset(synthetic.root)
    def no_fit(*args,**kwargs): raise AssertionError('Same dataset/N should reuse disk fit')
    monkeypatch.setattr('psyview.analysis.interactive.fit_to_CSF',no_fit)
    assert reopened.interactive().condition('C',8,fit=True)['peak']==result['peak']
    with pytest.raises(AssertionError):
        reopened.interactive().condition('C',6,fit=True)


def test_no_reversals_and_detection_mismatch(tiny_dataset):
    trials=tiny_dataset/'data/raw/trials.csv.gz'
    frame=pd.read_csv(trials)
    frame['contrast_normalized_source']=[.3,.2,.1]
    frame.to_csv(trials,index=False)
    reversals=tiny_dataset/'data/raw/staircase_reversals.csv'
    rows=pd.read_csv(reversals)
    rows.iloc[:0].to_csv(reversals,index=False)
    adapter=open_dataset(tiny_dataset)
    assert adapter.interactive().threshold('A',1)['threshold'] is None
    rows.to_csv(reversals,index=False)
    adapter=open_dataset(tiny_dataset)
    with pytest.raises(ValueError,match='differs from deposited'):
        adapter.interactive().threshold('A',1)


async def wait_for_plot(app,pilot):
    for _ in range(300):
        if app.spec is not None:
            return
        await pilot.pause(.05)
    pytest.fail('Interactive plot did not finish')


async def test_analysis_focus_n_and_stale_results(synthetic,monkeypatch):
    received=[]
    class Process:
        def poll(self): return 0
    monkeypatch.setattr(MatplotlibPlotRenderer,'open',lambda self,spec: received.append(spec) or Process())
    app=PsyView(synthetic)
    async with app.run_test(size=(130,45)) as pilot:
        assert app.analysis.mode=='archived'
        await pilot.press('a','enter')
        await wait_for_plot(app,pilot)
        assert app.analysis.mode=='interactive'
        selection=app.selection.selected.copy()
        await pilot.press('left','left')
        await wait_for_plot(app,pilot)
        assert app.analysis.n_reversals==6 and app.selection.selected==selection
        assert 'final 6' in app.spec.title
        await pilot.press('m','a','down','down','down')
        await wait_for_plot(app,pilot)
        await pilot.press('m','a','end')
        await wait_for_plot(app,pilot)
        assert app.analysis.n_reversals==10
        await pilot.press('enter')
        assert app.analysis.mode=='archived' and 'ARCHIVED' in app.spec.title
        assert all('INTERACTIVE' in spec.title for spec in received)
        await pilot.press('escape','r','q')


def test_real_n8_thresholds_and_downstream(adapter):
    engine=adapter.interactive()
    for row in adapter.table('stairs').itertuples():
        assert engine.threshold(row.staircase_id,8)['threshold']==row.threshold_last8_median
    metrics=pd.read_csv(adapter.root/'data/processed/csf_fit_metrics_recomputed.csv',float_precision='round_trip')
    for row in adapter.table('psf').itertuples():
        result=engine.condition(row.condition_id,8,fit=True)
        original=adapter.table('csf').loc[lambda f:f.condition_id.eq(row.condition_id)].sort_values('spatial_frequency_cpd')
        np.testing.assert_array_equal(result['frame'].contrast_sensitivity,original.contrast_sensitivity)
        expected=metrics.loc[metrics.condition_id.eq(row.condition_id),'baseline_fit_peak_cpd'].iloc[0]
        assert result['peak']==pytest.approx(expected,abs=1e-12)
