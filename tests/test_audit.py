import copy
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from psyview.app import PsyView
from psyview.models import PlotSpec, Series
from psyview.plotting.axes import padded_limits, axis_policy
from psyview.plotting.matplotlib_plots import MatplotlibPlotRenderer
from psyview.plotting.terminal import ScientificPlot, TerminalPlotRenderer
from psyview.state import SelectionState


@pytest.mark.parametrize('scale,values', [('linear', [1, 20]), ('linear', [5]), ('log', [.01, 2000]), ('log', [5])])
def test_padding(scale, values):
    lo, hi = padded_limits(values, scale)
    assert lo < min(values) <= max(values) < hi
    if scale == 'log':
        assert lo > 0
        assert min(values)/lo == pytest.approx(hi/max(values))


def test_invalid_log():
    with pytest.raises(ValueError):
        padded_limits([0, 1], 'log')
    spec = PlotSpec('', '', '', [Series([0, 1], [1, 2], '')], xscale='log')
    assert axis_policy(spec, 'x')[0::2] == ('linear', True)


@pytest.mark.parametrize('participant', ['P01', 'P02', 'P03', 'P04'])
def test_shared_data_all_levels(adapter, participant, tmp_path):
    filters = {'participant_id': participant}
    for luminance in adapter.get_values(1, filters)[:2]:
        state = SelectionState(adapter)
        state.memory[(0, ())] = participant
        state.memory[(1, (participant,))] = luminance
        state.refresh()
        for level in range(4):
            state.active = level
            spec = adapter.get_plot(level, state.filters())
            before = copy.deepcopy(spec)
            tables = {k: v.copy(deep=True) for k, v in adapter.tables.items()}
            widget = ScientificPlot()
            TerminalPlotRenderer().render(widget, spec)
            # Backend builds are destructive; independently disposable copies.
            for _ in range(2):
                plot = copy.deepcopy(widget.plt)
                plot.plotsize(100, 28)
                assert plot.build()
            figure = MatplotlibPlotRenderer().figure(spec)
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            FigureCanvasAgg(figure).draw()
            figure.clear()
            with patch('psyview.plotting.matplotlib_plots.subprocess.Popen') as launch:
                MatplotlibPlotRenderer().open(spec)
                path = Path(launch.call_args.args[0][-1])
                payload = json.loads(path.read_text())
                path.unlink()
            assert payload['metadata']['participant_id'] == participant
            assert payload['series'][0]['x'] == spec.series[0].x
            assert payload['series'][0]['y'] == spec.series[0].y
            assert spec == before
            for key in tables:
                pd.testing.assert_frame_equal(adapter.tables[key], tables[key])
            if level == 0:
                assert spec.xscale == 'log'
                assert spec.series[0].x == adapter.select('psf', state.filters()).sort_values('luminance_cd_m2').luminance_cd_m2.tolist()
            elif level == 1:
                assert spec.xscale == spec.yscale == 'log'
            else:
                assert spec.xscale == 'linear' and spec.yscale == 'log'


@pytest.mark.parametrize('threshold', [None, np.nan, .01])
@pytest.mark.parametrize('included', [False, True])
def test_optional_staircase(adapter, threshold, included):
    from psyview.plotting.pnas_plots import staircase_plot
    state = SelectionState(adapter)
    state.active = 3
    filters = state.filters()
    stairs = adapter.select('stairs', filters).copy()
    stairs['threshold_last8_median'] = threshold
    stairs['included_in_primary_csf'] = included
    reversals = adapter.table('reversals').iloc[:0]
    spec = staircase_plot(stairs, adapter.select('trials', filters), reversals, filters, pd.DataFrame())
    assert ('[EXCLUDED]' in spec.series[0].label) == (not included)
    assert bool([s for s in spec.series if s.kind == 'hline']) == (threshold == .01)
    assert not spec.series[1].x and not spec.series[2].x
    MatplotlibPlotRenderer().figure(spec).clear()
    TerminalPlotRenderer().render(ScientificPlot(), spec)


async def test_m_dispatch_repaint_reload(adapter, monkeypatch):
    received = []
    class Process:
        def poll(self): return 0
    def opened(self, spec):
        received.append(spec)
        return Process()
    monkeypatch.setattr(MatplotlibPlotRenderer, 'open', opened)
    app = PsyView(adapter)
    async with app.run_test(size=(140, 52)) as pilot:
        for participant in range(4):
            for lum in range(2):
                for level in range(4):
                    while app.selection.active > level:
                        await pilot.press('up')
                    while app.selection.active < level:
                        await pilot.press('down')
                    spec = app.spec
                    await pilot.press('m', 'm')
                    assert received[-1] is spec
                    await pilot.resize_terminal(75, 28)
                    await pilot.resize_terminal(140, 52)
                await pilot.press('up', 'up', 'right')
            await pilot.press('up', 'right')
        old = app.adapter
        await pilot.press('home', 'end', 'left', 'r')
        assert app.adapter is not old
        assert 'trials' not in app.adapter.tables
        await pilot.press('h', 'escape', 'question_mark', 'escape', 'q')
    assert len(received) == 64


def test_natural_numeric_sort(tmp_path):
    from psyview.data.csv_adapter import CSVAdapter
    (tmp_path/'data.csv').write_text('id\ns10\ns2\ns1\n')
    adapter = CSVAdapter({'dataset': {'name': 'test'}, 'sources': {'a': 'data.csv'}, 'hierarchy': [{'name': 'id', 'column': 'id', 'source': 'a'}]})
    adapter.load(tmp_path)
    assert adapter.get_values(0, {}) == ['s1', 's2', 's10']
