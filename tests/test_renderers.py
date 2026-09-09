import pytest
from psyview.app import PsyView
from psyview.state import SelectionState
from psyview.plotting.matplotlib_plots import MatplotlibPlotRenderer
from PIL import Image


async def test_full_navigation_and_save(adapter, tmp_path):
    app = PsyView(adapter, tmp_path)
    async with app.run_test(size=(140, 52)) as pilot:
        await pilot.press('down', 'down')
        assert app.selection.active == 2
        assert app.spec.metadata['Staircases'] >= 1
        await pilot.press('down', 'right', 'end')
        assert app.selection.active == 3
        assert 'threshold_last8_median' in app.spec.metadata
        await pilot.press('s')
        assert len(list(tmp_path.glob('*.png'))) == 1
        previous = app.selection.selected.copy()
        await pilot.press('r')
        assert app.selection.selected == previous
        await pilot.press('h', 'escape')
        app.save_screenshot('staircase.svg', path=str(tmp_path))
        await pilot.resize_terminal(75, 28)
        await pilot.press('left', 'up', 'up', 'up', 'home')
        assert app.selection.active == 0
        assert app.spec is not None


def test_matplotlib_all_levels(adapter, tmp_path):
    state = SelectionState(adapter)
    renderer = MatplotlibPlotRenderer()
    for level in range(4):
        state.active = level
        spec = adapter.get_plot(level, state.filters())
        path = tmp_path / f'level-{level}.png'
        renderer.save(spec, path)
        with Image.open(path) as image:
            assert image.size == (2200, 1300)
        figure = renderer.figure(spec)
        assert figure.axes[0].get_xscale() == spec.xscale
        assert figure.axes[0].get_yscale() == spec.yscale
        figure.clear()


async def test_refuses_export_inside_archive(adapter):
    app = PsyView(adapter, adapter.root / 'never-create-this')
    async with app.run_test() as pilot:
        await pilot.press('s')
        assert not (adapter.root / 'never-create-this').exists()
