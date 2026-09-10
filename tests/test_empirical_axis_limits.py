"""Series roles, not labels or sampled model domains, control automatic axes."""
from copy import deepcopy
from dataclasses import asdict
from functools import partial
from importlib.resources import files
from types import SimpleNamespace
import json
import math

import pandas as pd
import pytest
import yaml

from psyview.app import PsyView
from psyview.models import Level, PlotSpec, Series
from psyview.plotting.axes import axis_policy, empirical_axis_values
from psyview.plotting.matplotlib_plots import MatplotlibPlotRenderer
from psyview.plotting.terminal import ScientificPlot, TerminalPlotRenderer
from psyview.plotting.pnas_plots import csf_plot, add_csf_variability_bars, subject_plot
from psyview.plotting.lateral_plots import lateral_profile_plot
from psyview.state import AnalysisState
from psyview.data.registry import open_dataset
from test_browser import tiny_dataset
from test_interactive import synthetic
from test_lateral import tiny_lateral


def policy(dataset, column):
    config = yaml.safe_load(files('psyview').joinpath(
        'configs/' + dataset + '.yaml').read_text(encoding='utf-8'))
    return config['axis_policy'][column]


def row_specs(specs, policies, overrides=None):
    adapter = SimpleNamespace(
        config={'axis_policy': {'condition': policies}},
        levels=lambda: [Level('Condition', 'condition', 'data')],
        get_plot=lambda level, filters: deepcopy(specs[filters['condition']]),
    )
    owner = SimpleNamespace(axis_scale_overrides=overrides or {},
                            _axis_config=lambda level, axis: policies.get(axis, {}))
    return [PsyView._prepare_plot_with_row_axes(
        adapter, 0, {'condition': i}, None, False, None, False,
        {}, list(range(len(specs))), partial(PsyView._decorate_axis_policy, owner),
    ) for i in range(len(specs))]


def csf(values):
    frame = pd.DataFrame({'spatial_frequency_cpd': [.5, 2, 8, 16],
                          'contrast_sensitivity': values, 'included_in_csf_fit': True})
    psf = SimpleNamespace(luminance_cd_m2=20, f_pref_mean_cpd=4)
    curves = pd.DataFrame({'spatial_frequency_cpd': [.001, 2, 1000],
                           'contrast_sensitivity': [.01, 100, 5000]})
    return csf_plot(frame, psf, {'participant_id': 'P01'}, curves, '')


@pytest.mark.parametrize('values,expected', [
    ([70, 150, 400, 850], (10, 1000)),
    ([8, 150, 400, 850], (1, 1000)),
    ([70, 150, 400, 1800], (10, 10000)),
])
def test_csf_helper_domain_and_extrema_do_not_expand_shared_axes(values, expected):
    specs = [csf([80, 150, 400, 700]), csf(values)]
    assert any(s.role == 'fit' for s in specs[0].series)
    policies = policy('pnas_psychophysics', 'luminance_cd_m2')
    results = row_specs(specs, policies)
    without_fits = deepcopy(specs)
    for spec in without_fits:
        spec.series = [s for s in spec.series if s.role == 'data']
    control = row_specs(without_fits, policies)
    for result, baseline in zip(results, control):
        assert result.ylim == expected
        assert result.xlim == baseline.xlim
        assert result.ylim == baseline.ylim
        assert result.xscale == result.yscale == 'log'
        assert .001 < result.xlim[0] <= .5
        assert 16 <= result.xlim[1] < 1000


@pytest.mark.parametrize('values', [
    [-.35, -.1, .2, .45], [-.8, -.1, .2, .7], [-1.2, .1, .7, .8],
])
def test_lateral_soft_window_expands_only_for_empirical_content(values):
    frame = pd.DataFrame({'distance_from_flanker_edge_deg': [.1, .2, .4, .8],
                          'log_sensitivity_ratio': values, 'spread': [.1] * 4})
    spec = lateral_profile_plot(frame, {'participant_id': 'P01', 'luminance_label_cd_m2': 20})
    control = deepcopy(spec)
    spec.series.append(Series([-100, .2, 100], [-2.5, 0, 2.8], 'arbitrary', role='fit'))
    policies = policy('lateral_sensitivity', 'luminance_label_cd_m2')
    result, baseline = row_specs([spec, control], policies)
    assert result.xlim == baseline.xlim
    assert result.ylim == baseline.ylim
    if min(values) >= -.8:
        assert result.ylim == (-1, 1)
    else:
        assert result.ylim[0] <= -1.25  # Includes empirical spread/2.
        assert result.ylim[1] >= 1
    assert any(s.role == 'uncertainty' for s in spec.series)
    assert result.ylim == row_specs([control], policies)[0].ylim


def test_empirical_error_endpoints_count_model_bands_do_not():
    spec = csf([70, 150, 400, 850])
    add_csf_variability_bars(spec, [{'spatial_frequency_cpd': 2,
                                   'lower_sensitivity': 8, 'upper_sensitivity': 1800}])
    spec.series.append(Series([2, 2], [.0001, 1e6], 'uncertainty', role='fit'))
    assert [s.role for s in spec.series if s.label == 'Across-staircase threshold SD'] == ['uncertainty']
    assert min(empirical_axis_values(spec, 'y')) == 8
    assert max(empirical_axis_values(spec, 'y')) == 1800
    result = row_specs([spec], policy('pnas_psychophysics', 'luminance_cd_m2'))[0]
    assert result.ylim == (1, 10000)


@pytest.mark.parametrize('scale', ['linear', 'log'])
def test_scale_overrides_ignore_overlays_in_every_sibling(scale):
    specs = [csf([70, 150, 400, 850]), csf([8, 150, 400, 1800])]
    control = deepcopy(specs)
    for spec in control:
        spec.series = [s for s in spec.series if s.role == 'data']
    policies = policy('pnas_psychophysics', 'luminance_cd_m2')
    overrides = {(0, axis): scale for axis in ('x', 'y')}
    results = row_specs(specs, policies, overrides)
    for result, baseline in zip(results, row_specs(control, policies, overrides)):
        for axis in ('x', 'y'):
            assert axis_policy(result, axis) == axis_policy(baseline, axis)
            assert axis_policy(result, axis)[0] == scale
            assert axis_policy(result, axis) == axis_policy(results[0], axis)


def test_psf_percentiles_and_staircase_trajectory_are_primary():
    frame = pd.DataFrame({'luminance_cd_m2': [10, 403], 'f_pref_mean_cpd': [2, 8],
                          'percentile_2_5_cpd': [1, 6], 'percentile_97_5_cpd': [4, 12]})
    spec = subject_plot(frame, {'participant_id': 'P01'})
    assert sorted(empirical_axis_values(spec, 'y')) == [1, 2, 4, 6, 8, 12]
    spec.series.append(Series([1, 10000], [.01, 1000], '', role='fit'))
    assert max(empirical_axis_values(spec, 'x')) == 403
    assert max(empirical_axis_values(spec, 'y')) == 12
    stairs = PlotSpec('', '', '', [Series([1, 60], [.003, .05], 'fit in label'),
        Series([], [1000], '', 'hline'), Series([1000], [], '', 'vline'),
        Series([1000], [1000], '', 'scatter', role='cursor')], yscale='log')
    assert empirical_axis_values(stairs, 'x') == [1, 60]
    assert empirical_axis_values(stairs, 'y') == [.003, .05]
    assert axis_policy(stairs, 'y')[1] == (.001, .1)


def test_default_roles_serialization_and_overlay_only_policy():
    series = Series([1, 2], [3, 4], 'fit', 'scatter', 'red', False, 'x')
    assert series.role == 'data'
    payload = json.loads(json.dumps(asdict(series)))
    assert Series(**payload) == series
    del payload['role']
    assert Series(**payload) == series
    series.role = 'fit'
    assert Series(**json.loads(json.dumps(asdict(series)))).role == 'fit'
    spec = PlotSpec('', '', '', [series])
    assert empirical_axis_values(spec, 'x') == []
    assert axis_policy(spec, 'x')[1] == (0, 1)
    spec.xlim = (10, 20)
    assert axis_policy(spec, 'x')[1] == (10, 20)


def test_outlying_overlays_still_draw_with_unchanged_backend_limits():
    spec = row_specs([csf([70, 150, 400, 850])],
                     policy('pnas_psychophysics', 'luminance_cd_m2'))[0]
    original = deepcopy(spec)
    widget = ScientificPlot()
    TerminalPlotRenderer().render(widget, spec, show_labels=False)
    figure = MatplotlibPlotRenderer().figure(spec)
    try:
        for _ in range(2):
            plot = deepcopy(widget.plt)
            plot.plotsize(100, 30)
            assert plot.build()
            for axis in ('x', 'y'):
                limits = getattr(spec, axis + 'lim')
                assert getattr(plot.monitor, axis + 'lim')[0] == pytest.approx(
                    [math.log10(v) for v in limits])
                assert getattr(figure.axes[0], 'get_' + axis + 'lim')() == pytest.approx(limits)
            # The overlay is submitted intact; its domain exceeds the viewport.
            assert any(min(x) < plot.monitor.xlim[0][0] for x in plot.monitor.x)
            assert any(max(y) > plot.monitor.ylim[0][1] for y in plot.monitor.y)
        assert spec == original
    finally:
        figure.clear()


def test_interactive_csf_constructor_marks_fit_and_references(synthetic):
    spec = synthetic.get_plot(1, {'participant_id': 'S', 'luminance_cd_m2': 10},
                              AnalysisState('interactive', 6))
    assert any(s.role == 'fit' for s in spec.series)
    assert all(s.role == 'reference' for s in spec.series if s.kind == 'vline')
    before = [axis_policy(spec, axis) for axis in ('x', 'y')]
    for s in spec.series:
        if s.role == 'fit':
            s.x = [.000001, 1, 1e6]
            s.y = [.000001, 1, 1e6]
    assert before == [axis_policy(spec, axis) for axis in ('x', 'y')]


def test_lateral_fit_constructor_marks_overlays(tiny_lateral, monkeypatch):
    adapter = open_dataset(tiny_lateral)
    monkeypatch.setattr('psyview.analysis.lateral_fit.fit_lateral_profile',
                        lambda *a, **k: SimpleNamespace(x_curve=[-10, 0, 10],
                            y_curve=[-100, 0, 100], frequency_cpd=3, frequency_match_score=.9,
                            n_points=1, excluded_points=0))
    monkeypatch.setattr('psyview.analysis.lateral_fit.fit_display_text', lambda result: '')
    filters = {'participant_id': 'P01', 'luminance_label_cd_m2': 10}
    baseline = adapter.get_plot(1, filters)
    x = baseline.series[0].x[0]
    spec = adapter.get_plot_with_fit(1, filters, fit_cursor_x=x, fit_edit=True)
    assert any(s.role == 'fit' for s in spec.series)
    assert any(s.role == 'cursor' for s in spec.series)
    for axis in ('x', 'y'):
        assert axis_policy(spec, axis) == axis_policy(baseline, axis)


@pytest.mark.parametrize('dataset', ['synthetic', 'tiny_lateral'])
def test_threshold_boxes_and_staircases_ignore_overlays(dataset, request):
    source = request.getfixturevalue(dataset)
    adapter = source if dataset == 'synthetic' else open_dataset(source)
    from psyview.state import SelectionState
    selection = SelectionState(adapter)
    for level in range(2, len(adapter.levels())):
        selection.active = level
        spec = adapter.get_plot(level, selection.filters())
        before = [axis_policy(spec, axis) for axis in ('x', 'y')]
        spec.series.extend([
            Series([.000001, 1e6], [.000001, 1e6], '', role='fit'),
            Series([], [1e6], '', 'hline', role='reference'),
        ])
        assert before == [axis_policy(spec, axis) for axis in ('x', 'y')]
        if spec.xticks:
            observations = [v for s in spec.series if s.kind == 'scatter' and s.role == 'data' for v in s.y]
            lo, hi = before[1][1]
            assert observations and all(lo <= v <= hi for v in observations)


def test_positive_fit_cannot_prevent_empirical_log_fallback():
    spec = PlotSpec('', '', '', [Series([1, 2], [-2, 0], ''),
        Series([1, 2], [10, 100], '', role='fit')], yscale='log')
    assert axis_policy(spec, 'y')[0::2] == ('linear', True)
