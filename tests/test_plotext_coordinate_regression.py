"""Exercise real Plotext builds, not just physical axis-policy return values."""
from copy import deepcopy
from functools import partial
import math
from types import SimpleNamespace

import numpy as np
import pytest
from textual.app import App, ComposeResult

from psyview.app import PsyView
from psyview.models import Level, PlotSpec, Series
from psyview.plotting.axes import axis_policy
from psyview.plotting.matplotlib_plots import MatplotlibPlotRenderer
from psyview.plotting.terminal import ScientificPlot, TerminalPlotRenderer
from psyview.data.registry import open_dataset
from psyview.state import SelectionState
from test_browser import tiny_dataset
from test_interactive import synthetic
from test_lateral import tiny_lateral


def examples():
    return [
        PlotSpec('PSF', 'Luminance', 'Preferred frequency',
                 [Series([10, 20, 100, 403], [2, 4, 6, 8], 'data', 'scatter')],
                 xscale='log', xlim=(5, 1000), ylim=(0, 15)),
        PlotSpec('CSF', 'Frequency', 'Sensitivity',
                 [Series([.5, 1, 2, 4, 6, 8, 11.3, 16],
                         [130, 200, 250, 300, 270, 200, 120, 70], 'data', 'scatter')],
                 xscale='log', yscale='log', xlim=(.5, 20), ylim=(10, 1000)),
        PlotSpec('box', 'Frequency', 'Threshold',
                 [Series([1, 1, 1], [.0035, .004, .0045], 'data', 'scatter')],
                 yscale='log', xlim=(.45, 1.55), ylim=(.002, .005), xticks=[(1, '4')]),
        PlotSpec('staircase', 'Trial', 'Contrast',
                 [Series(list(range(1, 61)), np.geomspace(.05, .003, 60).tolist(), 'data')],
                 yscale='log', xlim=(0, 65), ylim=(.001, .1)),
    ]


def check_build(spec):
    before = deepcopy(spec)
    widget = ScientificPlot()
    TerminalPlotRenderer().render(widget, spec, show_labels=False)
    original = deepcopy(widget.plt.monitor)
    figure = MatplotlibPlotRenderer().figure(spec)
    ax = figure.axes[0]
    try:
        for width, height in [(100, 30), (75, 24), (100, 30)]:
            plot = deepcopy(widget.plt)
            plot.plotsize(width, height)
            assert plot.build()
            monitor = plot.monitor
            for axis in ('x', 'y'):
                scale, limits, _ = axis_policy(spec, axis)
                transform = math.log10 if scale == 'log' else float
                bounds = [transform(v) for v in limits]
                assert getattr(monitor, axis + 'lim')[0] == pytest.approx(bounds)
                assert getattr(ax, 'get_' + axis + 'lim')() == pytest.approx(limits)
                assert getattr(ax, 'get_' + axis + 'scale')() == scale
                for raw, built in zip(getattr(original, axis), getattr(monitor, axis)):
                    assert built == pytest.approx([transform(v) for v in raw])
                    assert all(bounds[0] - 1e-10 <= v <= bounds[1] + 1e-10 for v in built)
                ticks = getattr(original, axis + 'ticks')[0]
                if ticks:
                    assert getattr(monitor, axis + 'ticks')[0] == pytest.approx(
                        [transform(v) for v in ticks])
        assert spec == before
        assert widget.plt.monitor.x == original.x
        assert widget.plt.monitor.y == original.y
    finally:
        figure.clear()


@pytest.mark.parametrize('spec', examples(), ids=lambda s: s.title)
def test_physical_coordinates_match_both_backends(spec):
    check_build(spec)


@pytest.mark.parametrize('dataset', ['synthetic', 'tiny_lateral'])
def test_adapter_rows_build_in_both_backends(dataset, request, tmp_path):
    source = request.getfixturevalue(dataset)
    adapter = source if dataset == 'synthetic' else open_dataset(source)
    app = PsyView(adapter, tmp_path)
    state = SelectionState(adapter)
    for level in range(len(adapter.levels())):
        state.active = level
        parents = state.filters(level)
        siblings = adapter.get_values(level, parents)
        row = []
        for value in siblings:
            filters = {**parents, adapter.levels()[level].column: value}
            spec = PsyView._prepare_plot_with_row_axes(
                adapter, level, filters, None, False, None, False,
                parents, siblings, app._decorate_axis_policy,
            )
            check_build(spec)
            row.append(spec)
        assert all(spec.ylim == row[0].ylim for spec in row)
        if not row[0].xticks:
            assert all(spec.xlim == row[0].xlim for spec in row)
        else:
            assert all(spec.xticks == adapter.get_plot(
                level, {**parents, adapter.levels()[level].column: value},
            ).xticks for value, spec in zip(siblings, row))


@pytest.mark.parametrize('scale', ['linear', 'log'])
@pytest.mark.parametrize('axis', ['x', 'y'])
def test_scale_changes_resolve_all_siblings_before_sharing(scale, axis):
    specs = [PlotSpec('A', 'x', 'y', [Series([1, 2], [.003, .005], '')]),
             PlotSpec('B', 'x', 'y', [Series([20, 60], [.02, .05], '')])]
    policy = {'x': {'scale': 'log'}, 'y': {'scale': 'log', 'rounding': 'nice'}}
    adapter = SimpleNamespace(
        config={'axis_policy': {'condition': policy}},
        levels=lambda: [Level('Condition', 'condition', 'data')],
        get_plot=lambda level, filters: deepcopy(specs[filters['condition']]),
    )
    owner = SimpleNamespace(adapter=adapter, axis_scale_overrides={(0, axis): scale},
                            _axis_config=lambda level, a: policy[a])
    decorate = partial(PsyView._decorate_axis_policy, owner)
    results = [PsyView._prepare_plot_with_row_axes(
        adapter, 0, {'condition': i}, None, False, None, False, {}, [0, 1], decorate,
    ) for i in [0, 1]]
    assert axis_policy(results[0], axis) == axis_policy(results[1], axis)
    assert axis_policy(results[0], axis)[0] == scale
    for spec in results:
        check_build(spec)
    # limits: data keeps the chosen condition's local range.
    policy[axis]['limits'] = 'data'
    local = [PsyView._prepare_plot_with_row_axes(
        adapter, 0, {'condition': i}, None, False, None, False, {}, [0, 1], decorate,
    ) for i in [0, 1]]
    assert axis_policy(local[0], axis)[1] != axis_policy(local[1], axis)[1]


async def test_scientific_plot_repaints_do_not_transform_twice():
    class PlotApp(App):
        def compose(self) -> ComposeResult:
            yield ScientificPlot()
    app = PlotApp()
    async with app.run_test(size=(100, 30)) as pilot:
        widget = app.query_one(ScientificPlot)
        spec = examples()[1]
        spec.series.extend([Series([4], [], '', 'vline'),
                            Series([], [200], '', 'hline')])
        TerminalPlotRenderer().render(widget, spec, show_labels=False)
        before = deepcopy(widget.plt.monitor)
        first = widget.render().plain
        assert widget.render().plain == first
        await pilot.resize_terminal(75, 24)
        widget.render()
        await pilot.resize_terminal(100, 30)
        assert widget.render().plain == first
        for field in ('x', 'y', 'xticks', 'yticks', 'xlim', 'ylim', 'vcoord', 'hcoord'):
            assert getattr(widget.plt.monitor, field) == getattr(before, field)


async def test_keys_restore_defaults_and_keep_box_x_categorical(synthetic, tmp_path):
    app = PsyView(synthetic, tmp_path)
    async with app.run_test(size=(120, 40)) as pilot:
        for key in ('x', 'y'):
            original = deepcopy(app.spec)
            await pilot.press(key)
            assert getattr(app.spec, key + 'scale') != getattr(original, key + 'scale')
            check_build(app.spec)
            await pilot.press(key)
            assert axis_policy(app.spec, key) == axis_policy(original, key)
        await pilot.press('down', 'down')
        assert app.spec.xticks
        original = deepcopy(app.spec)
        await pilot.press('x')
        assert app.spec == original


def test_nonpositive_auxiliaries_do_not_change_log_scales():
    spec = examples()[1]
    spec.series.extend([
        Series([.5, 1, 2, 4], [-5, 0, 200, 250], 'fit'),
        Series([2, 2], [-10, 280], 'interval'),
        Series([0], [], '', 'vline'),
        Series([], [-1], '', 'hline'),
    ])
    check_build(spec)
    assert axis_policy(spec, 'x')[0] == axis_policy(spec, 'y')[0] == 'log'
