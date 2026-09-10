from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from psyview.app import PsyView
from psyview.models import PlotSpec, Series
from psyview.plotting.axes import axis_policy
from test_browser import tiny_dataset
from test_interactive import synthetic
from test_empirical_axis_limits import policy, row_specs


@pytest.mark.parametrize('endpoint', [0, -.2])
async def test_log_toggle_refuses_nonpositive_empirical_uncertainty_in_sibling(endpoint):
    first = PlotSpec('', 'x', 'y', [Series([1, 2], [.2, .4], '')])
    second = deepcopy(first)
    second.series.append(Series([1, 1], [endpoint, .5], '', role='uncertainty'))
    configured = policy('lateral_sensitivity', 'luminance_label_cd_m2')
    specs = row_specs([first, second], configured)
    notifications = []
    app = SimpleNamespace(
        spec=specs[0],
        selection=SimpleNamespace(active=0),
        axis_scale_overrides={},
        axis_limit_overrides={},
        notify=notifications.append,
        redraw=AsyncMock(),
    )
    before = deepcopy(app.spec)
    await PsyView._toggle_axis_scale(app, 'y')
    assert app.spec == before
    assert app.axis_scale_overrides == {}
    app.redraw.assert_not_awaited()
    assert 'requires positive empirical data and uncertainty' in notifications[0]
    overridden = row_specs([first, second], configured, {(0, 'y'): 'log'})
    assert all(axis_policy(spec, 'y') == axis_policy(specs[0], 'y') for spec in overridden)


async def test_valid_log_toggle_ignores_negative_fit_and_restores_default():
    raw = PlotSpec('', 'x', 'y', [Series([1, 2], [.2, .4], ''),
                                Series([1, 2], [-100, 100], '', role='fit')])
    configured = policy('lateral_sensitivity', 'luminance_label_cd_m2')
    app = SimpleNamespace(
        selection=SimpleNamespace(active=0),
        axis_scale_overrides={},
        axis_limit_overrides={},
        notify=lambda message: None,
    )

    async def redraw(force_background=False):
        app.spec = row_specs(
            [raw],
            configured,
            app.axis_scale_overrides,
        )[0]

    app.redraw = redraw
    await redraw()
    original = axis_policy(app.spec, 'y')
    await PsyView._toggle_axis_scale(app, 'y')
    assert axis_policy(app.spec, 'y')[0] == 'log'
    assert app.spec.ylim[0] > 0
    await PsyView._toggle_axis_scale(app, 'y')
    assert axis_policy(app.spec, 'y') == original
    assert app.axis_scale_overrides == {}


async def test_footer_hides_secondary_bindings_without_removing_actions(synthetic, tmp_path):
    app = PsyView(synthetic, tmp_path)
    async with app.run_test(size=(140, 45)) as pilot:
        bindings = {key: item.binding for key, item in app.screen.active_bindings.items()}

        for key in ('left', 'right', 'up', 'down', 'enter', 'a', 'v', 'r', 'm', 's', 'h', 'q'):
            assert bindings[key].show

        for key in ('home', 'end', 'escape', 'f', 'e', 'c', 'question_mark', 'x', 'y'):
            assert not bindings[key].show

        await pilot.press('v')
        assert app.view_focus
        assert 'VIEW' in app._view_panel_text(app.spec)

        index_before = app.view_index
        await pilot.press('down')
        assert app.view_index != index_before

        await pilot.press('escape')
        assert not app.view_focus

        await pilot.press('down', 'down', 'end')
        assert app.spec.metadata['spatial_frequency_cpd'] == 8
        await pilot.press('home')
        assert app.spec.metadata['spatial_frequency_cpd'] == .5

        await pilot.press('a')
        assert app.analysis_focus
        await pilot.press('escape')
        assert not app.analysis_focus

        notifications = []
        app.notify = lambda message, **kwargs: notifications.append(message)
        await pilot.press('f')
        assert any('lateral Luminance/profile level' in message for message in notifications)


@pytest.mark.parametrize('values,expected', [
    ([-.4, .5], (-1, 1)),
    ([-.8, .7], (-1, 1)),
    ([-1.25, .8], None),
    ([-.4, 1.25], None),
])
def test_lateral_siblings_keep_empirical_soft_window(values, expected):
    first = PlotSpec('', 'x', 'y', [Series([1, 2], values, '')])
    second = PlotSpec('', 'x', 'y', [Series([1, 2], [-.2, .3], ''),
                                   Series([1, 2], [-20, 20], '', role='fit')])
    specs = row_specs(
        [first, second],
        policy('lateral_sensitivity', 'luminance_label_cd_m2'),
    )

    assert specs[0].ylim == specs[1].ylim
    lo, hi = specs[0].ylim
    assert lo <= min(values) and hi >= max(values)

    if expected:
        assert (lo, hi) == expected
    else:
        assert -20 < lo <= -1 and 1 <= hi < 20
